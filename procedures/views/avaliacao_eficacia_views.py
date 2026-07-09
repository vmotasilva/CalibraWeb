# -*- coding: utf-8 -*-
from datetime import date, timedelta
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from collections import defaultdict
from procedures.models import RegistroTreinamento, ColaboradorPerfil, MatrizProcedimento
from rh.models import Colaborador
from organization.models import Setor

@login_required
def avaliacao_eficacia_list_view(request):
    """
    Lista os treinamentos de procedimentos críticos para controle da autoavaliação de eficácia (a partir de 30 dias).
    """
    # Filtrar apenas registros que possuem colaborador e procedimento,
    # onde o procedimento é crítico, o treinamento já ocorreu (data_treinamento is not null),
    # o colaborador está ativo e o registro de treinamento está ativo.
    qs = RegistroTreinamento.objects.select_related('colaborador', 'procedimento', 'colaborador__setor', 'colaborador__lider').filter(
        colaborador__isnull=False,
        procedimento__isnull=False,
        procedimento__criticidade='CRITICO',
        data_treinamento__isnull=False,
        ativo=True,
        colaborador__is_active=True,
        colaborador__afastado=False,
        colaborador__em_ferias=False,
    )

    # Obter dados para os filtros
    setores = Setor.objects.order_by('nome')
    lideres = Colaborador.objects.filter(
        is_active=True,
        id__in=Colaborador.objects.values_list('lider_id', flat=True).distinct()
    ).order_by('nome_completo')
    matrizes_opcoes = MatrizProcedimento.objects.filter(ativo=True).order_by('nome')

    # Parâmetros de filtro
    busca = (request.GET.get('q') or '').strip()
    status_filtro = (request.GET.get('status') or '').strip()
    lider_id = (request.GET.get('lider') or '').strip()
    setor_id = (request.GET.get('setor') or '').strip()
    dias_decorridos_filtro = (request.GET.get('dias_decorridos') or '').strip()
    vinculo_filtro = (request.GET.get('vinculo') or '').strip()
    posterior_filtro = (request.GET.get('posterior') or '').strip()
    matriz_filtro = (request.GET.get('matriz') or '').strip()

    # Filtro especial por dias decorridos (antes de filtrar status)
    today = date.today()
    carencia_date = today - timedelta(days=30)

    # Aplicar filtros no banco
    if busca:
        qs = qs.filter(
            Q(colaborador__nome_completo__icontains=busca) |
            Q(procedimento__codigo__icontains=busca) |
            Q(procedimento__nome__icontains=busca)
        )
    if lider_id:
        qs = qs.filter(colaborador__lider_id=lider_id)
    if setor_id:
        qs = qs.filter(colaborador__setor_id=setor_id)
    if matriz_filtro:
        qs = qs.filter(procedimento__matriz__iexact=matriz_filtro)

    if dias_decorridos_filtro:
        if dias_decorridos_filtro == 'menos_30':
            qs = qs.filter(data_treinamento__gt=carencia_date)
        elif dias_decorridos_filtro == '30_60':
            qs = qs.filter(data_treinamento__lte=carencia_date, data_treinamento__gte=today - timedelta(days=60))
        elif dias_decorridos_filtro == '60_90':
            qs = qs.filter(data_treinamento__lt=today - timedelta(days=60), data_treinamento__gte=today - timedelta(days=90))
        elif dias_decorridos_filtro == '90_mais':
            qs = qs.filter(data_treinamento__lt=today - timedelta(days=90))

    if status_filtro:
        if status_filtro == 'EFICAZ':
            qs = qs.filter(avaliacao_eficacia_status='EFICAZ')
        elif status_filtro == 'INEFICAZ':
            qs = qs.filter(avaliacao_eficacia_status='INEFICAZ')
        elif status_filtro == 'NAO_APLICA':
            qs = qs.filter(avaliacao_eficacia_status='NAO_APLICA')
        elif status_filtro == 'CARENCIA':
            # PENDENTE mas com menos de 30 dias desde o treinamento
            qs = qs.filter(
                Q(avaliacao_eficacia_status='PENDENTE') | Q(avaliacao_eficacia_status__isnull=True),
                data_treinamento__gt=carencia_date
            )
        elif status_filtro == 'PENDENTE':
            # PENDENTE e com 30 dias ou mais desde o treinamento
            qs = qs.filter(
                Q(avaliacao_eficacia_status='PENDENTE') | Q(avaliacao_eficacia_status__isnull=True),
                data_treinamento__lte=carencia_date
            )

    # Ordenação padrão: por data do treinamento decrescente
    qs = qs.order_by('-data_treinamento', 'colaborador__nome_completo')

    # Calcular totais para os cards do dashboard
    # Precisamos da query com filtros de busca, lider, setor e dias (mas sem filtro de status) para os totais locais
    totals_qs = RegistroTreinamento.objects.filter(
        colaborador__isnull=False,
        procedimento__isnull=False,
        procedimento__criticidade='CRITICO',
        data_treinamento__isnull=False,
        ativo=True,
        colaborador__is_active=True,
        colaborador__afastado=False,
        colaborador__em_ferias=False,
    )
    if busca:
        totals_qs = totals_qs.filter(
            Q(colaborador__nome_completo__icontains=busca) |
            Q(procedimento__codigo__icontains=busca) |
            Q(procedimento__nome__icontains=busca)
        )
    if lider_id:
        totals_qs = totals_qs.filter(colaborador__lider_id=lider_id)
    if setor_id:
        totals_qs = totals_qs.filter(colaborador__setor_id=setor_id)
    if matriz_filtro:
        totals_qs = totals_qs.filter(procedimento__matriz__iexact=matriz_filtro)
    if dias_decorridos_filtro:
        if dias_decorridos_filtro == 'menos_30':
            totals_qs = totals_qs.filter(data_treinamento__gt=carencia_date)
        elif dias_decorridos_filtro == '30_60':
            totals_qs = totals_qs.filter(data_treinamento__lte=carencia_date, data_treinamento__gte=today - timedelta(days=60))
        elif dias_decorridos_filtro == '60_90':
            totals_qs = totals_qs.filter(data_treinamento__lt=today - timedelta(days=60), data_treinamento__gte=today - timedelta(days=90))
        elif dias_decorridos_filtro == '90_mais':
            totals_qs = totals_qs.filter(data_treinamento__lt=today - timedelta(days=90))

    # Obter todos os registros de treinamentos críticos ativos para calcular se há posterior em aberto
    all_critical = list(RegistroTreinamento.objects.filter(
        colaborador__isnull=False,
        procedimento__isnull=False,
        procedimento__criticidade='CRITICO',
        data_treinamento__isnull=False,
        ativo=True,
    ))

    # Group by (colaborador_id, procedimento_id)
    grouped = defaultdict(list)
    for t in all_critical:
        grouped[(t.colaborador_id, t.procedimento_id)].append(t)

    # Sort each group by data_treinamento ascending
    for key in grouped:
        grouped[key].sort(key=lambda x: x.data_treinamento)

    # Find which ones have a posterior training with status PENDENTE / None
    posterior_pending_ids = set()
    for key, group in grouped.items():
        n = len(group)
        for i in range(n):
            t = group[i]
            has_posterior = False
            for j in range(i + 1, n):
                t2 = group[j]
                if t2.avaliacao_eficacia_status in ['PENDENTE', None, '']:
                    has_posterior = True
                    break
            if has_posterior:
                posterior_pending_ids.add(t.id)

    # Mapeamento do vínculo de perfil dos colaboradores
    colab_procs_map = defaultdict(set)
    for cp in ColaboradorPerfil.objects.filter(ativo=True):
        proc_ids = cp.get_procedimentos_necessarios().values_list('id', flat=True)
        colab_procs_map[cp.colaborador_id].update(proc_ids)

    # Filtrar e anotar no python (vínculo de perfil e posterior pendente)
    registros_list = list(qs)
    for t in registros_list:
        t.tem_vinculo_perfil = t.procedimento_id in colab_procs_map[t.colaborador_id]
        t.has_posterior_pending = t.id in posterior_pending_ids

    if vinculo_filtro == 'COM_VINCULO':
        registros_list = [t for t in registros_list if t.tem_vinculo_perfil]
    elif vinculo_filtro == 'SEM_VINCULO':
        registros_list = [t for t in registros_list if not t.tem_vinculo_perfil]

    if posterior_filtro == 'COM_POSTERIOR':
        registros_list = [t for t in registros_list if t.has_posterior_pending]
    elif posterior_filtro == 'SEM_POSTERIOR':
        registros_list = [t for t in registros_list if not t.has_posterior_pending]

    totals_list = list(totals_qs)
    for t in totals_list:
        t.tem_vinculo_perfil = t.procedimento_id in colab_procs_map[t.colaborador_id]
        t.has_posterior_pending = t.id in posterior_pending_ids

    if vinculo_filtro == 'COM_VINCULO':
        totals_list = [t for t in totals_list if t.tem_vinculo_perfil]
    elif vinculo_filtro == 'SEM_VINCULO':
        totals_list = [t for t in totals_list if not t.tem_vinculo_perfil]

    if posterior_filtro == 'COM_POSTERIOR':
        totals_list = [t for t in totals_list if t.has_posterior_pending]
    elif posterior_filtro == 'SEM_POSTERIOR':
        totals_list = [t for t in totals_list if not t.has_posterior_pending]

    total_geral = len(totals_list)
    total_eficaz = sum(1 for t in totals_list if t.avaliacao_eficacia_status == 'EFICAZ')
    total_ineficaz = sum(1 for t in totals_list if t.avaliacao_eficacia_status == 'INEFICAZ')
    total_nao_aplica = sum(1 for t in totals_list if t.avaliacao_eficacia_status == 'NAO_APLICA')
    total_carencia = sum(1 for t in totals_list if (t.avaliacao_eficacia_status in ['PENDENTE', None, '']) and (today - t.data_treinamento).days < 30)
    total_pendente = sum(1 for t in totals_list if (t.avaliacao_eficacia_status in ['PENDENTE', None, '']) and (today - t.data_treinamento).days >= 30)

    # Paginação
    paginator = Paginator(registros_list, 30)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # Processar cada objeto na página para adicionar informações calculadas
    for t in page_obj.object_list:
        t.data_elegibilidade = t.data_treinamento + timedelta(days=30)
        dias_dec = (today - t.data_treinamento).days
        t.dias_decorridos = dias_dec
        t.dias_restantes = max(0, 30 - dias_dec)
        
        # Determinar status para exibição
        if t.avaliacao_eficacia_status == 'EFICAZ':
            t.status_display = 'Eficaz'
            t.status_class = 'success'
        elif t.avaliacao_eficacia_status == 'INEFICAZ':
            t.status_display = 'Ineficaz'
            t.status_class = 'danger'
        elif t.avaliacao_eficacia_status == 'NAO_APLICA':
            t.status_display = 'Não se Aplica'
            t.status_class = 'secondary'
        else:
            if dias_dec < 30:
                t.status_display = 'Carência'
                t.status_class = 'info'
            else:
                t.status_display = 'Pendente'
                t.status_class = 'warning'

    # Manter a query string dos filtros para paginação
    query_params = request.GET.copy()
    if 'page' in query_params:
        del query_params['page']
    query_string = query_params.urlencode()

    context = {
        'page_obj': page_obj,
        'setores': setores,
        'lideres': lideres,
        'matrizes_opcoes': matrizes_opcoes,
        'busca': busca,
        'status_filtro': status_filtro,
        'lider_id': lider_id,
        'setor_id': setor_id,
        'dias_decorridos_filtro': dias_decorridos_filtro,
        'vinculo_filtro': vinculo_filtro,
        'posterior_filtro': posterior_filtro,
        'matriz_filtro': matriz_filtro,
        'query_string': query_string,
        # Totais
        'total_geral': total_geral,
        'total_eficaz': total_eficaz,
        'total_ineficaz': total_ineficaz,
        'total_nao_aplica': total_nao_aplica,
        'total_carencia': total_carencia,
        'total_pendente': total_pendente,
        'today': today,
    }
    return render(request, "procedures/avaliacao_eficacia_lista.html", context)

