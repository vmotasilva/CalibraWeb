# -*- coding: utf-8 -*-
"""
Views de importação e administração - Gerenciamento de dados em massa
"""

import os
import io
import logging
from datetime import date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import pandas as pd
from qms.models import ImportJob
from qms.views_helpers import parse_date, export_to_excel_response

logger = logging.getLogger(__name__)


# ==============================================================================
# SOLICITAÇÃO DE INSTRUMENTO
# ==============================================================================

@login_required
def nova_solicitacao(request):
    """Cria nova solicitação de instrumento/equipamento."""
    from procurements.forms import SolicitacaoForm
    
    if request.method == "POST":
        form = SolicitacaoForm(request.POST)
        if form.is_valid():
            solicitacao = form.save(commit=False)
            solicitacao.solicitante = request.user
            solicitacao.save()
            messages.success(request, "Solicitação enviada com sucesso!")
            return redirect("home")
    else:
        form = SolicitacaoForm()
    
    return render(
        request,
        "form_generico.html",
        {"form": form, "titulo": "Nova Solicitação"},
    )


# ==============================================================================
# IMPORTAÇÃO DE CATEGORIAS
# ==============================================================================

@login_required
@require_http_methods(["GET", "POST"])
def imp_categorias_view(request):
    """Importação de categorias de instrumentos."""
    if request.method == "GET":
        return render(request, "imp_categorias.html")
    
    # POST - Processamento
    if "file" not in request.FILES:
        messages.error(request, "Nenhum arquivo enviado.")
        return redirect("imp_categorias")
    
    try:
        arquivo = request.FILES["file"]
        df = pd.read_excel(arquivo)
        
        # Validação básica
        required_cols = {"nome", "descricao", "unidade_sigla"}
        if not required_cols.issubset(set(df.columns)):
            messages.error(request, f"Colunas esperadas: {required_cols}")
            return redirect("imp_categorias")
        
        # Cria job de importação
        filepath = os.path.join(
            "/tmp", f"categorias_{date.today().isoformat()}.xlsx"
        )
        arquivo.save(filepath)
        
        from qms.tasks import import_categorias_task
        try:
            import_categorias_task.delay(str(None), filepath)
        except Exception:
            import_categorias_task(None, filepath)
        
        messages.success(
            request, 
            f"Importação iniciada: {df.shape[0]} registros."
        )
    except Exception as e:
        messages.error(request, f"Erro ao processar arquivo: {e}")
        logger.exception("Falha na importação de categorias")
    
    return redirect("imp_categorias")


# ==============================================================================
# IMPORTAÇÃO DE COLABORADORES
# ==============================================================================

@login_required
@require_http_methods(["GET", "POST"])
def imp_colab_view(request):
    """Importação de colaboradores."""
    if request.method == "GET":
        return render(request, "imp_colab.html")
    
    # POST - Processamento
    if "file" not in request.FILES:
        messages.error(request, "Nenhum arquivo enviado.")
        return redirect("imp_colab")
    
    try:
        arquivo = request.FILES["file"]
        df = pd.read_excel(arquivo)
        
        # Validação básica
        required_cols = {
            "MATRICULA", "NOME", "CPF", "CARGO", "GRUPO", "SETOR", 
            "CC", "TURNO", "STATUS"
        }
        if not required_cols.issubset(set(df.columns)):
            messages.error(request, f"Colunas esperadas: {required_cols}")
            return redirect("imp_colab")
        
        # Cria job de importação
        filepath = os.path.join(
            "/tmp", f"colab_{date.today().isoformat()}.xlsx"
        )
        arquivo.save(filepath)
        
        from qms.tasks import import_colab_task
        try:
            import_colab_task.delay(str(None), filepath)
        except Exception:
            import_colab_task(None, filepath)
        
        messages.success(
            request,
            f"Importação de colaboradores iniciada: {df.shape[0]} registros."
        )
    except Exception as e:
        messages.error(request, f"Erro ao processar arquivo: {e}")
        logger.exception("Falha na importação de colaboradores")
    
    return redirect("imp_colab")


