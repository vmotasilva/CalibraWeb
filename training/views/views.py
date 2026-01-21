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
    
    # Cache key para estatísticas do dashboard
    cache_key = 'dashboard_treinamentos_stats'
    cached_data = cache.get(cache_key)
    
    if cached_data:
        return render(request, 'training/dashboard_treinamentos.html', cached_data)
    
    # Base query: apenas registros com colaborador e procedimento vinculados E ATIVOS E NÃO AFASTADOS
    valid_registros = RegistroTreinamento.objects.filter(
        colaborador__isnull=False,
        colaborador__is_active=True,
        colaborador__afastado=False,
        procedimento__isnull=False,
        ativo=True
    ).select_related('colaborador', 'procedimento', 'procedimento__revisao_atual')
    
    # Estatísticas gerais usando queries SQL otimizadas
    total_treinamentos = valid_registros.count()
    
    # Treinamentos vigentes: têm data E revisão coincide
    # OTIMIZAÇÃO: Usar query SQL ao invés de carregar tudo na memória
    treinamentos_vigentes = valid_registros.filter(
        data_treinamento__isnull=False,
        revisao_treinada=F('procedimento__revisao_atual')
    ).count()
    
    # Pendentes: sem data OU revisão desatualizada
    treinamentos_pendentes = valid_registros.filter(
        Q(data_treinamento__isnull=True) | 
        ~Q(revisao_treinada=F('procedimento__revisao_atual'))
    ).count()
    
    # Colaboradores com treinamentos vigentes (com data e revisão OK)
    total_colaboradores_treinados = valid_registros.filter(
        data_treinamento__isnull=False,
        revisao_treinada=F('procedimento__revisao_atual')
    ).values('colaborador_id').distinct().count()
    
    # Procedimentos únicos treinados
    total_procedimentos_unicos = valid_registros.filter(
        data_treinamento__isnull=False,
        revisao_treinada=F('procedimento__revisao_atual')
    ).values('procedimento_id').distinct().count()
    
    # Treinamentos nos últimos 30 dias
    data_30_dias_atras = date.today() - timedelta(days=30)
    treinamentos_ultimos_30_dias = valid_registros.filter(
        data_treinamento__gte=data_30_dias_atras,
        data_treinamento__isnull=False
    ).count()
    
    # Top 10 procedimentos mais treinados - OTIMIZADO com agregação SQL
    top_procedimentos = valid_registros.filter(
        data_treinamento__isnull=False,
        revisao_treinada=F('procedimento__revisao_atual')
    ).values('procedimento__codigo', 'procedimento__nome').annotate(
        total=Count('id')
    ).order_by('-total')[:10]
    
    # Top 10 colaboradores com mais treinamentos - OTIMIZADO com agregação SQL
    top_colaboradores = valid_registros.filter(
        data_treinamento__isnull=False,
        revisao_treinada=F('procedimento__revisao_atual')
    ).values('colaborador__nome_completo').annotate(
        total=Count('id')
    ).order_by('-total')[:10]
    
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
    
    # Treinamentos por mês (últimos 6 meses) - OTIMIZADO: query única com agregação
    from django.db.models import Case, When, IntegerField
    from django.db.models.functions import TruncMonth
    
    treinamentos_por_mes = []
    for i in range(5, -1, -1):
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
        
        # Contar vigentes e pendentes com queries SQL otimizadas
        vigentes = valid_registros.filter(
            colaborador_id__in=liderados_ids,
            data_treinamento__isnull=False,
            revisao_treinada=F('procedimento__revisao_atual')
        ).count()
        
        pendentes = valid_registros.filter(
            colaborador_id__in=liderados_ids
        ).filter(
            Q(data_treinamento__isnull=True) | 
            ~Q(revisao_treinada=F('procedimento__revisao_atual'))
        ).count()
        
        total = vigentes + pendentes
        if total > 0:
            # Abreviar nome
            parts = lider.nome_completo.split()
            nome_abrev = f"{parts[0]} {parts[-1]}" if len(parts) > 1 else lider.nome_completo[:30]
            
            treinamentos_por_lider.append({
                'nome': nome_abrev,
                'vigentes': vigentes,
                'pendentes': pendentes
            })
    
    # Ordenar por total e limitar a 10
    treinamentos_por_lider.sort(key=lambda x: x['vigentes'] + x['pendentes'], reverse=True)
    treinamentos_por_lider = treinamentos_por_lider[:10]
    
    # Gráfico por Setor e Turno - OTIMIZADO com agregação
    from organization.models import Setor
    treinamentos_por_setor_turno = []
    
    # Query otimizada: buscar combinações de setor+turno com agregação
    combinacoes = valid_registros.values(
        'colaborador__setor_id', 
        'colaborador__turno'
    ).annotate(
        vigentes=Count('id', filter=Q(
            data_treinamento__isnull=False,
            revisao_treinada=F('procedimento__revisao_atual')
        )),
        pendentes=Count('id', filter=Q(
            Q(data_treinamento__isnull=True) | 
            ~Q(revisao_treinada=F('procedimento__revisao_atual'))
        ))
    ).filter(
        colaborador__setor_id__isnull=False
    ).order_by('-vigentes', '-pendentes')[:15]  # Top 15 combinações
    
    # Buscar setores uma única vez
    setor_ids = [c['colaborador__setor_id'] for c in combinacoes]
    setores_dict = {s.id: s.nome for s in Setor.objects.filter(id__in=setor_ids)}
    turno_dict = dict(TURNOS_CHOICES)
    
    for combo in combinacoes:
        setor_id = combo['colaborador__setor_id']
        turno = combo['colaborador__turno']
        vigentes = combo['vigentes']
        pendentes = combo['pendentes']
        
        total = vigentes + pendentes
        if total > 0:
            setor_nome = setores_dict.get(setor_id, 'Desconhecido')
            if len(setor_nome) > 20:
                setor_nome = setor_nome[:17] + '...'
            
            turno_label = turno_dict.get(turno, turno or 'N/A')
            
            treinamentos_por_setor_turno.append({
                'nome': f'{setor_nome} - {turno_label}'[:40],
                'vigentes': vigentes,
                'pendentes': pendentes
            })
    
    # Montar contexto
    context = {
        'total_treinamentos': total_treinamentos,
        'treinamentos_vigentes': treinamentos_vigentes,
        'treinamentos_pendentes': treinamentos_pendentes,
        'total_colaboradores_treinados': total_colaboradores_treinados,
        'total_procedimentos_unicos': total_procedimentos_unicos,
        'treinamentos_ultimos_30_dias': treinamentos_ultimos_30_dias,
        'taxa_conformidade': taxa_conformidade,
        'top_procedimentos': list(top_procedimentos),
        'top_colaboradores': list(top_colaboradores),
        'status_distribuicao': status_distribuicao,
        'treinamentos_por_mes': treinamentos_por_mes,
        'treinamentos_por_lider': treinamentos_por_lider,
        'treinamentos_por_setor_turno': treinamentos_por_setor_turno,
    }
    
    # Adicionar dados de filtros dinâmicos - OTIMIZADO
    from organization.models import Setor
    
    # Setores com colaboradores ativos
    setores = Setor.objects.filter(
        colaborador__is_active=True,
        colaborador__afastado=False
    ).distinct().order_by('nome').values('id', 'nome')
    context['setores'] = list(setores)
    
    # Turnos
    context['turnos'] = [{'value': t[0], 'label': t[1]} for t in TURNOS_CHOICES]
    
    # Líderes com liderados ativos - OTIMIZADO
    lideres = Colaborador.objects.filter(
        liderados__isnull=False,
        liderados__is_active=True,
        is_active=True,
        afastado=False
    ).distinct().order_by('nome_completo').values('id', 'nome_completo')
    context['lideres'] = [{'id': l['id'], 'nome': l['nome_completo']} for l in lideres]
    
    # Supervisores - OTIMIZADO
    supervisores = Colaborador.objects.filter(
        supervisionados__isnull=False,
        supervisionados__is_active=True,
        is_active=True,
        afastado=False
    ).distinct().order_by('nome_completo').values('id', 'nome_completo')
    context['supervisores'] = [{'id': s['id'], 'nome': s['nome_completo']} for s in supervisores]
    
    # Gerentes - OTIMIZADO
    gerentes = Colaborador.objects.filter(
        gerenciados__isnull=False,
        gerenciados__is_active=True,
        is_active=True,
        afastado=False
    ).distinct().order_by('nome_completo').values('id', 'nome_completo')
    context['gerentes'] = [{'id': g['id'], 'nome': g['nome_completo']} for g in gerentes]
    
    # Tabela de dados com paginação - OTIMIZADO: apenas valores necessários
    registros_query = valid_registros.order_by('-data_treinamento', '-id').values(
        'id', 'colaborador__id', 'colaborador__nome_completo', 
        'procedimento__codigo', 'procedimento__nome', 'data_treinamento',
        'revisao_treinada', 'procedimento__revisao_atual'
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
        elif registro['revisao_treinada'] == registro['procedimento__revisao_atual']:
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
    
    # Cachear contexto por 5 minutos (300 segundos)
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
    
    # Base query - apenas registros com colaborador ATIVO (não afastado), procedimento não nulos E ativo=True
    base_query = Q(
        colaborador__isnull=False,
        colaborador__is_active=True,
        colaborador__afastado=False,  # Não contar treinamentos de colaboradores afastados
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
    
    # Contar registros
    treinamentos = RegistroTreinamento.objects.filter(base_query).distinct()
    total_treinamentos = treinamentos.count()
    treinamentos_vigentes = treinamentos.filter(data_treinamento__isnull=False).count()
    treinamentos_pendentes = treinamentos.filter(data_treinamento__isnull=True).count()
    
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
    
    # Gráfico por mês
    treinamentos_por_mes = []
    for i in range(5, -1, -1):
        data_inicio = date.today() - timedelta(days=30 * (i + 1))
        data_fim = date.today() - timedelta(days=30 * i)
        
        count = treinamentos.filter(
            data_treinamento__gte=data_inicio,
            data_treinamento__lt=data_fim,
            data_treinamento__isnull=False
        ).count()
        
        treinamentos_por_mes.append({
            'mes': data_inicio.strftime('%b/%y'),
            'total': count
        })
    
    # Gráfico por Líder (considerando filtros aplicados)
    treinamentos_por_lider = []
    líderes_q = Colaborador.objects.filter(
        liderados__isnull=False,
        liderados__is_active=True
    ).distinct().order_by('nome_completo')
    
    for lider in líderes_q:
        liderados_ids = lider.liderados.filter(is_active=True).values_list('id', flat=True)
        
        vigentes = RegistroTreinamento.objects.filter(
            colaborador_id__in=liderados_ids,
            data_treinamento__isnull=False,
            ativo=True
        ).filter(base_query).count()
        
        pendentes = RegistroTreinamento.objects.filter(
            colaborador_id__in=liderados_ids,
            data_treinamento__isnull=True,
            ativo=True
        ).filter(base_query).count()
        
        total = vigentes + pendentes
        if total > 0:
            parts = lider.nome_completo.split()
            if len(parts) > 1:
                nome_abrev = f"{parts[0]} {parts[-1]}"
            else:
                nome_abrev = lider.nome_completo[:30]
            
            treinamentos_por_lider.append({
                'nome': nome_abrev,
                'vigentes': vigentes,
                'pendentes': pendentes
            })
    
    treinamentos_por_lider.sort(key=lambda x: x['vigentes'] + x['pendentes'], reverse=True)
    treinamentos_por_lider = treinamentos_por_lider[:10]
    
    # Gráfico por Setor e Turno (considerando filtros aplicados)
    treinamentos_por_setor_turno = []
    from organization.models import Setor
    from core.models import TURNOS_CHOICES
    
    combinacoes = Colaborador.objects.filter(
        setor__isnull=False,
        is_active=True
    ).values_list('setor_id', 'turno').distinct()
    
    for setor_id, turno_val in combinacoes:
        try:
            setor = Setor.objects.get(id=setor_id)
            
            colaboradores_ids = Colaborador.objects.filter(
                setor_id=setor_id,
                turno=turno_val,
                is_active=True
            ).values_list('id', flat=True)
            
            vigentes = RegistroTreinamento.objects.filter(
                colaborador_id__in=colaboradores_ids,
                data_treinamento__isnull=False,
                ativo=True
            ).filter(base_query).count()
            
            pendentes = RegistroTreinamento.objects.filter(
                colaborador_id__in=colaboradores_ids,
                data_treinamento__isnull=True,
                ativo=True
            ).filter(base_query).count()
            
            total = vigentes + pendentes
            if total > 0:
                turno_dict = dict(TURNOS_CHOICES)
                turno_label = turno_dict.get(turno_val, turno_val)
                
                setor_nome = setor.nome
                if len(setor_nome) > 20:
                    setor_nome = setor_nome[:17] + '...'
                
                treinamentos_por_setor_turno.append({
                    'nome': f'{setor_nome} - {turno_label}'[:40],
                    'vigentes': vigentes,
                    'pendentes': pendentes
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
        'taxa_conformidade': taxa_conformidade,
        'status_distribuicao': status_distribuicao,
        'treinamentos_por_mes': treinamentos_por_mes,
        'treinamentos_por_lider': treinamentos_por_lider,
        'treinamentos_por_setor_turno': treinamentos_por_setor_turno,
        'dados_tabela': dados_tabela_list
    })