@require_POST
@login_required
def avaliacao_eficacia_registrar_view(request, treinamento_id):
    """
    Grava ou atualiza os dados da autoavaliação de eficácia.
    """
    treinamento = get_object_or_404(RegistroTreinamento, id=treinamento_id)
    
    # Validar se o procedimento associado é crítico
    if not treinamento.procedimento or treinamento.procedimento.criticidade != 'CRITICO':
        messages.error(request, "Este treinamento não requer Avaliação de Eficácia.")
        return redirect("procedures:avaliacao_eficacia_list")

    # Obter dados do formulário
    status = request.POST.get('status')
    data_avaliacao_str = request.POST.get('data_avaliacao')
    resultado_avaliacao = request.POST.get('resultado_avaliacao', '').strip()

    # Validações básicas
    if status not in ['EFICAZ', 'INEFICAZ', 'NAO_APLICA']:
        messages.error(request, "Status inválido selecionado.")
        return redirect("procedures:avaliacao_eficacia_list")

    if status == 'NAO_APLICA' and not resultado_avaliacao:
        messages.error(request, "A justificativa é obrigatória para a opção 'Não se Aplica'.")
        return redirect("procedures:avaliacao_eficacia_list")

    if not data_avaliacao_str:
        messages.error(request, "A data da avaliação é obrigatória.")
        return redirect("procedures:avaliacao_eficacia_list")

    from datetime import datetime
    try:
        data_avaliacao = datetime.strptime(data_avaliacao_str, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, "Formato de data inválido.")
        return redirect("procedures:avaliacao_eficacia_list")

    # Salvar avaliação no registro do treinamento
    treinamento.avaliacao_eficacia_status = status
    treinamento.avaliacao_eficacia_data = data_avaliacao
    treinamento.resultado_avaliacao = resultado_avaliacao
    treinamento.save()

    messages.success(request, f"Avaliação de eficácia registrada com sucesso para {treinamento.colaborador.nome_completo}.")
    return redirect("procedures:avaliacao_eficacia_list")