# ==============================================================================
# IMPORTAÇÃO DE HIERARQUIA
# ==============================================================================

@login_required
@require_http_methods(["GET", "POST"])
def imp_hierarquia_view(request):
    """Importação de estrutura hierárquica."""
    if request.method == "GET":
        return render(request, "imp_hierarquia.html")
    
    # POST - Processamento
    if "file" not in request.FILES:
        messages.error(request, "Nenhum arquivo enviado.")
        return redirect("imp_hierarquia")
    
    try:
        arquivo = request.FILES["file"]
        df = pd.read_excel(arquivo)
        
        # Validação básica
        required_cols = {"SETOR", "TURNO", "MAT_LIDER"}
        if not required_cols.issubset(set(df.columns)):
            messages.error(request, f"Colunas esperadas: {required_cols}")
            return redirect("imp_hierarquia")
        
        # Cria job de importação
        filepath = os.path.join(
            "/tmp", f"hierarquia_{date.today().isoformat()}.xlsx"
        )
        arquivo.save(filepath)
        
        from qms.tasks import import_hierarquia_task
        try:
            import_hierarquia_task.delay(str(None), filepath)
        except Exception:
            import_hierarquia_task(None, filepath)
        
        messages.success(
            request,
            f"Importação de hierarquia iniciada: {df.shape[0]} registros."
        )
    except Exception as e:
        messages.error(request, f"Erro ao processar arquivo: {e}")
        logger.exception("Falha na importação de hierarquia")
    
    return redirect("imp_hierarquia")


# ==============================================================================
# IMPORTAÇÃO DE FÉRIAS
# ==============================================================================

@login_required
@require_http_methods(["GET", "POST"])
def imp_ferias_view(request):
    """Importação de períodos de férias."""
    if request.method == "GET":
        return render(request, "imp_ferias.html")
    
    # POST - Processamento
    if "file" not in request.FILES:
        messages.error(request, "Nenhum arquivo enviado.")
        return redirect("imp_ferias")
    
    try:
        arquivo = request.FILES["file"]
        df = pd.read_excel(arquivo)
        
        # Validação básica
        required_cols = {
            "MATRICULA", "AQUISITIVO_INICIO", "AQUISITIVO_FIM",
            "DATA_INICIO", "DATA_FIM", "STATUS"
        }
        if not required_cols.issubset(set(df.columns)):
            messages.error(request, f"Colunas esperadas: {required_cols}")
            return redirect("imp_ferias")
        
        # Cria job de importação
        filepath = os.path.join(
            "/tmp", f"ferias_{date.today().isoformat()}.xlsx"
        )
        arquivo.save(filepath)
        
        from qms.tasks import import_ferias_task
        try:
            import_ferias_task.delay(str(None), filepath)
        except Exception:
            import_ferias_task(None, filepath)
        
        messages.success(
            request,
            f"Importação de férias iniciada: {df.shape[0]} registros."
        )
    except Exception as e:
        messages.error(request, f"Erro ao processar arquivo: {e}")
        logger.exception("Falha na importação de férias")
    
    return redirect("imp_ferias")


# ==============================================================================
# IMPORTAÇÃO DE PROCEDIMENTOS
# ==============================================================================

