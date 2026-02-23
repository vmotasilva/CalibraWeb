# -*- coding: utf-8 -*-
"""
Views para o módulo Training (Treinamentos e Procedimentos)
"""

import io
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Q
from django.core.paginator import Paginator
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# Imports dos models
from procedures.models import Procedimento, RegistroTreinamento, PacoteTreinamento
from rh.models import Colaborador

# Imports dos forms
from training.forms import ProcedimentoForm, RegistroTreinamentoForm

# Imports dos helpers
from qms.views_helpers import export_to_excel_response, can_manage_procedimentos


@login_required
def procedimentos_list_view(request):
    """Lista de Procedimentos com filtros avançados."""
    termo = (request.GET.get('q') or '').strip().upper()
    classificacao = (request.GET.get('classificacao') or '').strip().upper()
    setor_id = request.GET.get('setor')
    area_id = request.GET.get('area')
    rev = (request.GET.get('rev') or '').strip()
    elaborador_id = request.GET.get('elaborador')
    revisor_id = request.GET.get('revisor')
    aprovador_id = request.GET.get('aprovador')

    qs = Procedimento.objects.all()
    if termo:
        qs = qs.filter(Q(codigo__icontains=termo) | Q(nome__icontains=termo))
    if classificacao:
        qs = qs.filter(classificacao__iexact=classificacao)
    if setor_id and setor_id.isdigit():
        qs = qs.filter(pasta__icontains=setor_id)
    if area_id and area_id.isdigit():
        qs = qs.filter(sub_area__icontains=area_id)
    if rev:
        qs = qs.filter(numero_revisao__iexact=rev)

    page_number = request.GET.get('page','1')
    paginator = Paginator(qs.order_by('codigo'), 50)
    page_obj = paginator.get_page(page_number)
    procedimentos = page_obj.object_list

    ctx = {
        'procedimentos': procedimentos,
        'termo': termo,
        'classificacao': classificacao,
        'page_obj': page_obj,
        'paginator': paginator,
        'rev': rev,
        'setor_id': setor_id,
        'area_id': area_id,
        'querystring_base': '&'.join([p for p in [
            f"q={termo}" if termo else '',
            f"classificacao={classificacao}" if classificacao else '',
            f"setor={setor_id}" if setor_id else '',
            f"area={area_id}" if area_id else '',
            f"rev={rev}" if rev else '',
        ] if p])
    }
    return render(request, 'training/procedimento_lista.html', ctx)


@login_required
def export_procedimentos_excel_view(request):
    """Exporta procedimentos para Excel respeitando filtros."""
    termo = (request.GET.get('q') or '').strip().upper()
    classificacao = (request.GET.get('classificacao') or '').strip().upper()
    setor_id = request.GET.get('setor')
    area_id = request.GET.get('area')
    rev = (request.GET.get('rev') or '').strip()
    
    qs = Procedimento.objects.all()
    if termo:
        qs = qs.filter(Q(codigo__icontains=termo) | Q(nome__icontains=termo))
    if classificacao:
        qs = qs.filter(classificacao__iexact=classificacao)
    if setor_id and setor_id.isdigit():
        qs = qs.filter(pasta__icontains=setor_id)
    if area_id and area_id.isdigit():
        qs = qs.filter(sub_area__icontains=area_id)
    if rev:
        qs = qs.filter(numero_revisao__iexact=rev)
    
    rows = []
    for p in qs.order_by('codigo'):
        rows.append({
            'CODIGO': p.codigo,
            'NOME': p.nome,
            'CLASSIFICACAO': p.classificacao,
            'NUMERO_REVISAO': p.numero_revisao,
            'ULTIMA_REVISAO': p.ultima_revisao.strftime('%Y-%m-%d') if p.ultima_revisao else '',
            'DATA_APROVACAO': p.data_aprovacao.strftime('%Y-%m-%d') if p.data_aprovacao else '',
            'PROXIMA_REVISAO': p.proxima_revisao.strftime('%Y-%m-%d') if p.proxima_revisao else '',
            'DATA_VALIDADE': p.data_validade.strftime('%Y-%m-%d') if p.data_validade else '',
            'PASTA': p.pasta,
            'AUTOR': p.autor,
            'DOCUMENTOS_CONTROLADOS': p.documentos_controlados,
            'MATRIZ': p.matriz,
            'SUB_AREA': p.sub_area,
        })
    
    return export_to_excel_response(rows, "procedimentos_export.xlsx")


