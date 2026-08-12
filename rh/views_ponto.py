# -*- coding: utf-8 -*-
"""
Views para Importação e Tratativa de Falhas de Batida de Ponto
"""
import logging
import json
import pandas as pd
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.utils import timezone

from rh.models import (
    Colaborador,
    MapeamentoMatricula,
    DemandaFalhaPonto,
    StatusDemanda,
    JornadaDiariaFalha,
    ItemFalhaPonto,
    StatusTratativa
)

from rh.services.ponto_matcher import sugerir_colaboradores_similares
from qms.views_helpers import get_colaborador_for_user

logger = logging.getLogger(__name__)


@login_required
def importar_falhas_ponto_view(request):
    """
    Renderiza a tela de upload ou processa o arquivo Excel de batidas de ponto.
    """
    if request.method == 'GET':
        return render(request, 'rh/importar_falhas_ponto.html')

    if request.method == 'POST':
        excel_file = request.FILES.get('file')
        if not excel_file:
            return JsonResponse({'status': 'ERRO', 'mensagem': 'Nenhum arquivo enviado.'}, status=400)

        try:
            # Ler Excel
            df = pd.read_excel(excel_file)
        except Exception as e:
            logger.exception("Erro ao ler planilha excel de ponto.")
            return JsonResponse({'status': 'ERRO', 'mensagem': f'Falha ao abrir arquivo Excel: {str(e)}'}, status=400)

        # Padronizar nomes de colunas (strip e unificação de variações comuns)
        col_map = {}
        for col in df.columns:
            c_str = str(col).strip()
            c_lower = c_str.lower()
            if 'registro' in c_lower:
                col_map[col] = 'Registro'
            elif 'sobrenome' in c_lower or 'nome' in c_lower and 'manager' not in c_lower:
                col_map[col] = 'Nome'
            elif 'data' in c_lower:
                col_map[col] = 'Data'
            elif c_lower == 'err':
                col_map[col] = 'Err'
            elif 'notifica' in c_lower:
                col_map[col] = 'Notificacoes'
            elif 'manager' in c_lower and '.1' not in c_lower:
                col_map[col] = 'Manager_Matricula'
            elif 'manager' in c_lower and '.1' in c_lower:
                col_map[col] = 'Manager_Nome'
            elif 'trabdi' in c_lower or 'jornada' in c_lower:
                col_map[col] = 'Jornada'
            elif c_str.upper() in ['E1', 'S1', 'E2', 'S2', 'E3', 'S3']:
                col_map[col] = c_str.upper()



        df.rename(columns=col_map, inplace=True)

        if 'Registro' not in df.columns or 'Data' not in df.columns:
            return JsonResponse({
                'status': 'ERRO',
                'mensagem': "Planilha inválida. As colunas 'Registro' e 'Data' são obrigatórias."
            }, status=400)

        df['Registro_Str'] = df['Registro'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)

        # 1. Identificar registros únicos na planilha
        registros_unicos = df[['Registro_Str', 'Nome']].drop_duplicates(subset=['Registro_Str'])

        # 2. Buscar De-Para existentes
        mapeamentos = dict(MapeamentoMatricula.objects.values_list('matricula_planilha', 'colaborador__id'))

        orfaos = []
        de_para_map = {} # reg_str -> Colaborador instance

        for _, row in registros_unicos.iterrows():
            reg_planilha = row['Registro_Str']
            nome_planilha = str(row['Nome']) if pd.notna(row['Nome']) else ""

            # Caso 1: Já mapeado na tabela MapeamentoMatricula
            if reg_planilha in mapeamentos:
                colab = Colaborador.objects.filter(id=mapeamentos[reg_planilha]).first()
                if colab:
                    if not colab.matricula_global or str(colab.matricula_global).strip() == '':
                        colab.matricula_global = reg_planilha
                        colab.save(update_fields=['matricula_global'])
                    de_para_map[reg_planilha] = colab
                    continue

            # Caso 2: Matrícula da planilha é exatamente a matrícula ou matrícula global cadastrada no banco
            colab_direto = Colaborador.objects.filter(
                Q(matricula=reg_planilha) | Q(matricula_global=reg_planilha)
            ).first()
            if colab_direto:
                if not colab_direto.matricula_global or str(colab_direto.matricula_global).strip() == '':
                    colab_direto.matricula_global = reg_planilha
                    colab_direto.save(update_fields=['matricula_global'])
                de_para_map[reg_planilha] = colab_direto
                continue



            # Caso 3: Não encontrado -> Órfão que necessita de vínculo
            sugestoes = sugerir_colaboradores_similares(nome_planilha)
            orfaos.append({
                'registro_planilha': reg_planilha,
                'nome_planilha': nome_planilha,
                'sugestoes': sugestoes
            })

        # SE HOUVER ÓRFÃOS: Interrompe a importação e solicita resolução no frontend
        if orfaos:
            return JsonResponse({
                'status': 'PENDENTE_RESOLUCAO',
                'mensagem': f'Encontrados {len(orfaos)} colaborador(es) sem vínculo direto.',
                'orfaos': orfaos
            }, status=422)

        # PROCESSAMENTO TRANSACIONAL
        jornadas_processadas = 0
        try:
            with transaction.atomic():
                nome_arq = uploaded_file.name if hasattr(uploaded_file, 'name') else "relatorio_ponto.xlsx"
                data_str = datetime.now().strftime('%d/%m/%Y %H:%M')
                titulo_demanda = f"Importação de {data_str}"

                demanda = DemandaFalhaPonto.objects.create(
                    titulo=titulo_demanda,
                    arquivo_nome=nome_arq,
                    importado_por=request.user if request.user.is_authenticated else None,
                    status=StatusDemanda.ATIVA
                )

                grouped = df.groupby(['Registro_Str', 'Data'])

                for (reg_planilha, data_val), group_df in grouped:
                    colaborador = de_para_map[reg_planilha]
                    first_row = group_df.iloc[0]

                    # Parse data
                    if isinstance(data_val, pd.Timestamp):
                        data_obj = data_val.date()
                    elif isinstance(data_val, datetime):
                        data_obj = data_val.date()
                    else:
                        data_obj = pd.to_datetime(data_val).date()

                    e1_val, s1_val, e2_val, s2_val, e3_val, s3_val = (
                        get_batida('E1'), get_batida('S1'), get_batida('E2'),
                        get_batida('S2'), get_batida('E3'), get_batida('S3')
                    )

                    # Obter dados do Manager/Líder do relatório
                    manager_reg = str(first_row.get('Manager_Matricula', '')).strip().replace(r'\.0$', '') if pd.notna(first_row.get('Manager_Matricula')) else None
                    if manager_reg in ['nan', 'None', '', '0']:
                        manager_reg = None

                    manager_nome = str(first_row.get('Manager_Nome', '')).strip() if pd.notna(first_row.get('Manager_Nome')) else None
                    if manager_nome in ['nan', 'None', '']:
                        manager_nome = None

                    lider_obj = None
                    if manager_reg:
                        lider_obj = Colaborador.objects.filter(
                            Q(matricula=manager_reg) | Q(matricula_global=manager_reg)
                        ).first()
                    if not lider_obj and manager_nome:
                        lider_obj = Colaborador.objects.filter(nome_completo__iexact=manager_nome).first()

                    if lider_obj and lider_obj.posto_lideranca in [None, '', 'NAO_APLICA']:
                        lider_obj.posto_lideranca = 'LIDER'
                        lider_obj.save(update_fields=['posto_lideranca'])

                    jornada_prev_str = str(first_row.get('Jornada', '')).strip() if pd.notna(first_row.get('Jornada')) else ""

                    # Regra de Negócio: Ignorar dias de descanso/domingo/dsr/folga/feriado sem nenhuma batida registrada
                    jp_lower = jornada_prev_str.lower()
                    tem_batida = any(v and str(v).strip() not in ['', 'None', 'nan', '--:--'] for v in [e1_val, s1_val, e2_val, s2_val, e3_val, s3_val])
                    is_descanso = any(k in jp_lower for k in ['descanso', 'domingo', 'dsr', 'folga', 'feriado'])

                    if is_descanso and not tem_batida:
                        continue

                    jornada, _ = JornadaDiariaFalha.objects.update_or_create(
                        demanda=demanda,
                        colaborador=colaborador,
                        data=data_obj,
                        defaults={
                            'lider': lider_obj,
                            'matricula_lider': manager_reg,
                            'nome_lider': manager_nome,
                            'jornada_prevista': jornada_prev_str if jornada_prev_str else None,
                            'e1': e1_val,
                            's1': s1_val,
                            'e2': e2_val,
                            's2': s2_val,
                            'e3': e3_val,
                            's3': s3_val,
                            'status_tratativa': StatusTratativa.PENDENTE
                        }
                    )

                    # Atualiza os itens de erro consolidados do dia
                    jornada.erros.all().delete()

                    for _, row in group_df.iterrows():
                        err_code = str(row.get('Err', '')) if pd.notna(row.get('Err')) else 'ERRO'
                        desc_notif = str(row.get('Notificacoes', '')) if pd.notna(row.get('Notificacoes')) else 'Sem descrição'
                        ItemFalhaPonto.objects.create(
                            jornada=jornada,
                            codigo_erro=err_code,
                            descricao_notificacao=desc_notif
                        )

                    jornadas_processadas += 1

        except Exception as e:
            logger.exception("Erro ao salvar falhas de ponto no banco.")
            return JsonResponse({'status': 'ERRO', 'mensagem': f'Erro de banco de dados: {str(e)}'}, status=500)

        return JsonResponse({
            'status': 'SUCESSO',
            'demanda_id': demanda.id,
            'mensagem': f'Demanda "#{demanda.id} - {demanda.titulo}" gerada com sucesso! {jornadas_processadas} falhas de ponto registradas.'
        })



