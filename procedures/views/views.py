# -*- coding: utf-8 -*-
"""
Views para o módulo Procedures
Consolida training + procurements:
- Procedimentos, Treinamentos
- Fornecedores, Avaliações, Cotações
"""

import io
import os
import logging
from datetime import date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Q
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
import pandas as pd

logger = logging.getLogger(__name__)

# Models
from procedures.models import (
    Procedimento, RegistroTreinamento, PacoteTreinamento,
    Fornecedor, AvaliacaoFornecedor, ProcessoCotacao, Orcamento
)
from rh.models import Colaborador

# Forms
from procedures.forms import (
    ProcedimentoForm, RegistroTreinamentoForm, PacoteTreinamentoForm,
    FornecedorForm, AvaliacaoFornecedorForm, ProcessoCotacaoForm, OrcamentoForm
)

# Helpers
from qms.views_helpers import export_to_excel_response, can_manage_procedimentos


# ==============================================================================
# PROCEDIMENTOS
# ==============================================================================

@login_required
def procedimentos_list_view(request):
    """Lista de Procedimentos com filtros avançados."""
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

    page_number = request.GET.get('page', '1')
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
    return render(request, 'procedures/procedimento_lista.html', ctx)


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
def download_template_procedimentos_view(request):
    """Download do template de importação de procedimentos."""
    # Dados de exemplo
    rows = [
        {
            'codigo': 'POP.001',
            'nome': 'Procedimento Operacional Padrão 1',
            'descricao': 'Descrição do procedimento',
            'pasta': 'QUALIDADE',
            'classificacao': 'POP',
            'autor': 'Nome do Autor',
            'numero_revisao': '01',
            'ultima_revisao': '2025-12-24',
            'data_aprovacao': '2025-12-24',
            'proxima_revisao': '2026-12-24',
            'data_validade': '2026-12-24',
            'documentos_controlados': 'Sim',
            'matriz': 'Matriz Principal',
            'sub_area': 'Área de Processos',
        },
        {
            'codigo': 'POP.002',
            'nome': 'Procedimento Operacional Padrão 2',
            'descricao': 'Outro procedimento de exemplo',
            'pasta': 'PRODUÇÃO',
            'classificacao': 'IT',
            'autor': 'Outro Autor',
            'numero_revisao': '02',
            'ultima_revisao': '2025-12-24',
            'data_aprovacao': '2025-12-24',
            'proxima_revisao': '2026-12-24',
            'data_validade': '2026-12-24',
            'documentos_controlados': 'Não',
            'matriz': 'Matriz Principal',
            'sub_area': 'Área de Produção',
        },
    ]
    
    return export_to_excel_response(rows, "template_procedimentos.xlsx")


@login_required
def importar_procedimentos_view(request):
    """Importação em massa de procedimentos via arquivo Excel/CSV."""
    if not can_manage_procedimentos(request.user):
        messages.error(request, 'Sem permissão para importar procedimentos.')
        return redirect('procedimentos_list')
    
    from procedures.forms import ImportacaoProcedimentosForm
    from procedures.services.importacao_procedimentos import ImportacaoProcedimentosService
    from django.utils.safestring import mark_safe
    
    relatorio_html = None
    
    if request.method == 'POST' and request.FILES.get('arquivo_excel'):
        form = ImportacaoProcedimentosForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                arquivo = request.FILES['arquivo_excel']
                servico = ImportacaoProcedimentosService(arquivo)
                
                # Processa arquivo (modo upsert por padrão)
                resultados = servico.processar(modo='upsert')
                
                # Gera relatório
                relatorio_html = mark_safe(servico.gerar_relatorio_html())
                
                # Mensagem de sucesso
                if resultados['erros'] == 0:
                    messages.success(request, 
                        f"✅ Importação concluída com sucesso! "
                        f"{resultados['criados']} criados, {resultados['atualizados']} atualizados.")
                else:
                    messages.warning(request, 
                        f"⚠️ Importação com algumas inconsistências: "
                        f"{resultados['criados']} criados, {resultados['atualizados']} atualizados, "
                        f"{resultados['erros']} erros. Verifique os detalhes abaixo.")
                
                logger.info(f"Importação de procedimentos realizada por {request.user}: "
                           f"Criados: {resultados['criados']}, Atualizados: {resultados['atualizados']}, Erros: {resultados['erros']}")
                
            except Exception as e:
                messages.error(request, f"❌ Erro ao processar arquivo: {str(e)}")
                logger.error(f"Erro ao importar procedimentos: {e}", exc_info=True)
    else:
        form = ImportacaoProcedimentosForm()
    
    return render(request, 'procedures/procedimentos_importar.html', {
        'form': form,
        'relatorio_html': relatorio_html,
    })


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
    return render(request, 'procedures/procedimento_detalhe.html', {
        'proc': proc
    })


