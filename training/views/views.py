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
from training.models import Procedimento, RegistroTreinamento
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
    
    return render(request, 'form_generico.html', {
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
    
    return render(request, 'form_generico.html', {
        'form': form,
        'titulo': f'Editar {proc.codigo}'
    })


@login_required
def detalhe_procedimento_view(request, procedimento_id):
    """Visualiza detalhes de um procedimento."""
    proc = get_object_or_404(Procedimento, id=procedimento_id)
    return render(request, 'procedimento_detalhe.html', {
        'proc': proc
    })


@login_required
def treinamentos_list_view(request):
    """Lista de treinamentos realizados com filtros."""
    qs = RegistroTreinamento.objects.select_related('colaborador', 'procedimento').all()
    colaboradores = Colaborador.objects.order_by('nome_completo')
    procedimentos = Procedimento.objects.order_by('codigo')
    
    status = request.GET.get('status')
    colaborador_id = request.GET.get('colaborador')
    procedimento_id = request.GET.get('procedimento')
    busca = request.GET.get('q')

    # Filtro de status - nota: status_treinamento é uma property, não field
    if status:
        qs = [t for t in qs if t.status_treinamento == status]
    
    if colaborador_id:
        qs = qs.filter(colaborador_id=colaborador_id)
    if procedimento_id:
        qs = qs.filter(procedimento_id=procedimento_id)
    if busca:
        qs = qs.filter(
            Q(colaborador__nome_completo__icontains=busca) |
            Q(procedimento__codigo__icontains=busca) |
            Q(procedimento__nome__icontains=busca)
        )
    
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