@login_required
@require_POST
def api_confirmar_depara(request):
    """
    Recebe os vínculos 'de-para' confirmados pelo operador e salva na MapeamentoMatricula.
    Payload esperado JSON: {"vinculos": [{"registro_planilha": "123", "colaborador_id": 45}, ...]}
    """
    try:
        data = json.loads(request.body)
        vinculos = data.get('vinculos', [])
        
        salvos = 0
        with transaction.atomic():
            for v in vinculos:
                reg_planilha = str(v.get('registro_planilha', '')).strip()
                colab_id = v.get('colaborador_id')
                if reg_planilha and colab_id:
                    MapeamentoMatricula.objects.update_or_create(
                        matricula_planilha=reg_planilha,
                        defaults={'colaborador_id': colab_id}
                    )
                    colab = Colaborador.objects.filter(id=colab_id).first()
                    if colab and (not colab.matricula_global or str(colab.matricula_global).strip() == ''):
                        colab.matricula_global = reg_planilha
                        colab.save(update_fields=['matricula_global'])
                    salvos += 1


        return JsonResponse({
            'status': 'SUCESSO',
            'mensagem': f'{salvos} vínculo(s) de matrícula salvo(s) com sucesso!'
        })
    except Exception as e:
        logger.exception("Erro ao salvar mapeamento de matrícula.")
        return JsonResponse({'status': 'ERRO', 'mensagem': str(e)}, status=400)