# ==============================================================================
# TREINAMENTOS
# ==============================================================================

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

    # Filtro de status - nota: status_treinamento é uma property
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
    
    return render(request, "procedures/treinamento_lista.html", {
        "treinamentos": treinamentos,
        "colaboradores": colaboradores,
        "procedimentos": procedimentos,
        "status": status,
        "colaborador_id": colaborador_id,
        "procedimento_id": procedimento_id,
        "busca": busca,
    })


@login_required
def treinamentos_detalhe_view(request, treinamento_id):
    """View detalhes de um registro de treinamento."""
    treinamento = get_object_or_404(RegistroTreinamento, id=treinamento_id)
    return render(request, "procedures/treinamento_detalhe.html", {
        "treinamento": treinamento
    })


@login_required
def novo_treinamento_view(request):
    """Criar novo registro de treinamento."""
    if request.method == "POST":
        form = RegistroTreinamentoForm(request.POST)
        if form.is_valid():
            treinamento = form.save()
            messages.success(request, "Treinamento registrado com sucesso.")
            return redirect("treinamentos_list")
    else:
        form = RegistroTreinamentoForm()
    
    return render(request, "procedures/treinamento_form.html", {
        "form": form
    })


@login_required
def editar_treinamento_view(request, treinamento_id):
    """Editar registro de treinamento existente."""
    treinamento = get_object_or_404(RegistroTreinamento, id=treinamento_id)
    if request.method == "POST":
        form = RegistroTreinamentoForm(request.POST, instance=treinamento)
        if form.is_valid():
            form.save()
            messages.success(request, "Treinamento atualizado.")
            return redirect("treinamentos_list")
    else:
        form = RegistroTreinamentoForm(instance=treinamento)
    
    return render(request, "procedures/treinamento_form.html", {
        "form": form
    })


# ==============================================================================
# FORNECEDORES
# ==============================================================================

@login_required
def fornecedores_list_view(request):
    """Lista de fornecedores com filtros."""
    qs = Fornecedor.objects.all()
    
    termo = request.GET.get('q')
    status = request.GET.get('status')
    
    if termo:
        qs = qs.filter(Q(nome_fantasia__icontains=termo) | Q(cnpj__icontains=termo))
    if status:
        qs = qs.filter(status=status)
    
    page_number = request.GET.get('page', '1')
    paginator = Paginator(qs.order_by('nome_fantasia'), 50)
    page_obj = paginator.get_page(page_number)
    
    return render(request, "procedures/fornecedor_lista.html", {
        "page_obj": page_obj,
        "termo": termo,
        "status": status,
    })


@login_required
def novo_fornecedor_view(request):
    """Criar novo fornecedor."""
    if request.method == "POST":
        form = FornecedorForm(request.POST)
        if form.is_valid():
            fornecedor = form.save()
            messages.success(request, f"Fornecedor {fornecedor.nome_fantasia} criado com sucesso!")
            return redirect("fornecedores_list")
    else:
        form = FornecedorForm()
    
    return render(request, "procedures/fornecedor_form.html", {
        "form": form,
        "titulo": "Novo Fornecedor"
    })


@login_required
def editar_fornecedor_view(request, fornecedor_id):
    """Editar fornecedor existente."""
    fornecedor = get_object_or_404(Fornecedor, id=fornecedor_id)
    if request.method == "POST":
        form = FornecedorForm(request.POST, instance=fornecedor)
        if form.is_valid():
            form.save()
            messages.success(request, "Fornecedor atualizado com sucesso!")
            return redirect("fornecedores_list")
    else:
        form = FornecedorForm(instance=fornecedor)
    
    return render(request, "procedures/fornecedor_form.html", {
        "form": form,
        "titulo": f"Editar {fornecedor.nome_fantasia}"
    })


@login_required
def detalhe_fornecedor_view(request, fornecedor_id):
    """Detalhes de um fornecedor."""
    fornecedor = get_object_or_404(Fornecedor, id=fornecedor_id)
    avaliacoes = fornecedor.avaliacoes.all()
    
    return render(request, "procedures/fornecedor_detalhe.html", {
        "fornecedor": fornecedor,
        "avaliacoes": avaliacoes,
    })


