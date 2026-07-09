# -*- coding: utf-8 -*-
from datetime import date, timedelta
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from procedures.models import RegistroTreinamento
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

    # Parâmetros de filtro
    busca = (request.GET.get('q') or '').strip()
    status_filtro = (request.GET.get('status') or '').strip()
    lider_id = (request.GET.get('lider') or '').strip()
    setor_id = (request.GET.get('setor') or '').strip()

    # Aplicar filtros
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

    # Filtro especial por status da autoavaliação
    # Como as datas são calculadas dinamicamente:
    # carencia_threshold é a data máxima que indica "menos de 30 dias"
    today = date.today()
    carencia_date = today - timedelta(days=30)

    if status_filtro:
        if status_filtro == 'EFICAZ':
            qs = qs.filter(avaliacao_eficacia_status='EFICAZ')
        elif status_filtro == 'INEFICAZ':
            qs = qs.filter(avaliacao_eficacia_status='INEFICAZ')
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
    # Precisamos da query principal (com filtros de busca, lider, setor, mas sem filtro de status) para os totais locais
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

    total_geral = totals_qs.count()
    total_eficaz = totals_qs.filter(avaliacao_eficacia_status='EFICAZ').count()
    total_ineficaz = totals_qs.filter(avaliacao_eficacia_status='INEFICAZ').count()
    total_carencia = totals_qs.filter(
        Q(avaliacao_eficacia_status='PENDENTE') | Q(avaliacao_eficacia_status__isnull=True),
        data_treinamento__gt=carencia_date
    ).count()
    total_pendente = totals_qs.filter(
        Q(avaliacao_eficacia_status='PENDENTE') | Q(avaliacao_eficacia_status__isnull=True),
        data_treinamento__lte=carencia_date
    ).count()

    # Paginação
    paginator = Paginator(qs, 30)
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
        'busca': busca,
        'status_filtro': status_filtro,
        'lider_id': lider_id,
        'setor_id': setor_id,
        'query_string': query_string,
        # Totais
        'total_geral': total_geral,
        'total_eficaz': total_eficaz,
        'total_ineficaz': total_ineficaz,
        'total_carencia': total_carencia,
        'total_pendente': total_pendente,
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
    if status not in ['EFICAZ', 'INEFICAZ']:
        messages.error(request, "Status inválido selecionado.")
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