@login_required
def demandas_falhas_ponto_view(request):
    """
    Listagem de todas as Demandas de Falhas de Ponto (Importações).
    """
    status_filtro = request.GET.get('status', 'TODOS')
    search_q = request.GET.get('q', '').strip()

    qs = DemandaFalhaPonto.objects.all().select_related('importado_por').prefetch_related('jornadas')

    if status_filtro != 'TODOS':
        qs = qs.filter(status=status_filtro)

    if search_q:
        qs = qs.filter(
            Q(titulo__icontains=search_q) |
            Q(arquivo_nome__icontains=search_q) |
            Q(observacoes__icontains=search_q)
        )

    total_demandas = DemandaFalhaPonto.objects.count()
    demandas_ativas = DemandaFalhaPonto.objects.filter(status=StatusDemanda.ATIVA).count()
    demandas_arquivadas = DemandaFalhaPonto.objects.filter(status=StatusDemanda.ARQUIVADA).count()

    context = {
        'demandas': qs,
        'status_filtro': status_filtro,
        'search_q': search_q,
        'total_demandas': total_demandas,
        'demandas_ativas': demandas_ativas,
        'demandas_arquivadas': demandas_arquivadas,
        'status_choices': StatusDemanda.choices
    }

    return render(request, 'rh/demandas_falhas_ponto.html', context)


