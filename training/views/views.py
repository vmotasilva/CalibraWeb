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
    """Dashboard completo de treinamentos com estatísticas e gráficos"""
    from django.db.models import Count, Q, Exists, OuterRef
    from datetime import timedelta, date
    from core.models import TURNOS_CHOICES
    
    # Base query: apenas registros com colaborador e procedimento vinculados E ATIVOS E NÃO AFASTADOS
    def get_valid_registros():
        """Retorna apenas registros com colaborador ATIVO (não afastado), procedimento não nulos E ativo=True"""
        return RegistroTreinamento.objects.filter(
            colaborador__isnull=False,
            colaborador__is_active=True,
            colaborador__afastado=False,  # Não contar treinamentos de colaboradores afastados
            procedimento__isnull=False,
            ativo=True
        ).distinct()
    
    # Estatísticas gerais - apenas registros válidos E ativos
    valid_registros = get_valid_registros()
    total_treinamentos = valid_registros.count()
    
    # ⚠️ IMPORTANTE: Usar property status_treinamento ao invés de data_treinamento__isnull
    # Porque status_treinamento é calculado dinamicamente baseado em revisão_treinada + data_treinamento
    # Contar em Python após fetch para não quebrar a property
    registros_list = list(valid_registros)
    treinamentos_vigentes = sum(1 for r in registros_list if r.status_treinamento == 'OK')
    # NAO_INICIADO também é considerado pendente (não treinado ainda)
    treinamentos_pendentes = sum(1 for r in registros_list if r.status_treinamento in ('PENDENTE', 'NAO_INICIADO'))
    
    # Colaboradores com treinamentos (com status OK)
    total_colaboradores_treinados = len(set(
        r.colaborador_id for r in registros_list if r.status_treinamento == 'OK'
    ))
    
    # Procedimentos únicos treinados (com status OK)
    total_procedimentos_unicos = len(set(
        r.procedimento_id for r in registros_list if r.status_treinamento == 'OK'
    ))
    
    # Treinamentos nos últimos 30 dias (com status OK)
    data_30_dias_atras = date.today() - timedelta(days=30)
    treinamentos_ultimos_30_dias = sum(
        1 for r in registros_list 
        if r.status_treinamento == 'OK' and r.data_treinamento and r.data_treinamento >= data_30_dias_atras
    )
    
    # Top 10 procedimentos mais treinados (com status OK)
    from collections import Counter
    proc_counter = Counter(
        r.procedimento.codigo for r in registros_list if r.status_treinamento == 'OK' and r.procedimento
    )
    top_procedimentos = [
        {'procedimento__codigo': codigo, 'procedimento__nome': codigo, 'total': count}
        for codigo, count in proc_counter.most_common(10)
    ]
    
    # Top 10 colaboradores com mais treinamentos (com status OK)
    colab_counter = Counter(
        r.colaborador.nome_completo for r in registros_list if r.status_treinamento == 'OK' and r.colaborador
    )
    top_colaboradores = [
        {'colaborador__nome_completo': nome, 'total': count}
        for nome, count in colab_counter.most_common(10)
    ]
    
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
    
    # Treinamentos por mês (últimos 6 meses)
    treinamentos_por_mes = []
    for i in range(5, -1, -1):
        data_inicio = date.today() - timedelta(days=30 * (i + 1))
        data_fim = date.today() - timedelta(days=30 * i)
        
        count = RegistroTreinamento.objects.filter(
            data_treinamento__gte=data_inicio,
            data_treinamento__lt=data_fim,
            data_treinamento__isnull=False,
            ativo=True
        ).count()
        
        treinamentos_por_mes.append({
            'mes': data_inicio.strftime('%b/%y'),
            'total': count
        })
    
    # Gráfico por Líder: contar todos os colaboradores que têm esse líder
    treinamentos_por_lider = []
    líderes = Colaborador.objects.filter(
        liderados__isnull=False, 
        liderados__is_active=True
    ).distinct().order_by('nome_completo')
    
    for lider in líderes:
        # Pegar todos os liderados ativos deste líder
        liderados_ids = lider.liderados.filter(is_active=True).values_list('id', flat=True)
        
        # Contar registros de treinamento ATIVOS usando status_treinamento
        registros_lider = RegistroTreinamento.objects.filter(
            colaborador_id__in=liderados_ids,
            ativo=True
        )
        registros_lider_list = list(registros_lider)
        vigentes = sum(1 for r in registros_lider_list if r.status_treinamento == 'OK')
        # NAO_INICIADO também é pendente (não treinado ainda)
        pendentes = sum(1 for r in registros_lider_list if r.status_treinamento in ('PENDENTE', 'NAO_INICIADO'))
        
        # Incluir se tem qualquer registro
        total = vigentes + pendentes
        if total > 0:
            # Abreviar nome: primeira palavra + última palavra (ex: "EDUARDO SILVA")
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
    
    # Ordenar por total descendente e pegar top 10
    treinamentos_por_lider.sort(key=lambda x: x['vigentes'] + x['pendentes'], reverse=True)
    treinamentos_por_lider = treinamentos_por_lider[:10]
    
    # Gráfico por Setor e Turno: agrupar colaboradores por setor+turno
    treinamentos_por_setor_turno = []
    
    # Pegar combinações únicas de setor + turno
    combinacoes = Colaborador.objects.filter(
        setor__isnull=False,
        is_active=True
    ).values_list('setor_id', 'turno').distinct()
    
    for setor_id, turno in combinacoes:
        from organization.models import Setor
        try:
            setor = Setor.objects.get(id=setor_id)
            
            # Pegar todos os colaboradores ativos neste setor e turno
            colaboradores_ids = Colaborador.objects.filter(
                setor_id=setor_id,
                turno=turno,
                is_active=True
            ).values_list('id', flat=True)
            
            # Contar registros de treinamento usando status_treinamento
            registros_setor = RegistroTreinamento.objects.filter(
                colaborador_id__in=colaboradores_ids,
                ativo=True
            )
            registros_setor_list = list(registros_setor)
            vigentes = sum(1 for r in registros_setor_list if r.status_treinamento == 'OK')
            # NAO_INICIADO também é pendente (não treinado ainda)
            pendentes = sum(1 for r in registros_setor_list if r.status_treinamento in ('PENDENTE', 'NAO_INICIADO'))
            
            # Incluir se tem qualquer registro
            total = vigentes + pendentes
            if total > 0:
                # Mapear turno para label legível usando TURNOS_CHOICES
                turno_dict = dict(TURNOS_CHOICES)
                turno_label = turno_dict.get(turno, turno)
                
                # Abreviar nome do setor se necessário
                setor_nome = setor.nome
                if len(setor_nome) > 20:
                    setor_nome = setor_nome[:17] + '...'
                
                treinamentos_por_setor_turno.append({
                    'nome': f'{setor_nome} - {turno_label}'[:40],
                    'vigentes': vigentes,
                    'pendentes': pendentes
                })
        except Exception as e:
            pass
    
    # Ordenar por total descendente e pegar top 10
    treinamentos_por_setor_turno.sort(key=lambda x: x['vigentes'] + x['pendentes'], reverse=True)
    treinamentos_por_setor_turno = treinamentos_por_setor_turno[:10]
    
    context = {
        'total_treinamentos': total_treinamentos,
        'treinamentos_vigentes': treinamentos_vigentes,
        'treinamentos_pendentes': treinamentos_pendentes,
        'total_colaboradores_treinados': total_colaboradores_treinados,
        'total_procedimentos_unicos': total_procedimentos_unicos,
        'treinamentos_ultimos_30_dias': treinamentos_ultimos_30_dias,
        'taxa_conformidade': taxa_conformidade,
        'top_procedimentos': top_procedimentos,
        'top_colaboradores': top_colaboradores,
        'status_distribuicao': status_distribuicao,
        'treinamentos_por_mes': treinamentos_por_mes,
        'treinamentos_por_lider': treinamentos_por_lider,
        'treinamentos_por_setor_turno': treinamentos_por_setor_turno,
    }
    
    # Adicionar dados de filtros dinâmicos
    from organization.models import Setor
    from core.models import TURNOS_CHOICES
    
    # Setores
    setores = Setor.objects.filter(
        colaborador__is_active=True,
        colaborador__afastado=False
    ).distinct().order_by('nome').values_list('id', 'nome')
    context['setores'] = [{'id': s[0], 'nome': s[1]} for s in setores]
    
    # Turnos
    context['turnos'] = [{'value': t[0], 'label': t[1]} for t in TURNOS_CHOICES]
    
    # Líderes
    lideres = Colaborador.objects.filter(
        liderados__isnull=False,
        liderados__is_active=True,
        is_active=True,
        afastado=False
    ).distinct().order_by('nome_completo').values_list('id', 'nome_completo')
    context['lideres'] = [{'id': l[0], 'nome': l[1]} for l in lideres]
    
    # Supervisores
    supervisores = Colaborador.objects.filter(
        supervisionados__isnull=False,
        supervisionados__is_active=True,
        is_active=True,
        afastado=False
    ).distinct().order_by('nome_completo').values_list('id', 'nome_completo')
    context['supervisores'] = [{'id': s[0], 'nome': s[1]} for s in supervisores]
    
    # Gerentes
    gerentes = Colaborador.objects.filter(
        gerenciados__isnull=False,
        gerenciados__is_active=True,
        is_active=True,
        afastado=False
    ).distinct().order_by('nome_completo').values_list('id', 'nome_completo')
    context['gerentes'] = [{'id': g[0], 'nome': g[1]} for g in gerentes]
    
    # Tabela de dados com paginação
    registros_query = valid_registros.select_related(
        'colaborador', 'procedimento'
    ).order_by('-data_treinamento', '-id').values(
        'id', 'colaborador__id', 'colaborador__nome_completo', 'procedimento__codigo',
        'procedimento__nome', 'data_treinamento'
    )
    
    # Paginar com 15 registros por página
    page_number = request.GET.get('page', '1')
    paginator = Paginator(registros_query, 15)
    page_obj = paginator.get_page(page_number)
    
    # Processar dados da tabela para o template
    dados_processados = []
    for registro in page_obj.object_list:
        dados_processados.append({
            'id': registro['id'],
            'colaborador_id': registro['colaborador__id'],
            'colaborador': registro['colaborador__nome_completo'],
            'procedimento': registro['procedimento__codigo'],
            'procedimento_nome': registro['procedimento__nome'][:40],
            'data': registro['data_treinamento'].strftime('%d/%m/%Y') if registro['data_treinamento'] else 'Pendente'
        })
    
    context['dados_tabela'] = dados_processados
    context['page_obj'] = page_obj
    context['paginator'] = paginator
    
    # ===== GRÁFICOS DE PLANEJAMENTOS =====
    from procedures.models import PlanejamentoTreinamento
    from django.utils import timezone
    from dateutil.relativedelta import relativedelta
    
    # Pegar período do request (default: últimos 3 meses)
    periodo_meses = int(request.GET.get('periodo_planejamento', 3))
    data_inicio_planejamento = date.today() - relativedelta(months=periodo_meses)
    
    # Adicionar ao context para o form
    context['periodo_planejamento'] = periodo_meses
    
    # Filtrar planejamentos no período
    planejamentos = PlanejamentoTreinamento.objects.filter(
        data_prevista__gte=data_inicio_planejamento,
        data_prevista__lte=date.today() + timedelta(days=365)  # 1 ano no futuro
    )
    
    # ===== GRÁFICO 1: Por Setor e Turno =====
    planejamentos_setor_turno = {}
    
    for planejamento in planejamentos:
        for colaborador in planejamento.colaboradores.all():
            setor = colaborador.setor
            turno = colaborador.turno
            
            if not setor:
                continue
            
            # Criar chave
            chave = f"{setor.nome} - {turno}"
            
            if chave not in planejamentos_setor_turno:
                planejamentos_setor_turno[chave] = {
                    'nome': chave,
                    'no_prazo': 0,
                    'fora_prazo': 0,
                    'cancelados': 0,
                    'concluidos': 0
                }
            
            # Categorizar planejamento
            if planejamento.status == 'CANCELADO':
                planejamentos_setor_turno[chave]['cancelados'] += 1
            elif planejamento.status == 'REALIZADO':
                planejamentos_setor_turno[chave]['concluidos'] += 1
            elif planejamento.status in ['PLANEJADO', 'CONFIRMADO']:
                if planejamento.data_prevista >= date.today():
                    planejamentos_setor_turno[chave]['no_prazo'] += 1
                else:
                    planejamentos_setor_turno[chave]['fora_prazo'] += 1
    
    # Converter para lista e ordenar
    planejamentos_setor_turno_lista = list(planejamentos_setor_turno.values())
    planejamentos_setor_turno_lista.sort(
        key=lambda x: x['no_prazo'] + x['fora_prazo'] + x['cancelados'] + x['concluidos'],
        reverse=True
    )
    planejamentos_setor_turno_lista = planejamentos_setor_turno_lista[:15]  # Top 15
    
    context['planejamentos_setor_turno'] = planejamentos_setor_turno_lista
    
    # ===== GRÁFICO 2: Por Instrutor =====
    planejamentos_instrutor = {}
    
    for planejamento in planejamentos:
        if not planejamento.instrutor:
            continue
        
        instrutor_nome = planejamento.instrutor.nome_completo
        
        if instrutor_nome not in planejamentos_instrutor:
            planejamentos_instrutor[instrutor_nome] = {
                'nome': instrutor_nome,
                'no_prazo': 0,
                'fora_prazo': 0,
                'cancelados': 0,
                'concluidos': 0
            }
        
        # Categorizar planejamento
        if planejamento.status == 'CANCELADO':
            planejamentos_instrutor[instrutor_nome]['cancelados'] += 1
        elif planejamento.status == 'REALIZADO':
            planejamentos_instrutor[instrutor_nome]['concluidos'] += 1
        elif planejamento.status in ['PLANEJADO', 'CONFIRMADO']:
            if planejamento.data_prevista >= date.today():
                planejamentos_instrutor[instrutor_nome]['no_prazo'] += 1
            else:
                planejamentos_instrutor[instrutor_nome]['fora_prazo'] += 1
    
    # Converter para lista e ordenar
    planejamentos_instrutor_lista = list(planejamentos_instrutor.values())
    planejamentos_instrutor_lista.sort(
        key=lambda x: x['no_prazo'] + x['fora_prazo'] + x['cancelados'] + x['concluidos'],
        reverse=True
    )
    planejamentos_instrutor_lista = planejamentos_instrutor_lista[:15]  # Top 15
    
    context['planejamentos_instrutor'] = planejamentos_instrutor_lista
    
    return render(request, 'procedures/dashboard_treinamentos.html', context)


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
