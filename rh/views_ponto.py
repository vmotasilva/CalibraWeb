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
                    de_para_map[reg_planilha] = colab
                    continue

            # Caso 2: Matrícula da planilha é exatamente a matrícula ou matrícula global cadastrada no banco
            colab_direto = Colaborador.objects.filter(
                Q(matricula=reg_planilha) | Q(matricula_global=reg_planilha)
            ).first()
            if colab_direto:
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

                    def get_batida(field_name):
                        val = first_row.get(field_name)
                        if pd.notna(val) and str(val).strip() != '' and str(val).strip() != 'nan':
                            return str(val).strip()[:10]
                        return None

                    jornada, _ = JornadaDiariaFalha.objects.update_or_create(
                        colaborador=colaborador,
                        data=data_obj,
                        defaults={
                            'jornada_prevista': str(first_row.get('Jornada', '')) if pd.notna(first_row.get('Jornada')) else None,
                            'e1': get_batida('E1'),
                            's1': get_batida('S1'),
                            'e2': get_batida('E2'),
                            's2': get_batida('S2'),
                            'e3': get_batida('E3'),
                            's3': get_batida('S3'),
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
            'mensagem': f'Importação realizada com sucesso! {jornadas_processadas} jornadas diárias registradas/atualizadas.'
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
                    salvos += 1

        return JsonResponse({
            'status': 'SUCESSO',
            'mensagem': f'{salvos} vínculo(s) de matrícula salvo(s) com sucesso!'
        })
    except Exception as e:
        logger.exception("Erro ao salvar mapeamento de matrícula.")
        return JsonResponse({'status': 'ERRO', 'mensagem': str(e)}, status=400)


@login_required
def tratativa_falhas_ponto_view(request):
    """
    Tela principal de tratativa das falhas de batida de ponto para Líderes/Supervisores/Gerentes.
    Exibe os dados agrupados por Dia e Colaborador da equipe do usuário logado.
    """
    user = request.user
    status_filtro = request.GET.get('status', StatusTratativa.PENDENTE)
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    # Identificar perfil de colaborador do usuário logado
    colaborador_logado = get_colaborador_for_user(user)

    qs = JornadaDiariaFalha.objects.all()

    # Se não for superusuario/staff sem equipe, restringe aos liderados
    if not (user.is_superuser or user.is_staff):
        if not colaborador_logado:
            qs = JornadaDiariaFalha.objects.none()
        else:
            equipe_ids = Colaborador.objects.filter(
                Q(lider=colaborador_logado) |
                Q(supervisor=colaborador_logado) |
                Q(gerente=colaborador_logado) |
                Q(pk=colaborador_logado.pk)
            ).values_list('id', flat=True)
            qs = qs.filter(colaborador_id__in=equipe_ids)
    else:
        # Se for superuser/staff com filtro por líder específico no GET
        lider_id = request.GET.get('lider_id')
        if lider_id:
            equipe_ids = Colaborador.objects.filter(
                Q(lider_id=lider_id) | Q(supervisor_id=lider_id) | Q(gerente_id=lider_id)
            ).values_list('id', flat=True)
            qs = qs.filter(colaborador_id__in=equipe_ids)

    if status_filtro and status_filtro != 'TODOS':
        qs = qs.filter(status_tratativa=status_filtro)

    if data_inicio:
        qs = qs.filter(data__gte=data_inicio)
    if data_fim:
        qs = qs.filter(data__lte=data_fim)

    jornadas = qs.select_related(
        'colaborador',
        'colaborador__setor',
        'tratado_por'
    ).prefetch_related('erros').order_by('-data', 'colaborador__nome_completo')

    # Contadores para os cards do dashboard
    total_pendentes = JornadaDiariaFalha.objects.filter(status_tratativa=StatusTratativa.PENDENTE).count()
    total_justificados = JornadaDiariaFalha.objects.filter(status_tratativa=StatusTratativa.JUSTIFICADO).count()

    context = {
        'jornadas': jornadas,
        'status_filtro': status_filtro,
        'status_choices': StatusTratativa.choices,
        'total_pendentes': total_pendentes,
        'total_justificados': total_justificados,
        'lideres': Colaborador.objects.filter(is_active=True).order_by('nome_completo') if user.is_superuser else []
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
