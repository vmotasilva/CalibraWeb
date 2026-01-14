# -*- coding: utf-8 -*-
"""
Views para o módulo Training (Treinamentos e Procedimentos)
"""

import io
from datetime import date
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
from procedures.models import Procedimento, RegistroTreinamento
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
    
    # Filtro por status - filtrando em Python (é uma property, não field direto)
    if status:
        all_records = list(qs)
        qs = [t for t in all_records if t.status_treinamento == status]
    
    # Ordenar resultados
    if isinstance(qs, list):
        treinamentos = sorted(qs, key=lambda x: x.data_treinamento, reverse=True)[:100]
    else:
        treinamentos = qs.order_by('-data_treinamento')[:100]
    
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
    from django.db.models import Count, Q
    from datetime import timedelta, date
    from core.models import TURNOS_CHOICES
    
    # Estatísticas gerais
    total_treinamentos = RegistroTreinamento.objects.count()
    
    treinamentos_vigentes = RegistroTreinamento.objects.filter(
        data_treinamento__isnull=False
    ).count()
    
    treinamentos_pendentes = RegistroTreinamento.objects.filter(
        data_treinamento__isnull=True
    ).count()
    
    # Colaboradores com treinamentos
    total_colaboradores_treinados = RegistroTreinamento.objects.filter(
        data_treinamento__isnull=False
    ).values('colaborador').distinct().count()
    
    # Procedimentos únicos treinados
    total_procedimentos_unicos = RegistroTreinamento.objects.filter(
        data_treinamento__isnull=False
    ).values('procedimento').distinct().count()
    
    # Treinamentos nos últimos 30 dias
    data_30_dias_atras = date.today() - timedelta(days=30)
    treinamentos_ultimos_30_dias = RegistroTreinamento.objects.filter(
        data_treinamento__gte=data_30_dias_atras,
        data_treinamento__isnull=False
    ).count()
    
    # Top 10 procedimentos mais treinados
    top_procedimentos = RegistroTreinamento.objects.filter(
        data_treinamento__isnull=False
    ).values('procedimento__codigo', 'procedimento__nome').annotate(
        total=Count('id')
    ).order_by('-total')[:10]
    
    # Top 10 colaboradores com mais treinamentos
    top_colaboradores = RegistroTreinamento.objects.filter(
        data_treinamento__isnull=False
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
    
    # Treinamentos por mês (últimos 6 meses)
    treinamentos_por_mes = []
    for i in range(5, -1, -1):
        data_inicio = date.today() - timedelta(days=30 * (i + 1))
        data_fim = date.today() - timedelta(days=30 * i)
        
        count = RegistroTreinamento.objects.filter(
            data_treinamento__gte=data_inicio,
            data_treinamento__lt=data_fim,
            data_treinamento__isnull=False
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
        
        # Contar registros de treinamento
        vigentes = RegistroTreinamento.objects.filter(
            colaborador_id__in=liderados_ids,
            data_treinamento__isnull=False
        ).count()
        pendentes = RegistroTreinamento.objects.filter(
            colaborador_id__in=liderados_ids,
            data_treinamento__isnull=True
        ).count()
        
        # Incluir se tem qualquer registro
        total = vigentes + pendentes
        if total > 0:
            # Abreviar nome: primeira inicial + última inicial (ex: "E. S.")
            parts = lider.nome_completo.split()
            if len(parts) > 1:
                nome_abrev = f"{parts[0][0]}. {parts[-1][0]}."
            else:
                nome_abrev = lider.nome_completo[:30]
            
            if len(nome_abrev) > 30:
                nome_abrev = nome_abrev[:27] + '...'
            
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
            
            # Contar registros de treinamento
            vigentes = RegistroTreinamento.objects.filter(
                colaborador_id__in=colaboradores_ids,
                data_treinamento__isnull=False
            ).count()
            pendentes = RegistroTreinamento.objects.filter(
                colaborador_id__in=colaboradores_ids,
                data_treinamento__isnull=True
            ).count()
            
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
    
    return render(request, 'procedures/dashboard_treinamentos.html', context)