@login_required
@require_POST
def api_alternar_status_demanda(request, demanda_id):
    """
    Alterna o status de uma demanda entre ATIVA e ARQUIVADA.
    """
    demanda = get_object_or_404(DemandaFalhaPonto, id=demanda_id)
    if demanda.status == StatusDemanda.ATIVA:
        demanda.status = StatusDemanda.ARQUIVADA
    else:
        demanda.status = StatusDemanda.ATIVA
    demanda.save(update_fields=['status'])
    return JsonResponse({
        'status': 'SUCESSO',
        'novo_status': demanda.status,
        'novo_status_display': demanda.get_status_display()
    })


@login_required
@require_POST
def api_excluir_demanda(request, demanda_id):
    """
    Exclui uma demanda e todas as suas jornadas registradas (com delete em cascata).
    """
    demanda = get_object_or_404(DemandaFalhaPonto, id=demanda_id)
    titulo = demanda.titulo
    demanda.delete()
    return JsonResponse({
        'status': 'SUCESSO',
        'mensagem': f'Demanda "{titulo}" e todos os seus registros de batidas foram excluídos com sucesso!'
    })


@login_required
def tratativa_falhas_ponto_view(request, demanda_id=None):
    """
    Tela principal de tratativa das falhas de batida de ponto para Líderes/Supervisores/Gerentes.
    Exibe os dados agrupados por Manager e Colaborador para a demanda selecionada.
    """
    user = request.user
    status_filtro = request.GET.get('status', StatusTratativa.PENDENTE)
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    q_colab = request.GET.get('q_colab', '').strip()

    if not demanda_id:
        demanda_id = request.GET.get('demanda_id')

    demanda = None
    if demanda_id:
        demanda = get_object_or_404(DemandaFalhaPonto, id=demanda_id)
    else:
        demanda = DemandaFalhaPonto.objects.filter(status=StatusDemanda.ATIVA).first()
        if not demanda:
            demanda = DemandaFalhaPonto.objects.first()

    colaborador_logado = get_colaborador_for_user(user)

    if demanda:
        qs = JornadaDiariaFalha.objects.filter(demanda=demanda)
    else:
        qs = JornadaDiariaFalha.objects.none()


    # Se não for superusuario/staff sem equipe, restringe aos liderados
    if not (user.is_superuser or user.is_staff):
        if not colaborador_logado:
            qs = JornadaDiariaFalha.objects.none()
        else:
            qs = qs.filter(
                Q(lider=colaborador_logado) |
                Q(matricula_lider=colaborador_logado.matricula) |
                Q(matricula_lider=colaborador_logado.matricula_global) |
                Q(colaborador__lider=colaborador_logado) |
                Q(colaborador__supervisor=colaborador_logado) |
                Q(colaborador__gerente=colaborador_logado) |
                Q(colaborador=colaborador_logado)
            )
    else:
        # Se for superuser/staff com filtro por Manager no GET
        manager_id = request.GET.get('lider_id') or request.GET.get('manager_id')
        if manager_id:
            if str(manager_id).isdigit():
                sel_lider = Colaborador.objects.filter(id=manager_id).first()
                if sel_lider:
                    qs = qs.filter(
                        Q(lider=sel_lider) |
                        Q(matricula_lider=sel_lider.matricula) |
                        Q(matricula_lider=sel_lider.matricula_global) |
                        Q(nome_lider__iexact=sel_lider.nome_completo) |
                        Q(colaborador__lider=sel_lider) |
                        Q(colaborador__supervisor=sel_lider) |
                        Q(colaborador__gerente=sel_lider)
                    )
            else:
                qs = qs.filter(
                    Q(matricula_lider=manager_id) |
                    Q(nome_lider__icontains=manager_id)
                )

    if q_colab:
        qs = qs.filter(
            Q(colaborador__nome_completo__icontains=q_colab) |
            Q(colaborador__matricula__icontains=q_colab) |
            Q(colaborador__matricula_global__icontains=q_colab)
        )

    # Excluir falsos-positivos (Dias de descanso/domingo/dsr/folga sem nenhuma marcação de batida)
    rest_keywords = ['descanso', 'domingo', 'dsr', 'folga', 'feriado']
    filter_rest = Q()
    for kw in rest_keywords:
        filter_rest.add(Q(jornada_prevista__icontains=kw), Q.OR)

    empty_batidas = (
        (Q(e1__isnull=True) | Q(e1='') | Q(e1='nan') | Q(e1='--:--')) &
        (Q(s1__isnull=True) | Q(s1='') | Q(s1='nan') | Q(s1='--:--')) &
        (Q(e2__isnull=True) | Q(e2='') | Q(e2='nan') | Q(e2='--:--')) &
        (Q(s2__isnull=True) | Q(s2='') | Q(s2='nan') | Q(s2='--:--')) &
        (Q(e3__isnull=True) | Q(e3='') | Q(e3='nan') | Q(e3='--:--')) &
        (Q(s3__isnull=True) | Q(s3='') | Q(s3='nan') | Q(s3='--:--'))
    )

    qs = qs.exclude(filter_rest & empty_batidas)

    if status_filtro and status_filtro != 'TODOS':
        qs = qs.filter(status_tratativa=status_filtro)

    if data_inicio:
        qs = qs.filter(data__gte=data_inicio)
    if data_fim:
        qs = qs.filter(data__lte=data_fim)

    jornadas = qs.select_related(
        'colaborador',
        'colaborador__setor',
        'lider',
        'tratado_por'
    ).prefetch_related('erros').order_by('colaborador__nome_completo', 'data')

    # Queryset base para contadores gerais
    base_counts_qs = JornadaDiariaFalha.objects.all().exclude(filter_rest & empty_batidas)
    if not (user.is_superuser or user.is_staff):
        if colaborador_logado:
            base_counts_qs = base_counts_qs.filter(
                Q(lider=colaborador_logado) |
                Q(matricula_lider=colaborador_logado.matricula) |
                Q(colaborador__lider=colaborador_logado) |
                Q(colaborador=colaborador_logado)
            )
        else:
            base_counts_qs = JornadaDiariaFalha.objects.none()
    elif request.GET.get('lider_id') or request.GET.get('manager_id'):
        m_id = request.GET.get('lider_id') or request.GET.get('manager_id')
        if str(m_id).isdigit():
            sel_l = Colaborador.objects.filter(id=m_id).first()
            if sel_l:
                base_counts_qs = base_counts_qs.filter(
                    Q(lider=sel_l) | Q(matricula_lider=sel_l.matricula) | Q(colaborador__lider=sel_l)
                )
        else:
            base_counts_qs = base_counts_qs.filter(
                Q(matricula_lider=m_id) | Q(nome_lider__icontains=m_id)
            )

    total_pendentes = base_counts_qs.filter(status_tratativa=StatusTratativa.PENDENTE).count()
    total_justificados = base_counts_qs.filter(status_tratativa=StatusTratativa.JUSTIFICADO).count()

    # Lista completa de Managers para o filtro
    managers = []
    seen_managers = set()

    relatorio_managers = JornadaDiariaFalha.objects.exclude(
        Q(lider__isnull=True) & Q(nome_lider__isnull=True) & Q(matricula_lider__isnull=True)
    ).values('lider_id', 'lider__nome_completo', 'matricula_lider', 'nome_lider').distinct()

    for rm in relatorio_managers:
        lid_id = rm['lider_id']
        nome = rm['lider__nome_completo'] or rm['nome_lider'] or 'Gestor'
        mat = rm['matricula_lider'] or ''
        key = lid_id if lid_id else (mat or nome)
        if key not in seen_managers:
            seen_managers.add(key)
            label = f"{nome} ({mat})" if mat else nome
            managers.append({'id': str(key), 'nome_completo': label})

    outros_lideres = Colaborador.objects.filter(
        is_active=True,
        posto_lideranca__in=['LIDER', 'SUPERVISOR', 'GERENTE']
    ).exclude(posto_lideranca='NAO_APLICA').order_by('nome_completo')

    for colab in outros_lideres:
        if colab.id not in seen_managers:
            seen_managers.add(colab.id)
            label = f"{colab.nome_completo} ({colab.matricula})" if colab.matricula else colab.nome_completo
            managers.append({'id': str(colab.id), 'nome_completo': label})

    managers.sort(key=lambda x: str(x['nome_completo']))


    # Agrupamento Hierárquico: Manager -> Colaboradores
    jornadas_list = list(jornadas)
    
    def get_lider_key(j):
        if j.lider:
            return (j.lider.id, j.lider.nome_completo, j.lider.matricula)
        elif j.nome_lider:
            return (0, j.nome_lider, j.matricula_lider or '')
        elif j.colaborador.lider:
            return (j.colaborador.lider.id, j.colaborador.lider.nome_completo, j.colaborador.lider.matricula)
        return (-1, 'Sem Gestor Definido', '')

    jornadas_list.sort(key=lambda j: (get_lider_key(j)[1], j.colaborador.nome_completo, j.data))

    managers_agrupados = []
    from itertools import groupby

    for lider_key, j_group in groupby(jornadas_list, key=get_lider_key):
        lider_id_val, lider_nome_val, lider_mat_val = lider_key
        lider_items = list(j_group)

        colabs_list = []
        lider_items.sort(key=lambda j: (j.colaborador.nome_completo, j.data))
        for colab_obj, colab_items in groupby(lider_items, key=lambda j: j.colaborador):
            items_list = list(colab_items)
            pendentes_c = sum(1 for i in items_list if i.status_tratativa == StatusTratativa.PENDENTE)
            colabs_list.append({
                'colaborador': colab_obj,
                'jornadas': items_list,
                'total_ocorrencias': len(items_list),
                'pendentes_count': pendentes_c
            })

        manager_pendentes = sum(c['pendentes_count'] for c in colabs_list)
        manager_total = sum(c['total_ocorrencias'] for c in colabs_list)

        managers_agrupados.append({
            'lider_nome': lider_nome_val,
            'lider_matricula': lider_mat_val,
            'colaboradores': colabs_list,
            'total_colaboradores': len(colabs_list),
            'pendentes_count': manager_pendentes,
            'total_ocorrencias': manager_total
        })

    context = {
        'demanda': demanda,
        'managers_agrupados': managers_agrupados,
        'jornadas': jornadas,
        'status_filtro': status_filtro,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'q_colab': q_colab,
        'status_choices': StatusTratativa.choices,
        'total_pendentes': total_pendentes,
        'total_justificados': total_justificados,
        'managers': managers,
        'lideres': managers
    }

    return render(request, 'rh/tratativa_falhas_ponto.html', context)






