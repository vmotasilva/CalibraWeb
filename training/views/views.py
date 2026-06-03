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
from django.http import HttpResponse, JsonResponse
from django.db.models import Q
from django.core.paginator import Paginator
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def _abreviar_nome_dashboard(nome_completo, max_chars=30):
    nome_normalizado = " ".join(str(nome_completo or "").split())
    if not nome_normalizado:
        return ""

    partes = nome_normalizado.split(" ")
    if len(partes) == 1:
        return nome_normalizado[:max_chars]

    return f"{partes[0]} {partes[-1]}"[:max_chars]


def _coerce_int_list(values):
    return [int(value) for value in values if str(value).strip().isdigit()]


def _coerce_positive_int(value, default):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _normalize_scope_name(value):
    return (value or "").strip().casefold()


def _split_responsabilidades_treinamento(responsabilidades):
    responsabilidades_por_subarea = {}
    responsabilidades_gerais = {}
    for responsabilidade in responsabilidades:
        if not responsabilidade.colaborador_id or not responsabilidade.turno:
            continue

        matriz_nome = _normalize_scope_name(getattr(responsabilidade.matriz, 'nome', ''))
        if not matriz_nome:
            continue

        if responsabilidade.sub_area_id:
            sub_area_nome = _normalize_scope_name(getattr(responsabilidade.sub_area, 'nome', ''))
            if not sub_area_nome:
                continue
            responsabilidades_por_subarea[(matriz_nome, sub_area_nome, responsabilidade.turno)] = responsabilidade.colaborador
            continue

        responsabilidades_gerais[(matriz_nome, responsabilidade.turno)] = responsabilidade.colaborador

    return responsabilidades_por_subarea, responsabilidades_gerais


def _resolve_responsavel_treinamento(responsabilidades_por_subarea, responsabilidades_gerais, matriz_nome, sub_area_nome, turno):
    matriz_key = _normalize_scope_name(matriz_nome)
    if not matriz_key or not turno:
        return None

    sub_area_key = _normalize_scope_name(sub_area_nome)
    if sub_area_key:
        responsavel = responsabilidades_por_subarea.get((matriz_key, sub_area_key, turno))
        if responsavel:
            return responsavel

    return responsabilidades_gerais.get((matriz_key, turno))


def _build_responsavel_scope_q(responsabilidades_por_subarea, responsabilidades_gerais, scope_rows, responsavel_ids):
    scope_q = None
    responsavel_ids = set(responsavel_ids)
    for matriz_nome, sub_area_nome, turno in scope_rows:
        responsavel = _resolve_responsavel_treinamento(
            responsabilidades_por_subarea,
            responsabilidades_gerais,
            matriz_nome,
            sub_area_nome,
            turno,
        )
        if not responsavel or responsavel.id not in responsavel_ids:
            continue

        item_q = Q(procedimento__matriz=matriz_nome, colaborador__turno=turno)
        if _normalize_scope_name(sub_area_nome):
            item_q &= Q(procedimento__sub_area=sub_area_nome)
        else:
            item_q &= (Q(procedimento__sub_area__isnull=True) | Q(procedimento__sub_area__exact=''))
        scope_q = item_q if scope_q is None else (scope_q | item_q)
    return scope_q