# ==============================================================================
# AVALIAÇÕES DE FORNECEDOR
# ==============================================================================

@login_required
def nova_avaliacao_fornecedor_view(request):
    """Criar nova avaliação de fornecedor."""
    if request.method == "POST":
        form = AvaliacaoFornecedorForm(request.POST)
        if form.is_valid():
            avaliacao = form.save(commit=False)
            avaliacao.avaliador = request.user if hasattr(request.user, 'colaborador') else None
            avaliacao.save()
            messages.success(request, "Avaliação registrada com sucesso!")
            return redirect("fornecedores_list")
    else:
        form = AvaliacaoFornecedorForm()
    
    return render(request, "procedures/avaliacao_fornecedor_form.html", {
        "form": form
    })


# ==============================================================================
# PROCESSOS DE COTAÇÃO
# ==============================================================================

@login_required
def cotacoes_list_view(request):
    """Lista de processos de cotação."""
    qs = ProcessoCotacao.objects.all()
    
    status = request.GET.get('status')
    if status:
        qs = qs.filter(status=status)
    
    page_number = request.GET.get('page', '1')
    paginator = Paginator(qs.order_by('-data_abertura'), 50)
    page_obj = paginator.get_page(page_number)
    
    return render(request, "procedures/cotacao_lista.html", {
        "page_obj": page_obj,
        "status": status,
    })


@login_required
def nova_cotacao_view(request):
    """Criar novo processo de cotação."""
    if request.method == "POST":
        form = ProcessoCotacaoForm(request.POST)
        if form.is_valid():
            cotacao = form.save(commit=False)
            cotacao.responsavel = request.user if hasattr(request.user, 'colaborador') else None
            cotacao.save()
            form.save_m2m()
            messages.success(request, f"Cotação {cotacao.titulo} criada com sucesso!")
            return redirect("cotacoes_list")
    else:
        form = ProcessoCotacaoForm()
    
    return render(request, "procedures/cotacao_form.html", {
        "form": form,
        "titulo": "Nova Cotação"
    })


@login_required
def editar_cotacao_view(request, cotacao_id):
    """Editar processo de cotação existente."""
    cotacao = get_object_or_404(ProcessoCotacao, id=cotacao_id)
    if request.method == "POST":
        form = ProcessoCotacaoForm(request.POST, instance=cotacao)
        if form.is_valid():
            form.save()
            messages.success(request, "Cotação atualizada com sucesso!")
            return redirect("cotacoes_list")
    else:
        form = ProcessoCotacaoForm(instance=cotacao)
    
    return render(request, "procedures/cotacao_form.html", {
        "form": form,
        "titulo": f"Editar {cotacao.titulo}"
    })


@login_required
def detalhe_cotacao_view(request, cotacao_id):
    """Detalhes de um processo de cotação."""
    cotacao = get_object_or_404(ProcessoCotacao, id=cotacao_id)
    orcamentos = cotacao.orcamentos.all()
    
    return render(request, "procedures/cotacao_detalhe.html", {
        "cotacao": cotacao,
        "orcamentos": orcamentos,
    })


# ==============================================================================
# ORÇAMENTOS
# ==============================================================================

@login_required
def novo_orcamento_view(request):
    """Criar novo orçamento."""
    if request.method == "POST":
        form = OrcamentoForm(request.POST, request.FILES)
        if form.is_valid():
            orcamento = form.save()
            messages.success(request, "Orçamento criado com sucesso!")
            return redirect("cotacoes_list")
    else:
        form = OrcamentoForm()
    
    return render(request, "procedures/orcamento_form.html", {
        "form": form
    })


@login_required
def editar_orcamento_view(request, orcamento_id):
    """Editar orçamento existente."""
    orcamento = get_object_or_404(Orcamento, id=orcamento_id)
    if request.method == "POST":
        form = OrcamentoForm(request.POST, request.FILES, instance=orcamento)
        if form.is_valid():
            form.save()
            messages.success(request, "Orçamento atualizado com sucesso!")
            return redirect("detalhe_cotacao", cotacao_id=orcamento.processo.id)
    else:
        form = OrcamentoForm(instance=orcamento)
    
    return render(request, "procedures/orcamento_form.html", {
        "form": form
    })