@login_required
def export_procedimentos_pdf_view(request):
    """Exporta procedimentos em PDF tabular."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    
    termo = (request.GET.get('q') or '').strip().upper()
    classificacao = (request.GET.get('classificacao') or '').strip().upper()
    
    qs = Procedimento.objects.all()
    if termo:
        qs = qs.filter(Q(codigo__icontains=termo) | Q(nome__icontains=termo))
    if classificacao:
        qs = qs.filter(classificacao__iexact=classificacao)
    
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    y = h - 40
    c.setFont('Helvetica-Bold', 14)
    c.drawString(40, y, 'Relatório de Procedimentos')
    y -= 25
    c.setFont('Helvetica', 8)
    headers = ['Código','Nome','Classificação','Número Revisão','Última Revisão','Data Aprovação','Próxima Revisão','Data Validade','Pasta','Autor','Documentos Controlados','Matriz','Sub-Área']
    c.drawString(40, y, ' | '.join(headers))
    y -= 12
    c.setFont('Helvetica', 7)
    for p in qs.order_by('codigo'):
        line = [
            str(p.codigo or ''),
            (p.nome[:40] + ('...' if p.nome and len(p.nome)>40 else '')) if p.nome else '',
            str(p.classificacao or ''),
            str(p.numero_revisao or ''),
            p.ultima_revisao.strftime('%d/%m/%Y') if p.ultima_revisao else '',
            p.data_aprovacao.strftime('%d/%m/%Y') if p.data_aprovacao else '',
            p.proxima_revisao.strftime('%d/%m/%Y') if p.proxima_revisao else '',
            p.data_validade.strftime('%d/%m/%Y') if p.data_validade else '',
            str(p.pasta or ''),
            str(p.autor or ''),
            str(p.documentos_controlados or ''),
            str(p.matriz or ''),
            str(p.sub_area or ''),
        ]
        c.drawString(40, y, ' | '.join(line))
        y -= 10
        if y < 50:
            c.showPage()
            y = h - 50
            c.setFont('Helvetica', 7)
    c.showPage()
    c.save()
    buf.seek(0)
    r = HttpResponse(buf, content_type='application/pdf')
    r['Content-Disposition'] = 'attachment; filename="procedimentos.pdf"'
    return r


@login_required
def novo_procedimento_view(request):
    """Cria novo procedimento."""
    if not can_manage_procedimentos(request.user):
        messages.error(request, 'Sem permissão para criar procedimentos.')
        return redirect('procedimentos_list')
    
    if request.method == 'POST':
        form = ProcedimentoForm(request.POST, request.FILES)
        if form.is_valid():
            proc = form.save()
            messages.success(request, f"Procedimento {proc.codigo} criado com sucesso!")
            return redirect('procedimentos_list')
    else:
        form = ProcedimentoForm()
    
    return render(request, 'shared/form_generico.html', {
        'form': form,
        'titulo': 'Novo Procedimento'
    })


@login_required
def editar_procedimento_view(request, procedimento_id):
    """Edita um procedimento existente."""
    proc = get_object_or_404(Procedimento, id=procedimento_id)
    
    if not can_manage_procedimentos(request.user):
        messages.error(request, 'Sem permissão para editar procedimentos.')
        return redirect('detalhe_procedimento', procedimento_id=proc.id)
    
    if request.method == 'POST':
        form = ProcedimentoForm(request.POST, request.FILES, instance=proc)
        if form.is_valid():
            form.save()
            messages.success(request, "Procedimento atualizado com sucesso!")
            return redirect('detalhe_procedimento', procedimento_id=proc.id)
    else:
        form = ProcedimentoForm(instance=proc)
    
    return render(request, 'shared/form_generico.html', {
        'form': form,
        'titulo': f'Editar {proc.codigo}'
    })


@login_required
def detalhe_procedimento_view(request, procedimento_id):
    """Visualiza detalhes de um procedimento."""
    proc = get_object_or_404(Procedimento, id=procedimento_id)
    return render(request, 'training/procedimento_detalhe.html', {
        'proc': proc
    })


@login_required
def treinamentos_list_view(request):
    """Lista de treinamentos realizados com filtros avançados."""
    from django.db.models import Q
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    
    qs = RegistroTreinamento.objects.select_related('colaborador', 'procedimento').all()
    colaboradores = Colaborador.objects.order_by('nome_completo').distinct()
    procedimentos = Procedimento.objects.order_by('codigo').distinct()
    
    status = request.GET.get('status', '').strip()
    colaborador_id = request.GET.get('colaborador', '').strip()
    procedimento_id = request.GET.get('procedimento', '').strip()
    busca = request.GET.get('q', '').strip()
    
    # Limpar valores inválidos
    if busca == 'None' or not busca:
        busca = ''
    if status == 'None' or not status:
        status = ''
    if colaborador_id == 'None' or not colaborador_id:
        colaborador_id = ''
    if procedimento_id == 'None' or not procedimento_id:
        procedimento_id = ''
    
    # Filtro por colaborador - converter para int se fornecido
    if colaborador_id and colaborador_id.isdigit():
        qs = qs.filter(colaborador_id=int(colaborador_id))
    
    # Filtro por procedimento - converter para int se fornecido
    if procedimento_id and procedimento_id.isdigit():
        qs = qs.filter(procedimento_id=int(procedimento_id))
    
    # Filtro de busca por texto
    if busca:
        qs = qs.filter(
            Q(colaborador__nome_completo__icontains=busca) |
            Q(procedimento__codigo__icontains=busca) |
            Q(procedimento__nome__icontains=busca)
        )
    
    # Ordenar resultados antes de filtrar por status
    qs = qs.order_by('-data_treinamento')
    
    # Filtro por status - filtrando em Python (é uma property, não field direto)
    if status:
        all_records = list(qs)
        qs = [t for t in all_records if t.status_treinamento == status]
    
    # Paginar resultados (15 por página)
    paginator = Paginator(qs, 15)
    page = request.GET.get('page')
    
    try:
        treinamentos = paginator.page(page)
    except PageNotAnInteger:
        treinamentos = paginator.page(1)
    except EmptyPage:
        treinamentos = paginator.page(paginator.num_pages)
    
    return render(request, "training/treinamento_lista.html", {
        "treinamentos": treinamentos,
        "colaboradores": colaboradores,
        "procedimentos": procedimentos,
        "status": status,
        "colaborador_id": colaborador_id,
        "procedimento_id": procedimento_id,
        "busca": busca,
    })


# ==============================================================================
# ADDITIONAL TRAINING RECORD VIEWS
# ==============================================================================

@login_required
def treinamentos_detalhe_view(request, treinamento_id):
    """View detalhes de um registro de treinamento."""
    from training.models import RegistroTreinamento
    
    treinamento = get_object_or_404(RegistroTreinamento, id=treinamento_id)
    return render(request, "training/treinamento_detalhe.html", {
        "treinamento": treinamento
    })


@login_required
def novo_treinamento_view(request):
    """Criar novo registro de treinamento."""
    from training.models import RegistroTreinamento
    from training.forms import RegistroTreinamentoForm
    
    if request.method == "POST":
        form = RegistroTreinamentoForm(request.POST)
        if form.is_valid():
            treinamento = form.save()
            messages.success(request, "Treinamento registrado com sucesso.")
            return redirect("treinamentos_lista")
    else:
        form = RegistroTreinamentoForm()
    
    return render(request, "training/treinamento_form.html", {
        "form": form
    })


@login_required
def editar_treinamento_view(request, treinamento_id):
    """Editar registro de treinamento existente."""
    from training.models import RegistroTreinamento
    from training.forms import RegistroTreinamentoForm
    
    treinamento = get_object_or_404(RegistroTreinamento, id=treinamento_id)
    if request.method == "POST":
        form = RegistroTreinamentoForm(request.POST, instance=treinamento)
        if form.is_valid():
            form.save()
            messages.success(request, "Treinamento atualizado.")
            return redirect("treinamentos_lista")
    else:
        form = RegistroTreinamentoForm(instance=treinamento)
    
    return render(request, "training/treinamento_form.html", {
        "form": form
    })

# ==============================================================================
# DASHBOARD DE TREINAMENTOS
# ==============================================================================

@login_required
@login_required
def dashboard_treinamentos_view(request):
    """Dashboard completo de treinamentos com estatísticas e gráficos - OTIMIZADO"""
    from django.db.models import Count, Q, Exists, OuterRef, Prefetch, F
    from datetime import timedelta, date
    from core.models import TURNOS_CHOICES
    from django.core.cache import cache
    from procedures.models import PlanejamentoTreinamento, Procedimento
    from organization.models import Setor
    
    # Capturar filtros da URL (suportar múltiplos valores)
    filtro_setor_list = request.GET.getlist('setor')
    filtro_turno_list = request.GET.getlist('turno')
    filtro_lider_list = request.GET.getlist('lider')
    filtro_criticidade_list = request.GET.getlist('criticidade')
    filtro_matriz_list = request.GET.getlist('matriz')
    filtro_sub_area_list = request.GET.getlist('sub_area')
    
    # Para template (primeiro valor ou vazio)
    filtro_setor = filtro_setor_list[0] if filtro_setor_list else ''
    filtro_turno = filtro_turno_list[0] if filtro_turno_list else ''
    filtro_lider = filtro_lider_list[0] if filtro_lider_list else ''
    filtro_criticidade = filtro_criticidade_list[0] if filtro_criticidade_list else ''
    filtro_matriz = filtro_matriz_list[0] if filtro_matriz_list else ''
    filtro_sub_area = filtro_sub_area_list[0] if filtro_sub_area_list else ''
    
    # Se há filtros, não usar cache
    has_filters = (
        filtro_setor_list
        or filtro_turno_list
        or filtro_lider_list
        or filtro_criticidade_list
        or filtro_matriz_list
        or filtro_sub_area_list
    )
    
    # Cache key para estatísticas do dashboard (apenas sem filtros)
    cache_key = 'dashboard_treinamentos_stats'
    if not has_filters:
        cached_data = cache.get(cache_key)
        if cached_data:
            # Adicionar dados de filtros ao cache
            cached_data['filtro_setor'] = filtro_setor
            cached_data['filtro_turno'] = filtro_turno
            cached_data['filtro_lider'] = filtro_lider
            cached_data['filtro_criticidade'] = filtro_criticidade
            cached_data['filtro_matriz'] = filtro_matriz
            cached_data['filtro_sub_area'] = filtro_sub_area
            return render(request, 'training/dashboard_treinamentos.html', cached_data)
    
    # Base query: apenas registros com colaborador ATIVO, NÃO AFASTADO, NÃO EM FÉRIAS e procedimento vinculado
    valid_registros = RegistroTreinamento.objects.filter(
        colaborador__isnull=False,
        colaborador__is_active=True,
        colaborador__afastado=False,
        colaborador__em_ferias=False,
        procedimento__isnull=False,
        ativo=True
    ).select_related('colaborador', 'procedimento')
    
    # Aplicar filtros
    if filtro_setor_list:
        valid_registros = valid_registros.filter(colaborador__setor_id__in=filtro_setor_list)
    
    if filtro_turno_list:
        valid_registros = valid_registros.filter(colaborador__turno__in=filtro_turno_list)
    
    if filtro_lider_list:
        valid_registros = valid_registros.filter(colaborador__lider_id__in=filtro_lider_list)

    if filtro_criticidade_list:
        valid_registros = valid_registros.filter(procedimento__criticidade__in=filtro_criticidade_list)

    if filtro_matriz_list:
        valid_registros = valid_registros.filter(procedimento__matriz__in=filtro_matriz_list)

    if filtro_sub_area_list:
        valid_registros = valid_registros.filter(procedimento__sub_area__in=filtro_sub_area_list)
    
    # =========================================================================
    # REGISTROS ÚNICOS: Apenas o registro mais recente por colaborador+procedimento
    # Usado para indicadores de demanda (total, vigentes, pendentes)
    # =========================================================================
    from django.db.models import Max
    
    # IDs dos registros mais recentes para cada combinação colaborador+procedimento
    ultimos_registros_ids = valid_registros.values(
        'colaborador_id', 'procedimento_id'
    ).annotate(
        ultimo_id=Max('id')
    ).values_list('ultimo_id', flat=True)
    
    # Queryset filtrado apenas com registros únicos
    registros_unicos = valid_registros.filter(id__in=ultimos_registros_ids)
    
    # Estatísticas gerais - USANDO REGISTROS ÚNICOS (sem duplicatas)
    total_treinamentos = registros_unicos.count()
    
    # Treinamentos vigentes: têm data E revisão coincide
    # OTIMIZAÇÃO: Usar query SQL ao invés de carregar tudo na memória
    treinamentos_vigentes = registros_unicos.filter(
        data_treinamento__isnull=False,
        revisao_treinada=F('procedimento__numero_revisao')
    ).count()
    
    # Pendentes: sem data OU revisão desatualizada (também usando registros únicos)
    treinamentos_pendentes = registros_unicos.filter(
        Q(data_treinamento__isnull=True) | 
        ~Q(revisao_treinada=F('procedimento__numero_revisao'))
    ).count()
    
    # Colaboradores com treinamentos vigentes (com data e revisão OK)
    total_colaboradores_treinados = registros_unicos.filter(
        data_treinamento__isnull=False,
        revisao_treinada=F('procedimento__numero_revisao')
    ).values('colaborador_id').distinct().count()
    
    # Procedimentos únicos treinados
    total_procedimentos_unicos = registros_unicos.filter(
        data_treinamento__isnull=False,
        revisao_treinada=F('procedimento__numero_revisao')
    ).values('procedimento_id').distinct().count()
    
    # Treinamentos nos últimos 30 dias - AQUI USA valid_registros (todos os registros)
    # pois queremos ver quantos treinamentos realmente aconteceram
    data_30_dias_atras = date.today() - timedelta(days=30)
    treinamentos_ultimos_30_dias = valid_registros.filter(
        data_treinamento__gte=data_30_dias_atras,
        data_treinamento__isnull=False
    ).count()
    
    # Top lists removed to simplify dashboard and reduce query cost
    top_procedimentos = []
    top_colaboradores = []
    
    # Distribuição de status
    status_distribuicao = {
        'vigente': treinamentos_vigentes,
        'pendente': treinamentos_pendentes
    }
    
    # Taxa de conformidade (treinados vs total)
    if total_treinamentos > 0:
        taxa_conformidade = round((treinamentos_vigentes / total_treinamentos) * 100, 1)
    else:
        taxa_conformidade = 0
    
    # Treinamentos por mês (últimos 12 meses) - OTIMIZADO: query única com agregação
    from django.db.models import Case, When, IntegerField
    from django.db.models.functions import TruncMonth
    
    treinamentos_por_mes = []
    for i in range(11, -1, -1):
        data_inicio = date.today() - timedelta(days=30 * (i + 1))
        data_fim = date.today() - timedelta(days=30 * i)
        
        count = valid_registros.filter(
            data_treinamento__gte=data_inicio,
            data_treinamento__lt=data_fim,
            data_treinamento__isnull=False
        ).count()
        
        treinamentos_por_mes.append({
            'mes': data_inicio.strftime('%b/%y'),
            'total': count
        })
    
    # Gráfico por Líder - OTIMIZADO: apenas líderes com liderados ativos
    treinamentos_por_lider = []
    
    # Query otimizada: buscar líderes que têm liderados ativos
    lideres_com_liderados = Colaborador.objects.filter(
        liderados__is_active=True,
        liderados__isnull=False
    ).distinct().prefetch_related(
        Prefetch('liderados', queryset=Colaborador.objects.filter(is_active=True))
    ).order_by('nome_completo')[:20]  # Limitar a 20 líderes para performance
    
    for lider in lideres_com_liderados:
        liderados_ids = [l.id for l in lider.liderados.all()]
        
        # Contar REGISTROS ÚNICOS (por colaborador+procedimento) com status vigente ou pendente
        vigentes_count = registros_unicos.filter(
            colaborador_id__in=liderados_ids,
            data_treinamento__isnull=False,
            revisao_treinada=F('procedimento__numero_revisao')
        ).count()
        
        pendentes_count = registros_unicos.filter(
            colaborador_id__in=liderados_ids
        ).filter(
            Q(data_treinamento__isnull=True) | 
            ~Q(revisao_treinada=F('procedimento__numero_revisao'))
        ).count()
        
        total = vigentes_count + pendentes_count
        if total > 0:
            # Abreviar nome
            parts = lider.nome_completo.split()
            nome_abrev = f"{parts[0]} {parts[-1]}" if len(parts) > 1 else lider.nome_completo[:30]
            
            treinamentos_por_lider.append({
                'nome': nome_abrev,
                'vigentes': vigentes_count,
                'pendentes': pendentes_count
            })
    
    # Ordenar por total e limitar a 10
    treinamentos_por_lider.sort(key=lambda x: x['vigentes'] + x['pendentes'], reverse=True)
    treinamentos_por_lider = treinamentos_por_lider[:10]
    
    # Gráfico por Setor e Turno - usando registros únicos (1 por colaborador+procedimento)
    from organization.models import Setor
    treinamentos_por_setor_turno = []
    
    # Buscar combinações únicas de setor/turno
    combinacoes_setor_turno = registros_unicos.values(
        'colaborador__setor_id', 
        'colaborador__turno'
    ).filter(
        colaborador__setor_id__isnull=False
    ).distinct()
    
    # Buscar setores uma única vez
    setor_ids = list(set(c['colaborador__setor_id'] for c in combinacoes_setor_turno if c['colaborador__setor_id']))
    setores_dict = {s.id: s.nome for s in Setor.objects.filter(id__in=setor_ids)}
    turno_dict = dict(TURNOS_CHOICES)
    
    for combo in combinacoes_setor_turno:
        setor_id = combo['colaborador__setor_id']
        turno = combo['colaborador__turno']
        
        # Contar registros únicos vigentes e pendentes para este setor/turno
        vigentes_count = registros_unicos.filter(
            colaborador__setor_id=setor_id,
            colaborador__turno=turno,
            data_treinamento__isnull=False,
            revisao_treinada=F('procedimento__numero_revisao')
        ).count()
        
        pendentes_count = registros_unicos.filter(
            colaborador__setor_id=setor_id,
            colaborador__turno=turno
        ).filter(
            Q(data_treinamento__isnull=True) | 
            ~Q(revisao_treinada=F('procedimento__numero_revisao'))
        ).count()
        
        total = vigentes_count + pendentes_count
        if total > 0:
            setor_nome = setores_dict.get(setor_id, 'Desconhecido')
            if len(setor_nome) > 20:
                setor_nome = setor_nome[:17] + '...'
            
            turno_label = turno_dict.get(turno, turno or 'N/A')
            
            treinamentos_por_setor_turno.append({
                'nome': f'{setor_nome} - {turno_label}'[:40],
                'vigentes': vigentes_count,
                'pendentes': pendentes_count
            })
    
    # Ordenar por total e limitar a 10
    treinamentos_por_setor_turno.sort(key=lambda x: x['vigentes'] + x['pendentes'], reverse=True)
    treinamentos_por_setor_turno = treinamentos_por_setor_turno[:10]
    planejamento_instrutor = (
        PlanejamentoTreinamento.objects
        .filter(instrutor__isnull=False)
        .values('instrutor__nome_completo')
        .annotate(
            planejado=Count('id', filter=Q(status='PLANEJADO')),
            confirmado=Count('id', filter=Q(status='CONFIRMADO')),
            realizado=Count('id', filter=Q(status='REALIZADO')),
            cancelado=Count('id', filter=Q(status='CANCELADO')),
            atrasado=Count('id', filter=Q(status='ATRASADO')),
            total=Count('id')
        )
        .order_by('-total')[:10]
    )

    # Planejamento por Setor/Turno (baseado no planejamento)
    planejamento_setor_turno_pl = (
        PlanejamentoTreinamento.objects
        .filter(colaboradores__setor__isnull=False)
        .values('colaboradores__setor__nome', 'colaboradores__turno')
        .annotate(
            planejado=Count('id', filter=Q(status='PLANEJADO')),
            confirmado=Count('id', filter=Q(status='CONFIRMADO')),
            realizado=Count('id', filter=Q(status='REALIZADO')),
            cancelado=Count('id', filter=Q(status='CANCELADO')),
            atrasado=Count('id', filter=Q(status='ATRASADO')),
            total=Count('id')
        )
        .order_by('-total')[:10]
    )
    
    # Montar contexto
    context = {
        'total_treinamentos': total_treinamentos,
        'treinamentos_vigentes': treinamentos_vigentes,
        'treinamentos_pendentes': treinamentos_pendentes,
        'total_colaboradores_treinados': total_colaboradores_treinados,
        'total_procedimentos_unicos': total_procedimentos_unicos,
        'treinamentos_ultimos_30_dias': treinamentos_ultimos_30_dias,
        'taxa_conformidade': taxa_conformidade,
        'status_distribuicao': status_distribuicao,
        'treinamentos_por_mes': treinamentos_por_mes,
        'treinamentos_por_lider': treinamentos_por_lider,
        'treinamentos_por_setor_turno': treinamentos_por_setor_turno,
        'planejamento_por_instrutor': list(planejamento_instrutor),
        'planejamento_por_setor_turno': list(planejamento_setor_turno_pl),
    }
    
    # Adicionar dados de filtros dinâmicos - OTIMIZADO
    from organization.models import Setor
    
    # Setores com colaboradores ativos, não afastados e não em férias
    setores = Setor.objects.filter(
        colaborador__is_active=True,
        colaborador__afastado=False,
        colaborador__em_ferias=False
    ).distinct().order_by('nome').values('id', 'nome')
    context['setores'] = list(setores)
    
    # Turnos
    context['turnos'] = [{'value': t[0], 'label': t[1]} for t in TURNOS_CHOICES]

    # Criticidade / Matriz / Sub-área (opções)
    context['criticidade_choices'] = list(Procedimento._meta.get_field('criticidade').choices)
    context['matrizes'] = list(
        Procedimento.objects.exclude(matriz__isnull=True)
        .exclude(matriz__exact='')
        .values_list('matriz', flat=True)
        .distinct()
        .order_by('matriz')
    )
    context['sub_areas'] = list(
        Procedimento.objects.exclude(sub_area__isnull=True)
        .exclude(sub_area__exact='')
        .values_list('sub_area', flat=True)
        .distinct()
        .order_by('sub_area')
    )
    
    # Líderes com liderados ativos, não afastados e não em férias - OTIMIZADO
    lideres = Colaborador.objects.filter(
        liderados__isnull=False,
        liderados__is_active=True,
        liderados__afastado=False,
        liderados__em_ferias=False,
        is_active=True,
        afastado=False,
        em_ferias=False
    ).distinct().order_by('nome_completo').values('id', 'nome_completo')
    context['lideres'] = [{'id': l['id'], 'nome': l['nome_completo']} for l in lideres]
    
    # Supervisores - OTIMIZADO
    supervisores = Colaborador.objects.filter(
        supervisionados__isnull=False,
        supervisionados__is_active=True,
        supervisionados__afastado=False,
        supervisionados__em_ferias=False,
        is_active=True,
        afastado=False,
        em_ferias=False
    ).distinct().order_by('nome_completo').values('id', 'nome_completo')
    context['supervisores'] = [{'id': s['id'], 'nome': s['nome_completo']} for s in supervisores]
    
    # Gerentes - OTIMIZADO
    gerentes = Colaborador.objects.filter(
        gerenciados__isnull=False,
        gerenciados__is_active=True,
        gerenciados__afastado=False,
        gerenciados__em_ferias=False,
        is_active=True,
        afastado=False,
        em_ferias=False
    ).distinct().order_by('nome_completo').values('id', 'nome_completo')
    context['gerentes'] = [{'id': g['id'], 'nome': g['nome_completo']} for g in gerentes]
    
    # Tabela de dados com paginação - OTIMIZADO: apenas valores necessários
    registros_query = valid_registros.order_by('-data_treinamento', '-id').values(
        'id', 'colaborador__id', 'colaborador__nome_completo', 
        'procedimento__codigo', 'procedimento__nome', 'data_treinamento',
        'revisao_treinada', 'procedimento__numero_revisao'
    )
    
    # Paginar com 15 registros por página
    page_number = request.GET.get('page', '1')
    paginator = Paginator(registros_query, 15)
    page_obj = paginator.get_page(page_number)
    
    # Processar dados da tabela para o template
    dados_processados = []
    for registro in page_obj.object_list:
        # Calcular status diretamente
        if not registro['data_treinamento']:
            status = 'NAO_INICIADO'
        elif registro['revisao_treinada'] == registro['procedimento__numero_revisao']:
            status = 'OK'
        else:
            status = 'PENDENTE'
        
        dados_processados.append({
            'id': registro['id'],
            'colaborador_id': registro['colaborador__id'],
            'colaborador': registro['colaborador__nome_completo'],
            'procedimento': registro['procedimento__codigo'],
            'procedimento_nome': registro['procedimento__nome'][:40] if registro['procedimento__nome'] else '',
            'data': registro['data_treinamento'].strftime('%d/%m/%Y') if registro['data_treinamento'] else 'Pendente',
            'status': status
        })
    
    context['dados_tabela'] = dados_processados
    context['page_obj'] = page_obj
    context['paginator'] = paginator

    query_params = request.GET.copy()
    query_params.pop('page', None)
    context['query_string'] = query_params.urlencode()
    
    # Adicionar filtros selecionados ao contexto (como listas completas)
    context['filtro_setor_list'] = filtro_setor_list
    context['filtro_turno_list'] = filtro_turno_list
    context['filtro_lider_list'] = filtro_lider_list
    context['filtro_criticidade_list'] = filtro_criticidade_list
    context['filtro_matriz_list'] = filtro_matriz_list
    context['filtro_sub_area_list'] = filtro_sub_area_list
    
    # Também adicionar os valores únicos para compatibilidade
    context['filtro_setor'] = filtro_setor
    context['filtro_turno'] = filtro_turno
    context['filtro_lider'] = filtro_lider
    context['filtro_criticidade'] = filtro_criticidade
    context['filtro_matriz'] = filtro_matriz
    context['filtro_sub_area'] = filtro_sub_area
    
    # Cachear contexto por 5 minutos (300 segundos) - apenas sem filtros
    if not has_filters:
        cache.set(cache_key, context, 300)
    
    return render(request, 'training/dashboard_treinamentos.html', context)


@login_required
def dashboard_treinamentos_filtered_view(request):
    """API para retornar dados filtrados do dashboard"""
    import json
    from django.http import JsonResponse
    from django.db.models import Count, Q, Exists, OuterRef
    from datetime import timedelta, date
    
    # Pegar filtros da query string
    turno = request.GET.get('turno', '').strip()
    setor_id = request.GET.get('setor', '').strip()
    lider_id = request.GET.get('lider', '').strip()
    supervisor_id = request.GET.get('supervisor', '').strip()
    gerente_id = request.GET.get('gerente', '').strip()
    
    # Base query - apenas registros com colaborador ATIVO, NÃO AFASTADO, NÃO EM FÉRIAS, procedimento não nulos E ativo=True
    base_query = Q(
        colaborador__isnull=False,
        colaborador__is_active=True,
        colaborador__afastado=False,  # Não contar treinamentos de colaboradores afastados
        colaborador__em_ferias=False,  # Não contar treinamentos de colaboradores em férias
        procedimento__isnull=False,
        ativo=True
    )
    
    if turno:
        base_query &= Q(colaborador__turno=turno)
    if setor_id:
        try:
            base_query &= Q(colaborador__setor_id=int(setor_id))
        except:
            pass
    if lider_id:
        try:
            base_query &= Q(colaborador__lider_id=int(lider_id))
        except:
            pass
    if supervisor_id:
        try:
            base_query &= Q(colaborador__supervisor_id=int(supervisor_id))
        except:
            pass
    if gerente_id:
        try:
            base_query &= Q(colaborador__gerente_id=int(gerente_id))
        except:
            pass

    # Novo: permitir filtrar por status (vigente / pendente)
    status_param = (request.GET.get('status') or '').strip().lower()
    if status_param == 'vigente':
        base_query &= Q(data_treinamento__isnull=False) & Q(revisao_treinada=F('procedimento__numero_revisao'))
    elif status_param == 'pendente':
        base_query &= Q(Q(data_treinamento__isnull=True) | ~Q(revisao_treinada=F('procedimento__numero_revisao')))

    
    # Base: todos os registros que atendem aos filtros
    todos_registros = RegistroTreinamento.objects.filter(base_query).distinct()
    
    # =========================================================================
    # REGISTROS ÚNICOS: Apenas o registro mais recente por colaborador+procedimento
    # Usado para indicadores de demanda (total, vigentes, pendentes)
    # =========================================================================
    from django.db.models import Max
    
    # IDs dos registros mais recentes para cada combinação colaborador+procedimento
    ultimos_registros_ids = todos_registros.values(
        'colaborador_id', 'procedimento_id'
    ).annotate(
        ultimo_id=Max('id')
    ).values_list('ultimo_id', flat=True)
    
    # Queryset filtrado apenas com registros únicos
    treinamentos = todos_registros.filter(id__in=ultimos_registros_ids)
    
    # Contagens usando REGISTROS ÚNICOS (sem duplicatas por colaborador+procedimento)
    total_treinamentos = treinamentos.count()
    treinamentos_vigentes = treinamentos.filter(
        data_treinamento__isnull=False,
        revisao_treinada=F('procedimento__numero_revisao')
    ).count()
    treinamentos_pendentes = treinamentos.filter(
        Q(data_treinamento__isnull=True) | 
        ~Q(revisao_treinada=F('procedimento__numero_revisao'))
    ).count()
    
    # Taxa de conformidade
    if total_treinamentos > 0:
        taxa_conformidade = round((treinamentos_vigentes / total_treinamentos) * 100, 1)
    else:
        taxa_conformidade = 0
    
    # Distribuição de status
    status_distribuicao = {
        'vigente': treinamentos_vigentes,
        'pendente': treinamentos_pendentes
    }
    
    # Gráfico por mês (últimos 12 meses) - usa todos_registros para contar todos os treinamentos realizados
    treinamentos_por_mes = []
    for i in range(11, -1, -1):
        data_inicio = date.today() - timedelta(days=30 * (i + 1))
        data_fim = date.today() - timedelta(days=30 * i)
        
        count = todos_registros.filter(
            data_treinamento__gte=data_inicio,
            data_treinamento__lt=data_fim,
            data_treinamento__isnull=False
        ).count()
        
        treinamentos_por_mes.append({
            'mes': data_inicio.strftime('%b/%y'),
            'total': count
        })
    
    # Treinamentos nos últimos 30 dias - usa todos_registros (conta todos os treinamentos realizados)
    data_30_dias_atras = date.today() - timedelta(days=30)
    treinamentos_ultimos_30_dias = todos_registros.filter(
        data_treinamento__gte=data_30_dias_atras,
        data_treinamento__isnull=False
    ).count()
    
    # Top lists removed to reduce payload
    top_procedimentos = []
    top_colaboradores = []
    
    # Gráfico por Líder (usando registros únicos)
    treinamentos_por_lider = []
    líderes_q = Colaborador.objects.filter(
        liderados__isnull=False,
        liderados__is_active=True
    ).distinct().order_by('nome_completo')
    
    for lider in líderes_q:
        liderados_ids = list(lider.liderados.filter(is_active=True).values_list('id', flat=True))
        
        # Contar REGISTROS ÚNICOS com status vigente ou pendente
        vigentes_count = treinamentos.filter(
            colaborador_id__in=liderados_ids,
            data_treinamento__isnull=False,
            revisao_treinada=F('procedimento__numero_revisao')
        ).count()
        
        pendentes_count = treinamentos.filter(
            colaborador_id__in=liderados_ids
        ).filter(
            Q(data_treinamento__isnull=True) | 
            ~Q(revisao_treinada=F('procedimento__numero_revisao'))
        ).count()
        
        total = vigentes_count + pendentes_count
        if total > 0:
            parts = lider.nome_completo.split()
            if len(parts) > 1:
                nome_abrev = f"{parts[0]} {parts[-1]}"
            else:
                nome_abrev = lider.nome_completo[:30]
            
            treinamentos_por_lider.append({
                'nome': nome_abrev,
                'vigentes': vigentes_count,
                'pendentes': pendentes_count
            })
    
    treinamentos_por_lider.sort(key=lambda x: x['vigentes'] + x['pendentes'], reverse=True)
    treinamentos_por_lider = treinamentos_por_lider[:10]
    
    # Gráfico por Setor e Turno (usando registros únicos)
    treinamentos_por_setor_turno = []
    from organization.models import Setor
    from core.models import TURNOS_CHOICES
    
    combinacoes = Colaborador.objects.filter(
        setor__isnull=False,
        is_active=True
    ).values_list('setor_id', 'turno').distinct()
    
    turno_dict = dict(TURNOS_CHOICES)
    setores_cache = {}
    
    for setor_id, turno_val in combinacoes:
        try:
            # Cache de setores
            if setor_id not in setores_cache:
                setores_cache[setor_id] = Setor.objects.get(id=setor_id)
            setor = setores_cache[setor_id]
            
            # Contar REGISTROS ÚNICOS com status vigente ou pendente para este setor/turno
            vigentes_count = treinamentos.filter(
                colaborador__setor_id=setor_id,
                colaborador__turno=turno_val,
                data_treinamento__isnull=False,
                revisao_treinada=F('procedimento__numero_revisao')
            ).count()
            
            pendentes_count = treinamentos.filter(
                colaborador__setor_id=setor_id,
                colaborador__turno=turno_val
            ).filter(
                Q(data_treinamento__isnull=True) | 
                ~Q(revisao_treinada=F('procedimento__numero_revisao'))
            ).count()
            
            total = vigentes_count + pendentes_count
            if total > 0:
                turno_label = turno_dict.get(turno_val, turno_val)
                
                setor_nome = setor.nome
                if len(setor_nome) > 20:
                    setor_nome = setor_nome[:17] + '...'
                
                treinamentos_por_setor_turno.append({
                    'nome': f'{setor_nome} - {turno_label}'[:40],
                    'vigentes': vigentes_count,
                    'pendentes': pendentes_count
                })
        except:
            pass
    
    treinamentos_por_setor_turno.sort(key=lambda x: x['vigentes'] + x['pendentes'], reverse=True)
    treinamentos_por_setor_turno = treinamentos_por_setor_turno[:10]
    
    # Dados da tabela: últimos treinamentos
    dados_tabela = list(treinamentos.select_related(
        'colaborador', 'procedimento'
    ).order_by('-data_treinamento', '-id')[:50].values(
        'id', 'colaborador__nome_completo', 'procedimento__codigo',
        'procedimento__nome', 'data_treinamento'
    ))
    
    dados_tabela_list = []
    for registro in dados_tabela:
        dados_tabela_list.append({
            'id': registro['id'],
            'colaborador': registro['colaborador__nome_completo'],
            'procedimento': registro['procedimento__codigo'],
            'procedimento_nome': registro['procedimento__nome'][:40],
            'data': registro['data_treinamento'].strftime('%d/%m/%Y') if registro['data_treinamento'] else 'Pendente'
        })
    
    return JsonResponse({
        'total_treinamentos': total_treinamentos,
        'treinamentos_vigentes': treinamentos_vigentes,
        'treinamentos_pendentes': treinamentos_pendentes,
        'treinamentos_ultimos_30_dias': treinamentos_ultimos_30_dias,
        'taxa_conformidade': taxa_conformidade,
        'status_distribuicao': status_distribuicao,
        'treinamentos_por_mes': treinamentos_por_mes,
        'treinamentos_por_lider': treinamentos_por_lider,
        'treinamentos_por_setor_turno': treinamentos_por_setor_turno,
        'dados_tabela': dados_tabela_list
    })


@login_required
def dashboard_treinamentos_exportar_csv_view(request):
    """Exporta todos os treinamentos do dashboard em CSV (respeitando filtros)"""
    import csv
    from datetime import date
    
    # Pegar filtros da query string (suportar múltiplos valores)
    turnos = request.GET.getlist('turno')
    setores = request.GET.getlist('setor')
    lideres = request.GET.getlist('lider')
    criticidades = request.GET.getlist('criticidade')
    matrizes = request.GET.getlist('matriz')
    sub_areas = request.GET.getlist('sub_area')
    
    # Base query - apenas registros ATIVOS, NÃO AFASTADOS, NÃO EM FÉRIAS
    base_query = Q(
        colaborador__isnull=False,
        colaborador__is_active=True,
        colaborador__afastado=False,
        colaborador__em_ferias=False,
        procedimento__isnull=False,
        ativo=True
    )
    
    # Aplicar filtros (se há múltiplos valores)
    if turnos:
        base_query &= Q(colaborador__turno__in=turnos)
    if setores:
        try:
            setores_int = [int(s) for s in setores if s.strip()]
            if setores_int:
                base_query &= Q(colaborador__setor_id__in=setores_int)
        except:
            pass
    if lideres:
        try:
            lideres_int = [int(l) for l in lideres if l.strip()]
            if lideres_int:
                base_query &= Q(colaborador__lider_id__in=lideres_int)
        except:
            pass

    if criticidades:
        criticidades_clean = [c for c in criticidades if str(c).strip()]
        if criticidades_clean:
            base_query &= Q(procedimento__criticidade__in=criticidades_clean)

    if matrizes:
        matrizes_clean = [m for m in matrizes if str(m).strip()]
        if matrizes_clean:
            base_query &= Q(procedimento__matriz__in=matrizes_clean)

    if sub_areas:
        sub_areas_clean = [sa for sa in sub_areas if str(sa).strip()]
        if sub_areas_clean:
            base_query &= Q(procedimento__sub_area__in=sub_areas_clean)
    
    # Obter TODOS os registros (não paginar)
    registros = RegistroTreinamento.objects.filter(base_query).select_related(
        'colaborador', 'procedimento'
    ).order_by('-data_treinamento', '-id')
    
    # Criar resposta CSV
    response = HttpResponse(content_type='text/csv;charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="treinamentos_{date.today().isoformat()}.csv"'
    
    # Escrever BOM para UTF-8
    response.write('\ufeff')
    
    writer = csv.writer(response, delimiter=';', quoting=csv.QUOTE_ALL)
    
    # Cabeçalhos
    writer.writerow([
        'Colaborador',
        'Matrícula',
        'Cargo',
        'Setor',
        'Procedimento',
        'Código',
        'Data Treinamento',
        'Revisão Treinada',
        'Revisão Procedimento',
        'Status',
        'Carga Horária'
    ])
    
    # Dados
    for treinamento in registros:
        # Determinar status
        if not treinamento.data_treinamento:
            status = 'NÃO INICIADO'
        elif treinamento.revisao_treinada == treinamento.procedimento.numero_revisao:
            status = 'VIGENTE'
        else:
            status = 'PENDENTE'
        
        writer.writerow([
            treinamento.colaborador.nome_completo if treinamento.colaborador else '',
            treinamento.colaborador.matricula if treinamento.colaborador else '',
            treinamento.colaborador.cargo if treinamento.colaborador else '',
            treinamento.colaborador.setor.nome if treinamento.colaborador and treinamento.colaborador.setor else '',
            treinamento.procedimento.nome if treinamento.procedimento else '',
            treinamento.procedimento.codigo if treinamento.procedimento else '',
            treinamento.data_treinamento.strftime('%d/%m/%Y') if treinamento.data_treinamento else '',
            treinamento.revisao_treinada if treinamento.revisao_treinada else '',
            treinamento.procedimento.numero_revisao if treinamento.procedimento else '',
            status,
            f'{treinamento.carga_horaria}h' if treinamento.carga_horaria else ''
        ])
    
    return response