def _paginate_dashboard_pendencias(request, context):
    pendencias = list(context.get('pendencias_dashboard') or [])
    total_pendencias = context.get('total_pendencias_dashboard')
    if total_pendencias is None:
        total_pendencias = len(pendencias)
        context['total_pendencias_dashboard'] = total_pendencias

    page_size = _coerce_positive_int(request.GET.get('pendencias_page_size'), 10)
    if page_size not in {10, 25, 50, 100}:
        page_size = 10

    paginator = Paginator(pendencias, page_size)
    page_obj = paginator.get_page(request.GET.get('pendencias_page') or 1)
    query_params = request.GET.copy()
    query_params.pop('pendencias_page', None)

    context['todas_pendencias_dashboard'] = pendencias
    context['pendencias_dashboard'] = list(page_obj.object_list)
    context['pendencias_page_obj'] = page_obj
    context['pendencias_page_size'] = page_size
    context['pendencias_page_size_options'] = [10, 25, 50, 100]
    context['pendencias_querystring'] = query_params.urlencode()
    context['pendencias_page_start'] = page_obj.start_index() if paginator.count else 0
    context['pendencias_page_end'] = page_obj.end_index() if paginator.count else 0
    return context

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
def dashboard_treinamentos_view(request):
    """Dashboard completo de treinamentos com estatísticas e gráficos - OTIMIZADO"""
    from django.db.models import Count, Q, Exists, OuterRef, Prefetch, F
    from datetime import timedelta, date
    from core.models import TURNOS_CHOICES
    from django.core.cache import cache
    from procedures.models import PlanejamentoTreinamento, Procedimento, ResponsavelTreinamentoMatriz
    from organization.models import Setor

    responsabilidades_registros = list(
        ResponsavelTreinamentoMatriz.objects.select_related('matriz', 'sub_area', 'colaborador').filter(
            colaborador__isnull=False,
        )
    )
    responsabilidades_por_subarea, responsabilidades_gerais = _split_responsabilidades_treinamento(
        responsabilidades_registros
    )
    
    # Capturar filtros da URL (suportar múltiplos valores)
    filtro_setor_list = request.GET.getlist('setor')
    filtro_turno_list = request.GET.getlist('turno')
    filtro_lider_list = request.GET.getlist('lider')
    filtro_supervisor_list = request.GET.getlist('supervisor')
    filtro_gerente_list = request.GET.getlist('gerente')
    filtro_criticidade_list = request.GET.getlist('criticidade')
    filtro_matriz_list = request.GET.getlist('matriz')
    filtro_sub_area_list = request.GET.getlist('sub_area')
    filtro_instrutor_responsavel_list = request.GET.getlist('instrutor_responsavel')
    filtro_colaborador_id = (request.GET.get('colaborador_id') or '').strip()
    filtro_colaborador_q = (request.GET.get('colaborador_q') or '').strip()

    # Se veio apenas com texto e ele retorna UM único colaborador, promover para ID
    # (evita ambiguidade e permite cálculo por perfil no dashboard)
    if (not filtro_colaborador_id) and filtro_colaborador_q and len(filtro_colaborador_q) >= 2:
        candidatos = list(
            Colaborador.objects.filter(
                is_active=True,
                afastado=False,
                em_ferias=False,
            ).filter(
                Q(nome_completo__icontains=filtro_colaborador_q)
                | Q(matricula__icontains=filtro_colaborador_q)
            ).values_list('id', flat=True)[:2]
        )
        if len(candidatos) == 1:
            filtro_colaborador_id = str(candidatos[0])
    
    # Para template (primeiro valor ou vazio)
    filtro_setor = filtro_setor_list[0] if filtro_setor_list else ''
    filtro_turno = filtro_turno_list[0] if filtro_turno_list else ''
    filtro_lider = filtro_lider_list[0] if filtro_lider_list else ''
    filtro_supervisor = filtro_supervisor_list[0] if filtro_supervisor_list else ''
    filtro_gerente = filtro_gerente_list[0] if filtro_gerente_list else ''
    filtro_criticidade = filtro_criticidade_list[0] if filtro_criticidade_list else ''
    filtro_matriz = filtro_matriz_list[0] if filtro_matriz_list else ''
    filtro_sub_area = filtro_sub_area_list[0] if filtro_sub_area_list else ''
    filtro_instrutor_responsavel = filtro_instrutor_responsavel_list[0] if filtro_instrutor_responsavel_list else ''
    
    # Se há filtros, não usar cache
    has_filters = (
        filtro_setor_list
        or filtro_turno_list
        or filtro_lider_list
        or filtro_supervisor_list
        or filtro_gerente_list
        or filtro_criticidade_list
        or filtro_matriz_list
        or filtro_sub_area_list
        or filtro_instrutor_responsavel_list
        or bool(filtro_colaborador_id)
        or bool(filtro_colaborador_q)
    )
    
    # Cache key para estatísticas do dashboard (apenas sem filtros)
    cache_key = 'dashboard_treinamentos_stats'
    if not has_filters:
        cached_data = cache.get(cache_key)
        if cached_data:
            cached_data = dict(cached_data)
            # Adicionar dados de filtros ao cache
            cached_data['filtro_setor'] = filtro_setor
            cached_data['filtro_turno'] = filtro_turno
            cached_data['filtro_lider'] = filtro_lider
            cached_data['filtro_criticidade'] = filtro_criticidade
            cached_data['filtro_matriz'] = filtro_matriz
            cached_data['filtro_sub_area'] = filtro_sub_area
            cached_data['filtro_instrutor_responsavel'] = filtro_instrutor_responsavel
            cached_data['filtro_instrutor_responsavel_list'] = filtro_instrutor_responsavel_list
            cached_data['filtro_colaborador_id'] = filtro_colaborador_id
            cached_data['filtro_colaborador_q'] = filtro_colaborador_q
            cached_data.setdefault('instrutores_responsaveis', [])
            cached_data.setdefault('pendencias_dashboard', [])
            cached_data.setdefault('total_pendencias_dashboard', 0)
            _paginate_dashboard_pendencias(request, cached_data)
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

    if filtro_supervisor_list:
        valid_registros = valid_registros.filter(colaborador__supervisor_id__in=filtro_supervisor_list)

    if filtro_gerente_list:
        valid_registros = valid_registros.filter(colaborador__gerente_id__in=filtro_gerente_list)

    if filtro_criticidade_list:
        valid_registros = valid_registros.filter(procedimento__criticidade__in=filtro_criticidade_list)

    if filtro_matriz_list:
        valid_registros = valid_registros.filter(procedimento__matriz__in=filtro_matriz_list)

    if filtro_sub_area_list:
        valid_registros = valid_registros.filter(procedimento__sub_area__in=filtro_sub_area_list)

    filtro_instrutor_responsavel_ids = _coerce_int_list(filtro_instrutor_responsavel_list)
    if filtro_instrutor_responsavel_list:
        scope_rows = list(
            valid_registros.values_list(
                'procedimento__matriz',
                'procedimento__sub_area',
                'colaborador__turno',
            ).distinct()
        )
        responsabilidades_scope_q = _build_responsavel_scope_q(
            responsabilidades_por_subarea,
            responsabilidades_gerais,
            scope_rows,
            filtro_instrutor_responsavel_ids,
        )
        valid_registros = valid_registros.filter(responsabilidades_scope_q) if responsabilidades_scope_q is not None else valid_registros.none()

    if filtro_colaborador_id and filtro_colaborador_id.isdigit():
        valid_registros = valid_registros.filter(colaborador_id=int(filtro_colaborador_id))
    elif filtro_colaborador_q:
        valid_registros = valid_registros.filter(
            Q(colaborador__nome_completo__icontains=filtro_colaborador_q)
            | Q(colaborador__matricula__icontains=filtro_colaborador_q)
        )

    # Considerar apenas procedimentos associados a algum perfil ativo do colaborador
    # (sem duplicar; Exists não multiplica linhas)
    from procedures.models import ColaboradorPerfil
    perfil_exists_qs = ColaboradorPerfil.objects.filter(
        colaborador_id=OuterRef('colaborador_id'),
        ativo=True,
        perfil__grupos__subgrupos__procedimentos=OuterRef('procedimento_id'),
    )
    valid_registros = valid_registros.annotate(
        _associado_perfil=Exists(perfil_exists_qs)
    ).filter(_associado_perfil=True)

    # =====================================================================
    # MODO COLABORADOR (EXATO POR ID): indicadores devem refletir o PERFIL
    # (inclui procedimentos sem registro => "não iniciado"), como no RH.
    # =====================================================================
    perfil_procedimentos_ids = None
    colaborador_obj = None
    if filtro_colaborador_id and filtro_colaborador_id.isdigit():
        colab_id_int = int(filtro_colaborador_id)
        colaborador_obj = Colaborador.objects.filter(id=colab_id_int).first()

        # Se o colaborador não passar nos filtros de colaborador, tratamos como sem resultado.
        if colaborador_obj:
            if not getattr(colaborador_obj, 'is_active', False):
                colaborador_obj = None
            if getattr(colaborador_obj, 'afastado', False):
                colaborador_obj = None
            if getattr(colaborador_obj, 'em_ferias', False):
                colaborador_obj = None

        if colaborador_obj:
            # Respeitar filtros "de colaborador" mesmo se ele não tiver registros.
            if filtro_setor_list and str(getattr(colaborador_obj, 'setor_id', '') or '') not in set(map(str, filtro_setor_list)):
                colaborador_obj = None
            if filtro_turno_list and str(getattr(colaborador_obj, 'turno', '') or '') not in set(map(str, filtro_turno_list)):
                colaborador_obj = None
            if filtro_lider_list and str(getattr(colaborador_obj, 'lider_id', '') or '') not in set(map(str, filtro_lider_list)):
                colaborador_obj = None

        if colaborador_obj:
            from procedures.models import ColaboradorPerfil

            procedimentos_qs = Procedimento.objects.none()
            for cp in ColaboradorPerfil.objects.filter(colaborador_id=colab_id_int, ativo=True).select_related('perfil'):
                procedimentos_qs = procedimentos_qs | cp.get_procedimentos_necessarios()

            procedimentos_qs = procedimentos_qs.distinct()

            # Respeitar filtros do dashboard que são do procedimento
            if filtro_criticidade_list:
                procedimentos_qs = procedimentos_qs.filter(criticidade__in=filtro_criticidade_list)
            if filtro_matriz_list:
                procedimentos_qs = procedimentos_qs.filter(matriz__in=filtro_matriz_list)
            if filtro_sub_area_list:
                procedimentos_qs = procedimentos_qs.filter(sub_area__in=filtro_sub_area_list)
            if filtro_instrutor_responsavel_ids:
                procedimentos_ids_permitidos = []
                for procedimento_id, matriz_nome, sub_area_nome in procedimentos_qs.values_list('id', 'matriz', 'sub_area'):
                    responsavel = _resolve_responsavel_treinamento(
                        responsabilidades_por_subarea,
                        responsabilidades_gerais,
                        matriz_nome,
                        sub_area_nome,
                        getattr(colaborador_obj, 'turno', None),
                    )
                    if responsavel and responsavel.id in filtro_instrutor_responsavel_ids:
                        procedimentos_ids_permitidos.append(procedimento_id)
                procedimentos_qs = procedimentos_qs.filter(id__in=procedimentos_ids_permitidos) if procedimentos_ids_permitidos else procedimentos_qs.none()

            perfil_procedimentos_ids = list(procedimentos_qs.values_list('id', flat=True))
            if not perfil_procedimentos_ids:
                perfil_procedimentos_ids = None

            # Garantir que gráficos/tabela (baseados em registros) fiquem consistentes com o Perfil
            if perfil_procedimentos_ids:
                valid_registros = valid_registros.filter(procedimento_id__in=perfil_procedimentos_ids)
    
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
    
    # Definição unificada de status vigente e pendente (referência: data de aprovação do documento)
    vigentes_q = Q(data_treinamento__isnull=False) & (
        Q(procedimento__data_aprovacao__isnull=True) |
        Q(data_treinamento__gte=F('procedimento__data_aprovacao'))
    )
    pendentes_q = Q(data_treinamento__isnull=True) | (
        Q(procedimento__data_aprovacao__isnull=False) &
        Q(data_treinamento__lt=F('procedimento__data_aprovacao'))
    )

    # Estatísticas gerais - USANDO REGISTROS ÚNICOS (sem duplicatas)
    total_treinamentos = registros_unicos.count()
    
    # Treinamentos vigentes: têm data e foram após a data de aprovação (ou sem aprovação cadastrada)
    treinamentos_vigentes = registros_unicos.filter(vigentes_q).count()
    
    # Pendentes: sem data ou antes da data de aprovação
    treinamentos_pendentes = registros_unicos.filter(pendentes_q).count()
    
    # Colaboradores com treinamentos vigentes
    total_colaboradores_treinados = registros_unicos.filter(vigentes_q).values('colaborador_id').distinct().count()
    
    # Procedimentos únicos treinados
    total_procedimentos_unicos = registros_unicos.filter(vigentes_q).values('procedimento_id').distinct().count()
    
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

    ultimo_treinamento_por_procedimento = {}

    # Se filtrou colaborador exato, os indicadores devem refletir a matriz do Perfil
    if colaborador_obj is not None and perfil_procedimentos_ids:
        EPOCH_DATE = date(1970, 1, 1)

        # Não filtrar por "ativo" aqui: para bater com Matriz/RH, usamos o histórico real
        treinamentos_qs = RegistroTreinamento.objects.filter(
            colaborador_id=colaborador_obj.id,
            procedimento_id__in=perfil_procedimentos_ids,
            procedimento__isnull=False,
        ).select_related('procedimento', 'lista_presenca').order_by('-data_treinamento', '-id')

        # 1) Preferir registros com data válida (não nula e não 1970-01-01)
        for t in treinamentos_qs:
            proc_id = t.procedimento_id
            if proc_id in ultimo_treinamento_por_procedimento:
                continue
            if not t.data_treinamento:
                continue
            if t.data_treinamento == EPOCH_DATE:
                continue
            ultimo_treinamento_por_procedimento[proc_id] = t

        # 2) Se não houver data válida, cair para o registro mais recente sem data
        for t in treinamentos_qs:
            proc_id = t.procedimento_id
            if proc_id in ultimo_treinamento_por_procedimento:
                continue
            if t.data_treinamento:
                continue
            ultimo_treinamento_por_procedimento[proc_id] = t

        vigentes_count = 0
        pendentes_count = 0
        for proc_id in perfil_procedimentos_ids:
            t = ultimo_treinamento_por_procedimento.get(proc_id)
            if not t:
                pendentes_count += 1
                continue

            # Se a data é sentinela, tratar como pendente
            if t.data_treinamento == EPOCH_DATE:
                pendentes_count += 1
                continue

            if t.status_treinamento == 'OK':
                vigentes_count += 1
            else:
                pendentes_count += 1

        total_treinamentos = len(perfil_procedimentos_ids)
        treinamentos_vigentes = vigentes_count
        treinamentos_pendentes = pendentes_count
        total_procedimentos_unicos = vigentes_count
        total_colaboradores_treinados = 1 if vigentes_count > 0 else 0
        status_distribuicao = {
            'vigente': treinamentos_vigentes,
            'pendente': treinamentos_pendentes
        }

        if total_treinamentos > 0:
            taxa_conformidade = round((treinamentos_vigentes / total_treinamentos) * 100, 1)
        else:
            taxa_conformidade = 0

        # Ajustar gráficos de DEMANDA para refletirem o cálculo por perfil (colaborador único)
        try:
            if getattr(colaborador_obj, 'lider', None):
                parts = str(colaborador_obj.lider.nome_completo or '').split()
                nome_lider = f"{parts[0]} {parts[-1]}" if len(parts) > 1 else (colaborador_obj.lider.nome_completo or '')
            else:
                nome_lider = 'Sem líder'
            treinamentos_por_lider = [{'nome': nome_lider[:30], 'vigentes': vigentes_count, 'pendentes': pendentes_count}]
        except Exception:
            pass

        try:
            from core.models import TURNOS_CHOICES
            turno_dict = dict(TURNOS_CHOICES)
            setor_nome = getattr(getattr(colaborador_obj, 'setor', None), 'nome', None) or 'Desconhecido'
            turno_label = turno_dict.get(getattr(colaborador_obj, 'turno', None), getattr(colaborador_obj, 'turno', None) or 'N/A')
            treinamentos_por_setor_turno = [{'nome': f'{setor_nome} - {turno_label}'[:40], 'vigentes': vigentes_count, 'pendentes': pendentes_count}]
        except Exception:
            pass
    
    # Taxa de conformidade (treinados vs total)
    if total_treinamentos > 0:
        taxa_conformidade = round((treinamentos_vigentes / total_treinamentos) * 100, 1)
    else:
        taxa_conformidade = 0
    
    # Treinamentos por mês (últimos 12 meses) - por mês de calendário
    from django.db.models.functions import TruncMonth

    def _add_months(month_start: date, months: int) -> date:
        year = month_start.year + (month_start.month - 1 + months) // 12
        month = (month_start.month - 1 + months) % 12 + 1
        return date(year, month, 1)

    current_month_start = date.today().replace(day=1)
    oldest_month_start = _add_months(current_month_start, -11)
    month_starts = [_add_months(oldest_month_start, i) for i in range(12)]

    month_counts = {
        (row['mes'].date() if hasattr(row['mes'], 'date') else row['mes']): row['total']
        for row in valid_registros.filter(
            data_treinamento__isnull=False,
            data_treinamento__gte=oldest_month_start,
        )
        .annotate(mes=TruncMonth('data_treinamento'))
        .values('mes')
        .annotate(total=Count('id'))
        .order_by('mes')
    }

    treinamentos_por_mes = [
        {
            'mes': m.strftime('%b/%y'),
            'mes_iso': m.strftime('%Y-%m'),
            'total': month_counts.get(m, 0),
        }
        for m in month_starts
    ]
    
    # Gráfico por Líder - evitar N+1: 1 query agregada
    treinamentos_por_lider = []

    lideres_com_liderados = list(
        Colaborador.objects.filter(
            liderados__is_active=True,
            liderados__isnull=False
        )
        .distinct()
        .order_by('nome_completo')[:20]
    )

    lider_ids = [l.id for l in lideres_com_liderados]
    lider_nome_abrev = {}
    for lider in lideres_com_liderados:
        parts = (lider.nome_completo or '').split()
        nome_abrev = f"{parts[0]} {parts[-1]}" if len(parts) > 1 else (lider.nome_completo or '')[:30]
        lider_nome_abrev[lider.id] = (nome_abrev or 'Sem líder')[:30]

    if lider_ids:
        lider_counts = (
            registros_unicos
            .filter(colaborador__lider_id__in=lider_ids)
            .values('colaborador__lider_id')
            .annotate(
                vigentes=Count(
                    'id',
                    filter=vigentes_q
                ),
                pendentes=Count(
                    'id',
                    filter=pendentes_q
                )
            )
        )

        for row in lider_counts:
            lider_id = row.get('colaborador__lider_id')
            vigentes_count = int(row.get('vigentes') or 0)
            pendentes_count = int(row.get('pendentes') or 0)
            total = vigentes_count + pendentes_count
            if total > 0 and lider_id in lider_nome_abrev:
                treinamentos_por_lider.append({
                    'nome': lider_nome_abrev[lider_id],
                    'vigentes': vigentes_count,
                    'pendentes': pendentes_count,
                })

    treinamentos_por_lider.sort(key=lambda x: x['vigentes'] + x['pendentes'], reverse=True)
    treinamentos_por_lider = treinamentos_por_lider[:10]

    # Gráfico por Instrutor Responsável (baseado na matriz de responsabilidade)
    demanda_por_instrutor = []
    total_responsabilidades_treinamento = len(responsabilidades_registros)

    if total_responsabilidades_treinamento:
        demanda_por_escopo = (
            registros_unicos
            .exclude(procedimento__matriz__isnull=True)
            .exclude(procedimento__matriz__exact='')
            .values('procedimento__matriz', 'procedimento__sub_area', 'colaborador__turno')
            .annotate(
                vigentes=Count(
                    'id',
                    filter=vigentes_q
                ),
                pendentes=Count(
                    'id',
                    filter=pendentes_q
                )
            )
        )

        demanda_por_instrutor_map = {}
        for row in demanda_por_escopo:
            matriz_nome = (row.get('procedimento__matriz') or '').strip()
            sub_area_nome = (row.get('procedimento__sub_area') or '').strip()
            turno = row.get('colaborador__turno')
            responsavel = _resolve_responsavel_treinamento(
                responsabilidades_por_subarea,
                responsabilidades_gerais,
                matriz_nome,
                sub_area_nome,
                turno,
            )
            if not responsavel:
                continue

            item = demanda_por_instrutor_map.setdefault(
                responsavel.id,
                {
                    'nome': _abreviar_nome_dashboard(responsavel.nome_completo or f'Colaborador {responsavel.id}') or f'Colaborador {responsavel.id}',
                    'vigentes': 0,
                    'pendentes': 0,
                }
            )
            item['vigentes'] += int(row.get('vigentes') or 0)
            item['pendentes'] += int(row.get('pendentes') or 0)

        demanda_por_instrutor = sorted(
            demanda_por_instrutor_map.values(),
            key=lambda x: x['vigentes'] + x['pendentes'],
            reverse=True,
        )[:10]

    # Gráfico por Setor e Turno - evitar N+1: 1 query agregada
    treinamentos_por_setor_turno = []
    turno_dict = dict(TURNOS_CHOICES)

    combo_counts = (
        registros_unicos
        .filter(colaborador__setor_id__isnull=False)
        .values('colaborador__setor_id', 'colaborador__turno')
        .annotate(
            vigentes=Count(
                'id',
                filter=vigentes_q
            ),
            pendentes=Count(
                'id',
                filter=pendentes_q
            )
        )
    )

    setor_ids = list({row['colaborador__setor_id'] for row in combo_counts if row.get('colaborador__setor_id')})
    setores_dict = {s.id: s.nome for s in Setor.objects.filter(id__in=setor_ids)}

    for row in combo_counts:
        setor_id = row.get('colaborador__setor_id')
        turno = row.get('colaborador__turno')

        vigentes_count = int(row.get('vigentes') or 0)
        pendentes_count = int(row.get('pendentes') or 0)
        total = vigentes_count + pendentes_count
        if total <= 0:
            continue

        setor_nome = setores_dict.get(setor_id, 'Desconhecido')
        if len(setor_nome) > 20:
            setor_nome = setor_nome[:17] + '...'

        turno_label = turno_dict.get(turno, turno or 'N/A')
        treinamentos_por_setor_turno.append({
            'nome': f'{setor_nome} - {turno_label}'[:40],
            'vigentes': vigentes_count,
            'pendentes': pendentes_count,
        })

    treinamentos_por_setor_turno.sort(key=lambda x: x['vigentes'] + x['pendentes'], reverse=True)
    treinamentos_por_setor_turno = treinamentos_por_setor_turno[:10]

    planejamentos_filtrados = PlanejamentoTreinamento.objects.all()
    if filtro_setor_list:
        planejamentos_filtrados = planejamentos_filtrados.filter(colaboradores__setor_id__in=filtro_setor_list)
    if filtro_turno_list:
        planejamentos_filtrados = planejamentos_filtrados.filter(colaboradores__turno__in=filtro_turno_list)
    if filtro_lider_list:
        planejamentos_filtrados = planejamentos_filtrados.filter(colaboradores__lider_id__in=filtro_lider_list)
    if filtro_supervisor_list:
        planejamentos_filtrados = planejamentos_filtrados.filter(colaboradores__supervisor_id__in=filtro_supervisor_list)
    if filtro_gerente_list:
        planejamentos_filtrados = planejamentos_filtrados.filter(colaboradores__gerente_id__in=filtro_gerente_list)
    if filtro_criticidade_list:
        planejamentos_filtrados = planejamentos_filtrados.filter(procedimentos__criticidade__in=filtro_criticidade_list)
    if filtro_matriz_list:
        planejamentos_filtrados = planejamentos_filtrados.filter(procedimentos__matriz__in=filtro_matriz_list)
    if filtro_sub_area_list:
        planejamentos_filtrados = planejamentos_filtrados.filter(procedimentos__sub_area__in=filtro_sub_area_list)
    if filtro_instrutor_responsavel_ids:
        planejamentos_filtrados = planejamentos_filtrados.filter(instrutor_id__in=filtro_instrutor_responsavel_ids)
    if filtro_colaborador_id and filtro_colaborador_id.isdigit():
        planejamentos_filtrados = planejamentos_filtrados.filter(colaboradores__id=int(filtro_colaborador_id))
    elif filtro_colaborador_q:
        planejamentos_filtrados = planejamentos_filtrados.filter(
            Q(colaboradores__nome_completo__icontains=filtro_colaborador_q)
            | Q(colaboradores__matricula__icontains=filtro_colaborador_q)
        )

    planejamento_instrutor = (
        planejamentos_filtrados
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
    planejamento_instrutor = list(planejamento_instrutor)
    for item in planejamento_instrutor:
        item['nome_abreviado'] = _abreviar_nome_dashboard(item.get('instrutor__nome_completo'))

    # Planejamento por Setor/Turno (baseado no planejamento)
    planejamento_setor_turno_pl = (
        planejamentos_filtrados
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
    # Novo: lista de responsáveis por matriz/turno para o card
    responsaveis_matriz_turno = []
    for r in responsabilidades_registros:
        responsaveis_matriz_turno.append({
            'matriz': r.matriz.nome,
            'sub_area': r.sub_area.nome if r.sub_area_id else '-',
            'turno': dict(TURNOS_CHOICES).get(r.turno, r.turno),
            'colaborador': r.colaborador.nome_completo if r.colaborador else '-',
        })

    instrutores_responsaveis = []
    instrutores_responsaveis_ids = set()
    for responsabilidade in sorted(responsabilidades_registros, key=lambda item: item.colaborador.nome_completo if item.colaborador else ''):
        if responsabilidade.colaborador_id in instrutores_responsaveis_ids:
            continue
        instrutores_responsaveis_ids.add(responsabilidade.colaborador_id)
        instrutores_responsaveis.append({
            'id': responsabilidade.colaborador_id,
            'nome': responsabilidade.colaborador.nome_completo,
        })

    pendencias_dashboard = []
    epoch_date = date(1970, 1, 1)
    if colaborador_obj is not None and perfil_procedimentos_ids:
        procedimentos_pendentes = Procedimento.objects.filter(id__in=perfil_procedimentos_ids).order_by('codigo', 'nome')
        for procedimento in procedimentos_pendentes:
            ultimo_registro = ultimo_treinamento_por_procedimento.get(procedimento.id)
            if ultimo_registro and ultimo_registro.data_treinamento != epoch_date and ultimo_registro.status_treinamento == 'OK':
                continue

            responsavel = _resolve_responsavel_treinamento(
                responsabilidades_por_subarea,
                responsabilidades_gerais,
                procedimento.matriz,
                procedimento.sub_area,
                getattr(colaborador_obj, 'turno', None),
            )
            pendencias_dashboard.append({
                'colaborador': colaborador_obj.nome_completo,
                'matricula': colaborador_obj.matricula,
                'procedimento': procedimento.codigo,
                'procedimento_nome': getattr(procedimento, 'titulo', None) or procedimento.nome or '-',
                'matriz': procedimento.matriz or '-',
                'sub_area': procedimento.sub_area or '-',
                'instrutor_responsavel': responsavel.nome_completo if responsavel else '-',
                'ultimo_treinamento': ultimo_registro.data_treinamento.strftime('%d/%m/%Y') if ultimo_registro and ultimo_registro.data_treinamento and ultimo_registro.data_treinamento != epoch_date else 'Não iniciado',
            })
    else:
        pendencias_queryset = (
            registros_unicos
            .filter(pendentes_q)
            .select_related('colaborador', 'procedimento')
            .order_by(
                'procedimento__codigo',
                'procedimento__nome',
                'colaborador__nome_completo',
                'colaborador__matricula',
            )
        )
        for registro in pendencias_queryset:
            responsavel = _resolve_responsavel_treinamento(
                responsabilidades_por_subarea,
                responsabilidades_gerais,
                registro.procedimento.matriz,
                registro.procedimento.sub_area,
                getattr(registro.colaborador, 'turno', None),
            )
            pendencias_dashboard.append({
                'colaborador': registro.colaborador.nome_completo,
                'matricula': registro.colaborador.matricula,
                'procedimento': registro.procedimento.codigo,
                'procedimento_nome': getattr(registro.procedimento, 'titulo', None) or registro.procedimento.nome or '-',
                'matriz': registro.procedimento.matriz or '-',
                'sub_area': registro.procedimento.sub_area or '-',
                'instrutor_responsavel': responsavel.nome_completo if responsavel else '-',
                'ultimo_treinamento': registro.data_treinamento.strftime('%d/%m/%Y') if registro.data_treinamento else 'Não iniciado',
            })

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
        'demanda_por_instrutor': demanda_por_instrutor,
        'treinamentos_por_setor_turno': treinamentos_por_setor_turno,
        'planejamento_por_instrutor': planejamento_instrutor,
        'planejamento_por_setor_turno': list(planejamento_setor_turno_pl),
        'total_responsabilidades_treinamento': total_responsabilidades_treinamento,
        'responsaveis_matriz_turno': responsaveis_matriz_turno,
        'instrutores_responsaveis': instrutores_responsaveis,
        'pendencias_dashboard': pendencias_dashboard,
        'total_pendencias_dashboard': len(pendencias_dashboard),
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
    
    # Adicionar filtros selecionados ao contexto (como listas completas)
    context['filtro_setor_list'] = filtro_setor_list
    context['filtro_turno_list'] = filtro_turno_list
    context['filtro_lider_list'] = filtro_lider_list
    context['filtro_criticidade_list'] = filtro_criticidade_list
    context['filtro_matriz_list'] = filtro_matriz_list
    context['filtro_sub_area_list'] = filtro_sub_area_list
    context['filtro_instrutor_responsavel_list'] = filtro_instrutor_responsavel_list
    
    # Também adicionar os valores únicos para compatibilidade
    context['filtro_setor'] = filtro_setor
    context['filtro_turno'] = filtro_turno
    context['filtro_lider'] = filtro_lider
    context['filtro_criticidade'] = filtro_criticidade
    context['filtro_matriz'] = filtro_matriz
    context['filtro_sub_area'] = filtro_sub_area
    context['filtro_instrutor_responsavel'] = filtro_instrutor_responsavel
    context['filtro_colaborador_id'] = filtro_colaborador_id
    context['filtro_colaborador_q'] = filtro_colaborador_q
    
    # Cachear contexto por 5 minutos (300 segundos) - apenas sem filtros
    if not has_filters:
        cache.set(cache_key, context, 300)

    _paginate_dashboard_pendencias(request, context)
    
    return render(request, 'training/dashboard_treinamentos.html', context)


@login_required
def dashboard_treinamentos_filtered_view(request):
    """API para retornar dados filtrados do dashboard"""
    import json
    from django.http import JsonResponse
    from django.db.models import Count, Q, Exists, OuterRef, F
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

    # Definição unificada de status vigente e pendente (referência: data de aprovação do documento)
    vigentes_q = Q(data_treinamento__isnull=False) & (
        Q(procedimento__data_aprovacao__isnull=True) |
        Q(data_treinamento__gte=F('procedimento__data_aprovacao'))
    )
    pendentes_q = Q(data_treinamento__isnull=True) | (
        Q(procedimento__data_aprovacao__isnull=False) &
        Q(data_treinamento__lt=F('procedimento__data_aprovacao'))
    )

    # Novo: permitir filtrar por status (vigente / pendente)
    status_param = (request.GET.get('status') or '').strip().lower()
    if status_param == 'vigente':
        base_query &= vigentes_q
    elif status_param == 'pendente':
        base_query &= pendentes_q

    
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
    treinamentos_vigentes = treinamentos.filter(vigentes_q).count()
    treinamentos_pendentes = treinamentos.filter(pendentes_q).count()
    
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
            vigentes_q,
            colaborador_id__in=liderados_ids
        ).count()
        
        pendentes_count = treinamentos.filter(
            pendentes_q,
            colaborador_id__in=liderados_ids
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
                vigentes_q,
                colaborador__setor_id=setor_id,
                colaborador__turno=turno_val
            ).count()
            
            pendentes_count = treinamentos.filter(
                pendentes_q,
                colaborador__setor_id=setor_id,
                colaborador__turno=turno_val
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
    from procedures.models import ResponsavelTreinamentoMatriz

    responsabilidades_registros = list(
        ResponsavelTreinamentoMatriz.objects.select_related('matriz', 'sub_area', 'colaborador').filter(
            colaborador__isnull=False,
        )
    )
    responsabilidades_por_subarea, responsabilidades_gerais = _split_responsabilidades_treinamento(
        responsabilidades_registros
    )
    
    # Pegar filtros da query string (suportar múltiplos valores)
    turnos = request.GET.getlist('turno')
    setores = request.GET.getlist('setor')
    lideres = request.GET.getlist('lider')
    criticidades = request.GET.getlist('criticidade')
    matrizes = request.GET.getlist('matriz')
    sub_areas = request.GET.getlist('sub_area')
    instrutores_responsaveis = request.GET.getlist('instrutor_responsavel')
    colaborador_id = (request.GET.get('colaborador_id') or '').strip()
    colaborador_q = (request.GET.get('colaborador_q') or '').strip()
    
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
        setores_int = []
        try:
            setores_int = [int(s) for s in setores if s.strip()]
            if setores_int:
                base_query &= Q(colaborador__setor_id__in=setores_int)
        except:
            pass
    if lideres:
        lideres_int = []
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

    if instrutores_responsaveis:
        instrutores_responsaveis_ids = _coerce_int_list(instrutores_responsaveis)
        scope_rows = list(
            RegistroTreinamento.objects.filter(base_query)
            .values_list('procedimento__matriz', 'procedimento__sub_area', 'colaborador__turno')
            .distinct()
        )
        responsabilidades_scope_q = _build_responsavel_scope_q(
            responsabilidades_por_subarea,
            responsabilidades_gerais,
            scope_rows,
            instrutores_responsaveis_ids,
        )
        base_query &= responsabilidades_scope_q if responsabilidades_scope_q is not None else Q(pk__in=[])

    if colaborador_id and colaborador_id.isdigit():
        base_query &= Q(colaborador_id=int(colaborador_id))
    elif colaborador_q:
        base_query &= (
            Q(colaborador__nome_completo__icontains=colaborador_q)
            | Q(colaborador__matricula__icontains=colaborador_q)
        )

    # Se houver colaborador exato, e existir Perfil associado, exportar lista baseada no Perfil
    # (inclui procedimentos sem RegistroTreinamento), para bater com RH/Matriz.
    itens_export = None
    colaborador_obj = None
    if colaborador_id and colaborador_id.isdigit():
        colaborador_obj = Colaborador.objects.filter(
            id=int(colaborador_id),
            is_active=True,
            afastado=False,
            em_ferias=False,
        ).first()

    # Se filtros de colaborador foram aplicados, garantir que o colaborador escolhido respeita
    # (mesmo que ele não tenha registros).
    if colaborador_obj:
        try:
            if turnos and str(getattr(colaborador_obj, 'turno', '') or '') not in set(map(str, turnos)):
                colaborador_obj = None
        except Exception:
            pass

    if colaborador_obj and setores:
        try:
            setores_int_check = [int(s) for s in setores if str(s).strip().isdigit()]
            if setores_int_check and getattr(colaborador_obj, 'setor_id', None) not in setores_int_check:
                colaborador_obj = None
        except Exception:
            pass

    if colaborador_obj and lideres:
        try:
            lideres_int_check = [int(l) for l in lideres if str(l).strip().isdigit()]
            if lideres_int_check and getattr(colaborador_obj, 'lider_id', None) not in lideres_int_check:
                colaborador_obj = None
        except Exception:
            pass

    if colaborador_obj:
        try:
            from procedures.models import ColaboradorPerfil

            procedimentos_qs = Procedimento.objects.none()
            for cp in ColaboradorPerfil.objects.filter(colaborador_id=colaborador_obj.id, ativo=True).select_related('perfil'):
                procedimentos_qs = procedimentos_qs | cp.get_procedimentos_necessarios()
            procedimentos_qs = procedimentos_qs.distinct()

            # Respeitar filtros do procedimento
            if criticidades:
                criticidades_clean = [c for c in criticidades if str(c).strip()]
                if criticidades_clean:
                    procedimentos_qs = procedimentos_qs.filter(criticidade__in=criticidades_clean)
            if matrizes:
                matrizes_clean = [m for m in matrizes if str(m).strip()]
                if matrizes_clean:
                    procedimentos_qs = procedimentos_qs.filter(matriz__in=matrizes_clean)
            if sub_areas:
                sub_areas_clean = [sa for sa in sub_areas if str(sa).strip()]
                if sub_areas_clean:
                    procedimentos_qs = procedimentos_qs.filter(sub_area__in=sub_areas_clean)
            if instrutores_responsaveis:
                procedimentos_ids_permitidos = []
                for procedimento_id, matriz_nome, sub_area_nome in procedimentos_qs.values_list('id', 'matriz', 'sub_area'):
                    responsavel = _resolve_responsavel_treinamento(
                        responsabilidades_por_subarea,
                        responsabilidades_gerais,
                        matriz_nome,
                        sub_area_nome,
                        getattr(colaborador_obj, 'turno', None),
                    )
                    if responsavel and responsavel.id in instrutores_responsaveis_ids:
                        procedimentos_ids_permitidos.append(procedimento_id)
                procedimentos_qs = procedimentos_qs.filter(id__in=procedimentos_ids_permitidos) if procedimentos_ids_permitidos else procedimentos_qs.none()

            procedimentos_ids = list(procedimentos_qs.values_list('id', flat=True))
            if procedimentos_ids:
                EPOCH_DATE = date(1970, 1, 1)
                ultimo_treinamento_por_procedimento = {}

                treinamentos_qs = RegistroTreinamento.objects.filter(
                    base_query,
                    colaborador_id=colaborador_obj.id,
                    procedimento_id__in=procedimentos_ids,
                ).select_related('procedimento').order_by('-data_treinamento', '-id')

                for t in treinamentos_qs:
                    proc_id = t.procedimento_id
                    if proc_id in ultimo_treinamento_por_procedimento:
                        continue
                    if not t.data_treinamento:
                        continue
                    if t.data_treinamento == EPOCH_DATE:
                        continue
                    ultimo_treinamento_por_procedimento[proc_id] = t

                for t in treinamentos_qs:
                    proc_id = t.procedimento_id
                    if proc_id in ultimo_treinamento_por_procedimento:
                        continue
                    if t.data_treinamento:
                        continue
                    ultimo_treinamento_por_procedimento[proc_id] = t

                itens_export = []
                for proc in procedimentos_qs.order_by('codigo'):
                    t = ultimo_treinamento_por_procedimento.get(proc.id)
                    if t is None:
                        t = RegistroTreinamento(
                            colaborador=colaborador_obj,
                            procedimento=proc,
                            ativo=True,
                            data_treinamento=None,
                            revisao_treinada=None,
                        )
                    itens_export.append(t)
        except Exception:
            itens_export = None

    # Fallback: exportar TODOS os registros (não paginar)
    registros = itens_export if isinstance(itens_export, list) else RegistroTreinamento.objects.filter(base_query).select_related(
        'colaborador', 'procedimento'
    )

    # No modo queryset, manter consistência com o dashboard: apenas itens associados a algum perfil ativo
    if not isinstance(registros, list):
        from django.db.models import Exists, OuterRef
        from procedures.models import ColaboradorPerfil

        perfil_exists_qs = ColaboradorPerfil.objects.filter(
            colaborador_id=OuterRef('colaborador_id'),
            ativo=True,
            perfil__grupos__subgrupos__procedimentos=OuterRef('procedimento_id'),
        )
        registros = registros.annotate(_associado_perfil=Exists(perfil_exists_qs)).filter(_associado_perfil=True)

    registros = registros if isinstance(registros, list) else registros.order_by('-data_treinamento', '-id')
    
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
        if treinamento.status_treinamento == 'OK':
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


@login_required
def colaboradores_autocomplete_view(request):
    """Retorna sugestões de colaboradores (RH) para autocomplete (nome/matrícula)."""
    q = (request.GET.get('q') or '').strip()
    try:
        limit = int(request.GET.get('limit') or 20)
    except Exception:
        limit = 20
    limit = max(1, min(limit, 50))

    if len(q) < 2:
        return JsonResponse({"results": []})

    qs = Colaborador.objects.filter(
        is_active=True,
        afastado=False,
        em_ferias=False,
    ).filter(
        Q(nome_completo__icontains=q) | Q(matricula__icontains=q)
    ).order_by('nome_completo')

    results = list(qs.values('id', 'nome_completo', 'matricula')[:limit])
    return JsonResponse({"results": results})