@login_required
@require_POST
def api_tratar_jornada(request, jornada_id):
    """
    API endpoint para o líder registrar a tratativa da jornada (status, justificativa, observacao).
    """
    jornada = get_object_or_404(JornadaDiariaFalha, pk=jornada_id)
    
    try:
        data = json.loads(request.body)
        novo_status = data.get('status_tratativa')
        justificativa = data.get('justificativa', '')
        obs_lider = data.get('observacao_lider', '')

        if novo_status not in StatusTratativa.values:
            return JsonResponse({'status': 'ERRO', 'mensagem': 'Status inválido.'}, status=400)

        jornada.status_tratativa = novo_status
        jornada.justificativa = justificativa
        jornada.observacao_lider = obs_lider
        jornada.tratado_por = request.user
        jornada.tratado_em = timezone.now()
        jornada.save()

        return JsonResponse({
            'status': 'SUCESSO',
            'mensagem': 'Tratativa salva com sucesso!',
            'status_display': jornada.get_status_tratativa_display(),
            'tratado_em': jornada.tratado_em.strftime('%d/%m/%Y %H:%M')
        })
    except Exception as e:
        logger.exception("Erro ao tratar jornada diária.")
        return JsonResponse({'status': 'ERRO', 'mensagem': str(e)}, status=400)