@login_required
@require_http_methods(["GET", "POST"])
def imp_procedimentos_view(request):
    """Importação de procedimentos operacionais."""
    if request.method == "GET":
        return render(request, "imp_procedimentos.html")
    
    # POST - Processamento
    if "file" not in request.FILES:
        messages.error(request, "Nenhum arquivo enviado.")
        return redirect("imp_procedimentos")
    
    try:
        arquivo = request.FILES["file"]
        df = pd.read_excel(arquivo)
        
        # Validação básica
        required_cols = {
            "no", "codigo", "nome", "descricao", "pasta",
            "classificacao", "autor", "numero_revisao"
        }
        if not required_cols.issubset(set(df.columns)):
            messages.error(request, f"Colunas esperadas: {required_cols}")
            return redirect("imp_procedimentos")
        
        # Cria job de importação
        filepath = os.path.join(
            "/tmp", f"procedimentos_{date.today().isoformat()}.xlsx"
        )
        arquivo.save(filepath)
        
        from qms.tasks import import_procedimentos_task
        try:
            import_procedimentos_task.delay(str(None), filepath)
        except Exception:
            import_procedimentos_task(None, filepath)
        
        messages.success(
            request,
            f"Importação de procedimentos iniciada: {df.shape[0]} registros."
        )
    except Exception as e:
        messages.error(request, f"Erro ao processar arquivo: {e}")
        logger.exception("Falha na importação de procedimentos")
    
    return redirect("imp_procedimentos")


# ==============================================================================
# EXPORTAÇÃO DE DADOS
# ==============================================================================

@login_required
def export_categorias_view(request):
    """Exporta todas as categorias registradas."""
    from metrologia.models import CategoriaInstrumento
    
    try:
        categorias = CategoriaInstrumento.objects.all().order_by("nome")
        data = []
        for cat in categorias:
            data.append({
                "ID": cat.id,
                "NOME": cat.nome,
                "DESCRICAO": cat.descricao or "",
                "UNIDADE": cat.unidade_sigla or "",
            })
        
        df = pd.DataFrame(data)
        fname = f"categorias_export_{date.today().isoformat()}.xlsx"
        return export_to_excel_response(df, fname)
    except Exception as e:
        messages.error(request, f"Falha ao exportar: {e}")
        return redirect("imp_categorias")


@login_required
def export_colab_view(request):
    """Exporta todos os colaboradores."""
    from rh.models import Colaborador
    
    try:
        colabs = Colaborador.objects.filter(is_active=True).select_related(
            "setor", "centro_custo"
        ).order_by("nome_completo")
        
        data = []
        for colab in colabs:
            data.append({
                "MATRICULA": colab.matricula,
                "NOME": colab.nome_completo,
                "CPF": colab.cpf or "",
                "CARGO": colab.cargo or "",
                "SETOR": colab.setor.nome if colab.setor else "",
                "CC": colab.centro_custo.codigo if colab.centro_custo else "",
                "TURNO": colab.get_turno_display(),
                "STATUS": "ATIVO",
            })
        
        df = pd.DataFrame(data)
        fname = f"colaboradores_export_{date.today().isoformat()}.xlsx"
        return export_to_excel_response(df, fname)
    except Exception as e:
        messages.error(request, f"Falha ao exportar: {e}")
        return redirect("imp_colab")


@login_required
def export_hierarquia_view(request):
    """Exporta a hierarquia organizacional."""
    from organization.models import HierarquiaSetor
    
    try:
        hierarquias = HierarquiaSetor.objects.all().select_related(
            "setor", "lider", "supervisor", "gerente", "diretor"
        ).order_by("setor__nome")
        
        data = []
        for h in hierarquias:
            data.append({
                "SETOR": h.setor.nome if h.setor else "",
                "TURNO": h.get_turno_display(),
                "MAT_LIDER": h.lider.matricula if h.lider else "",
                "MAT_SUPERVISOR": h.supervisor.matricula if h.supervisor else "",
                "MAT_GERENTE": h.gerente.matricula if h.gerente else "",
                "MAT_DIRETOR": h.diretor.matricula if h.diretor else "",
            })
        
        df = pd.DataFrame(data)
        fname = f"hierarquia_export_{date.today().isoformat()}.xlsx"
        return export_to_excel_response(df, fname)
    except Exception as e:
        messages.error(request, f"Falha ao exportar: {e}")
        return redirect("imp_hierarquia")