@require_POST
@login_required
def avaliacao_eficacia_registrar_massa_view(request):
    """
    Registra avaliação de eficácia em massa para vários treinamentos selecionados.
    """
    treinamento_ids = request.POST.getlist('treinamento_ids')
    if not treinamento_ids:
        messages.warning(request, "Nenhum treinamento selecionado para avaliação em massa.")
        return redirect("procedures:avaliacao_eficacia_list")

    status = request.POST.get('status')
    data_avaliacao_str = request.POST.get('data_avaliacao')
    resultado_avaliacao = request.POST.get('resultado_avaliacao', '').strip()

    # Validações básicas
    if status not in ['EFICAZ', 'INEFICAZ', 'NAO_APLICA']:
        messages.error(request, "Status de eficácia inválido.")
        return redirect("procedures:avaliacao_eficacia_list")

    if status == 'NAO_APLICA' and not resultado_avaliacao:
        messages.error(request, "A justificativa é obrigatória para a opção 'Não se Aplica'.")
        return redirect("procedures:avaliacao_eficacia_list")

    if not data_avaliacao_str:
        messages.error(request, "A data da avaliação é obrigatória.")
        return redirect("procedures:avaliacao_eficacia_list")

    from datetime import datetime
    try:
        data_avaliacao = datetime.strptime(data_avaliacao_str, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, "Formato de data inválido.")
        return redirect("procedures:avaliacao_eficacia_list")

    # Filtrar os treinamentos que de fato necessitam e não estão em carência
    today = date.today()
    carencia_date = today - timedelta(days=30)
    
    treinamentos = RegistroTreinamento.objects.filter(
        id__in=treinamento_ids,
        procedimento__criticidade='CRITICO',
        data_treinamento__isnull=False,
        ativo=True,
    ).filter(
        # Apenas os elegíveis (data_treinamento + 30 <= hoje)
        data_treinamento__lte=carencia_date
    )

    count = 0
    if treinamentos.exists():
        from django.db import transaction
        with transaction.atomic():
            for t in treinamentos:
                t.avaliacao_eficacia_status = status
                t.avaliacao_eficacia_data = data_avaliacao
                t.resultado_avaliacao = resultado_avaliacao
                t.save()
                count += 1

    messages.success(request, f"Avaliação em massa concluída! {count} treinamento(s) atualizado(s) com sucesso.")
    return redirect("procedures:avaliacao_eficacia_list")
