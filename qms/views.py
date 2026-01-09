# -*- coding: utf-8 -*-
"""
Main views module for QMS application.
This module consolidates views for the metrologia, procedures, and import modules.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import HttpResponse, JsonResponse, Http404, FileResponse
from django.db.models import Q, Count, Max, Prefetch
from django.core.paginator import Paginator
from django.utils import timezone
from django.urls import reverse
from datetime import date, datetime, timedelta
from decimal import Decimal
import logging

# Import helper functions from views_helpers
from .views_helpers import (
    excel_date_to_datetime,
    get_all_subordinates,
    get_colaborador_for_user,
    dl_generic,
    dl_df,
    can_manage_procedimentos,
    export_to_excel_response,
    parse_date,
)

# Import pagination utilities
from .pagination import OffsetPaginator, PaginationHelper

# Import models from correct apps
from metrologia.models import (
    Instrumento,
    HistoricoCalibracao,
    CategoriaInstrumento,
    FaixaMedicao,
    ArquivoPadrao,
    ResultadoFaixaCalibracao,
)
from rh.models import Colaborador
from procedures.models import Procedimento
from organization.models import Setor
from .models import (
    ImportJob,
    SolicitacaoInstrumento,
    OcorrenciaInstrumento,
)

logger = logging.getLogger(__name__)

# ==============================================================================
# HEALTH CHECK
# ==============================================================================

def health_check(request):
    """Health check endpoint for monitoring."""
    return JsonResponse({"status": "ok"}, status=200)


# ==============================================================================
# DASHBOARD AND MODULE VIEWS
# ==============================================================================

@login_required
def dashboard_view(request):
    """Main dashboard view showing overview of the system."""
    context = {
        'total_instrumentos': Instrumento.objects.count(),
        'total_calibracoes': HistoricoCalibracao.objects.count(),
        'total_colaboradores': Colaborador.objects.count(),
        'total_procedimentos': Procedimento.objects.count(),
    }
    return render(request, 'shared/dashboard.html', context)


@login_required
def modulo_metrologia_view(request):
    """Metrologia module main view."""
    from datetime import date, timedelta
    from django.db.models.functions import Lower
    
    # Retrieve all instruments and related data
    instrumentos = Instrumento.objects.all().select_related('setor', 'categoria').prefetch_related('faixas').order_by('tag')
    
    # Get filter parameters from request
    status_filter = request.GET.get('status', '')
    categoria_filter = request.GET.get('categoria', '')
    setor_filter = request.GET.get('setor', '')
    search_query = request.GET.get('search', '')
    
    # Apenas filtros de categoria, setor e busca, sem filtrar por status no backend
    today = date.today()
    alerta_30d = today + timedelta(days=30)
    alerta_60d = today + timedelta(days=60)
    alerta_90d = today + timedelta(days=90)
    alerta_120d = today + timedelta(days=120)
    
    if categoria_filter:
        instrumentos = instrumentos.filter(categoria__id=categoria_filter)
    if setor_filter:
        instrumentos = instrumentos.filter(setor__id=setor_filter)
    if search_query:
        from django.db.models import Q
        instrumentos = instrumentos.filter(
            Q(tag__icontains=search_query) |
            Q(descricao__icontains=search_query) |
            Q(fabricante__icontains=search_query)
        )
    
    # Get available categories and sectors for filter options - ORDENADOS ALFABETICAMENTE
    categorias_filtro = CategoriaInstrumento.objects.all().order_by(Lower('nome'))
    setores_filtro = Setor.objects.all().order_by(Lower('nome'))
    
    context = {
        'instrumentos': instrumentos,
        'total_instrumentos': Instrumento.objects.count(),
        'total_calibracoes': HistoricoCalibracao.objects.count(),
        'categorias_filtro': categorias_filtro,
        'setores_filtro': setores_filtro,
        'status_filter': status_filter,
        'categoria_filter': categoria_filter,
        'setor_filter': setor_filter,
        'search_query': search_query,
        'colaborador': request.user,
        'today': today,
        'today_30days': today + timedelta(days=30),
        'hoje': today,
        'alerta_30d': alerta_30d,
        'alerta_60d': alerta_60d,
        'alerta_90d': alerta_90d,
        'alerta_120d': alerta_120d,
    }
    return render(request, 'metrologia/dashboard.html', context)


# ==============================================================================
# INSTRUMENT VIEWS
# ==============================================================================

@login_required
def novo_instrumento_view(request, instrumento_id=None):
    """Create or edit an instrument."""
    from .forms import InstrumentoForm
    
    if instrumento_id:
        instrumento = get_object_or_404(Instrumento, id=instrumento_id)
        is_edit = True
    else:
        instrumento = None
        is_edit = False
    
    if request.method == 'POST':
        form = InstrumentoForm(request.POST, instance=instrumento)
        if form.is_valid():
            instrumento_obj = form.save()
            if is_edit:
                messages.success(request, 'Instrumento atualizado com sucesso.')
            else:
                messages.success(request, 'Instrumento criado com sucesso.')
            return redirect('visualizar_instrumento', instrumento_id=instrumento_obj.id)
        else:
            messages.error(request, 'Erro ao salvar o instrumento. Verifique os dados.')
    else:
        form = InstrumentoForm(instance=instrumento)
    
    context = {
        'form': form,
        'instrumento': instrumento,
        'is_edit': is_edit,
        'title': 'Editar Instrumento' if is_edit else 'Novo Instrumento',
    }
    return render(request, 'metrologia/instrumento_form.html', context)


@login_required
def detalhe_instrumento_view(request, instrumento_id):
    """View instrument details with calibration history and quotations."""
    from datetime import date
    from metrologia.models import ItemCotacao, AtendimentoSolicitacao, ProcessoAutomatizacao
    
    # Get instrument or return 404
    instrumento = get_object_or_404(Instrumento, id=instrumento_id)

    # Get related data with optimization and error handling
    try:
        historicos = list(
            HistoricoCalibracao.objects.filter(instrumento=instrumento)
            .prefetch_related('resultados_faixa__faixa__unidade')
            .order_by("-data_calibracao")
        )
    except Exception as e:
        historicos = []
        logger.error(f"Erro ao buscar históricos para instrumento {instrumento_id}: {str(e)}")

    try:
        ocorrencias = list(
            OcorrenciaInstrumento.objects.filter(instrumento=instrumento)
            .select_related('usuario_responsavel')
            .order_by("-data_ocorrencia")
        )
    except Exception as e:
        ocorrencias = []
        logger.error(f"Erro ao buscar ocorrências para instrumento {instrumento_id}: {str(e)}")

    try:
        faixas = list(
            FaixaMedicao.objects.filter(instrumento=instrumento)
            .select_related('unidade')
            .all()
        )
    except Exception as e:
        faixas = []
        logger.error(f"Erro ao buscar faixas para instrumento {instrumento_id}: {str(e)}")

    # NEW: Get quotation-related data - fetch AtendimentoSolicitacao directly
    try:
        # Get all atendimentos for this instrument
        atendimentos_instrumento = list(
            AtendimentoSolicitacao.objects.filter(
                item_cotacao__instrumento=instrumento
            ).select_related(
                'item_cotacao__cotacao_fornecedor__fornecedor',
                'item_cotacao__item_solicitacao__solicitacao',
                'solicitacao'
            ).prefetch_related(
                'historicos_calibracao'  # Include related calibration history
            ).order_by('-data_escolha')
        )
        
        # Separate by service type
        cotacoes_calibracao = [a for a in atendimentos_instrumento if a.item_cotacao.tipo_servico == 'CALIBRACAO']
        cotacoes_aquisicao = [a for a in atendimentos_instrumento if a.item_cotacao.tipo_servico == 'AQUISICAO']
        
        # Keep original list for backward compatibility
        cotacoes_itens = atendimentos_instrumento
    except Exception as e:
        cotacoes_itens = []
        cotacoes_calibracao = []
        cotacoes_aquisicao = []
        logger.error(f"Erro ao buscar cotações para instrumento {instrumento_id}: {str(e)}")

    # Get ALL quotation items for this instrument (complete history)
    try:
        todas_cotacoes = list(
            ItemCotacao.objects.filter(
                instrumento=instrumento
            ).select_related(
                'cotacao_fornecedor__fornecedor',
                'item_solicitacao__solicitacao'
            ).order_by('-cotacao_fornecedor__data_criacao')
        )
    except Exception as e:
        todas_cotacoes = []
        logger.error(f"Erro ao buscar todas as cotações para instrumento {instrumento_id}: {str(e)}")

    # Get all quotation requests (SolicitacaoCotacao) that contain items with this instrument
    try:
        from metrologia.models import ItemSolicitacaoCotacao, SolicitacaoCotacao
        
        solicitacoes_cotacao = list(
            SolicitacaoCotacao.objects.filter(
                itens__instrumento=instrumento
            ).select_related(
                'responsavel'
            ).distinct().order_by('-data_criacao')
        )
    except Exception as e:
        solicitacoes_cotacao = []
        logger.error(f"Erro ao buscar solicitações de cotação para instrumento {instrumento_id}: {str(e)}")

    try:
        rastreios_laboratorio = list(
            AtendimentoSolicitacao.objects.filter(
                item_solicitacao__instrumento=instrumento,
                item_cotacao__local_atendimento='NO_LABORATORIO'
            ).select_related(
                'item_cotacao__cotacao_fornecedor__fornecedor',
                'item_solicitacao'
            ).order_by('-data_escolha')
        )
    except Exception as e:
        rastreios_laboratorio = []
        logger.error(f"Erro ao buscar rastreios para instrumento {instrumento_id}: {str(e)}")

    try:
        processos_automatizacao = list(
            ProcessoAutomatizacao.objects.filter(
                atendimento__item_solicitacao__instrumento=instrumento
            ).select_related(
                'atendimento__item_cotacao'
            ).order_by('-data_inicio')
        )
    except Exception as e:
        processos_automatizacao = []
        logger.error(f"Erro ao buscar processos de automatização para instrumento {instrumento_id}: {str(e)}")

    context = {
        'instrumento': instrumento,
        'historicos': historicos,
        'ocorrencias': ocorrencias,
        'faixas': faixas,
        'today': date.today(),
        'edit_url': f"/instrumento/{instrumento.id}/editar/",
        # NEW: Quotation data
        'cotacoes_calibracao': cotacoes_calibracao,
        'cotacoes_aquisicao': cotacoes_aquisicao,
        'todas_cotacoes': todas_cotacoes,
        'solicitacoes_cotacao': solicitacoes_cotacao,
        'rastreios_laboratorio': rastreios_laboratorio,
        'processos_automatizacao': processos_automatizacao,
    }
    return render(request, 'metrologia/instrumento_detalhe.html', context)


# ==============================================================================
# CALIBRATION HISTORY VIEWS
# ==============================================================================

@login_required
def registrar_historico_calibracao_view(request, instrumento_id):
    """Cria novo histórico de calibração e redireciona para edição no template unificado (editar_historico.html)."""
    try:
        from datetime import date
        
        instrumento = get_object_or_404(Instrumento, id=instrumento_id)
        logger.info(f"Registrar histórico: instrumento_id={instrumento_id}, method={request.method}, user={request.user}")
        
        # Cria um novo histórico vazio para o instrumento com campos obrigatórios preenchidos
        historico = HistoricoCalibracao.objects.create(
            instrumento=instrumento,
            data_calibracao=date.today(),  # Campo obrigatório
            data_aprovacao=date.today(),  # Campo obrigatório com default
            numero_certificado="S/N",  # Campo obrigatório com default
            tipo_calibracao="EXTERNA",  # Campo obrigatório com default
            resultado="APROVADO_SEM_CORRECAO"  # Campo obrigatório com default
        )
        
        logger.info(f"✓ Histórico vazio {historico.id} criado com sucesso para instrumento {instrumento_id}")
        
        # Redireciona para edição no template unificado (editar_historico.html)
        messages.success(request, f"✓ Novo histórico criado! Agora preencha os dados.")
        return redirect('editar_historico_calibracao', historico_id=historico.id)
        
    except Exception as e:
        logger.error(f"❌ Erro crítico em registrar_historico_calibracao_view: {e}", exc_info=True)
        messages.error(request, f'Erro ao criar histórico: {str(e)}')
        return redirect('detalhe_instrumento', instrumento_id=instrumento_id)


@login_required
def visualizar_historico_calibracao_view(request, historico_id):
    """View calibration history details."""
    from django.db.models import Prefetch
    
    historico = get_object_or_404(
        HistoricoCalibracao.objects.prefetch_related(
            Prefetch('resultados_faixa__faixa')
        ), 
        id=historico_id
    )
    
    context = {
        'historico': historico,
        'instrumento': historico.instrumento,
        'resultados_faixa': historico.resultados_faixa.all(),
    }
    return render(request, 'metrologia/historico_calibracao_detail.html', context)


@login_required
def remover_historico_view(request, historico_id):
    """Remove a calibration history record."""
    historico = get_object_or_404(HistoricoCalibracao, id=historico_id)
    instrumento_id = historico.instrumento.id
    
    if request.method == 'POST':
        historico.delete()
        messages.success(request, 'Histórico removido com sucesso.')
        return redirect('visualizar_instrumento', instrumento_id=instrumento_id)
    
    context = {
        'historico': historico,
    }
    return render(request, 'shared/dashboard.html', context)


# ==============================================================================
# CERTIFICATE VIEWS
# ==============================================================================

@login_required
def preview_certificado_view(request, historico_id):
    """Preview a calibration certificate."""
    historico = get_object_or_404(HistoricoCalibracao, id=historico_id)
    
    context = {
        'historico': historico,
    }
    return render(request, 'metrologia/certificado_preview.html', context)


@login_required
def download_certificado_view(request, historico_id):
    """Download a calibration certificate."""
    historico = get_object_or_404(HistoricoCalibracao, id=historico_id)
    
    # Get the type of certificate to download (original or stamped)
    tipo = request.GET.get('tipo', 'carimbado')  # Default to stamped if available
    
    if tipo == 'carimbado':
        certificado = historico.certificado_carimbado or historico.certificado
    elif tipo == 'original':
        certificado = historico.certificado
    else:
        # Fallback: prefer stamped, then original
        certificado = historico.certificado_carimbado or historico.certificado
    
    if certificado:
        response = FileResponse(certificado.open('rb'))
        response['Content-Disposition'] = f'attachment; filename="{certificado.name}"'
        return response
    
    messages.error(request, 'Certificado não disponível.')
    return redirect('visualizar_historico_calibracao', historico_id=historico_id)


@login_required
def anexar_certificado_historico_view(request, historico_id):
    """Attach a certificate to a calibration history record."""
    from metrologia.models import FaixaMedicao
    
    historico = get_object_or_404(HistoricoCalibracao, id=historico_id)
    
    if request.method == 'POST':
        if 'certificado' in request.FILES:
            historico.certificado = request.FILES['certificado']
            historico.save()
            messages.success(request, 'Certificado anexado com sucesso.')
        return redirect('visualizar_historico_calibracao', historico_id=historico_id)
    
    # Get measurement ranges for this instrument
    faixas_medicao = FaixaMedicao.objects.filter(
        instrumento=historico.instrumento
    ).order_by('valor_minimo') if historico.instrumento else []
    
    context = {
        'historico': historico,
        'faixas_medicao': faixas_medicao,
    }
    return render(request, 'metrologia/historico_calibracao_form.html', context)


@login_required
def remover_certificado_historico_view(request, historico_id):
    """Remove a certificate from a calibration history record."""
    historico = get_object_or_404(HistoricoCalibracao, id=historico_id)
    
    if request.method == 'POST':
        historico.certificado = None
        historico.save()
        messages.success(request, 'Certificado removido com sucesso.')
        return redirect('visualizar_historico_calibracao', historico_id=historico_id)
    
    context = {
        'historico': historico,
    }
    return render(request, 'shared/dashboard.html', context)


@login_required
def get_certificado_bytes_view(request, historico_id):
    """Return certificate PDF as bytes for PDF.js viewer."""
    from django.core.files.storage import default_storage
    import os
    
    historico = get_object_or_404(HistoricoCalibracao, id=historico_id)
    
    # Get the type of certificate to return (original or stamped)
    tipo = request.GET.get('tipo', 'auto')  # Changed default to 'auto'
    
    logger.info(f"[GET_CERT] Requisição de certificado tipo='{tipo}' para historico {historico_id}")
    logger.info(f"[GET_CERT] certificado_carimbado: {historico.certificado_carimbado.name if historico.certificado_carimbado else 'None'}")
    logger.info(f"[GET_CERT] certificado: {historico.certificado.name if historico.certificado else 'None'}")
    
    # Smart selection logic
    certificado = None
    
    if tipo == 'carimbado':
        certificado = historico.certificado_carimbado
        if not certificado:
            logger.info(f"[GET_CERT] Certificado carimbado não disponível, usando original")
            certificado = historico.certificado
    elif tipo == 'original':
        certificado = historico.certificado
        if not certificado:
            logger.info(f"[GET_CERT] Certificado original não disponível, usando carimbado")
            certificado = historico.certificado_carimbado
    else:  # tipo == 'auto' or any other value - prefer carimbado, fallback to original
        certificado = historico.certificado_carimbado if historico.certificado_carimbado else historico.certificado
    
    if not certificado:
        logger.warning(f"[GET_CERT] Nenhum certificado disponível para historico {historico_id}")
        return JsonResponse({'error': 'Nenhum certificado disponível'}, status=404)
    
    try:
        # Get the file name/path
        file_path = certificado.name
        logger.info(f"[GET_CERT] Tentando ler arquivo: {file_path}")
        
        # Check if file exists
        if not default_storage.exists(file_path):
            logger.error(f"[GET_CERT] Arquivo não existe no storage: {file_path}")
            return JsonResponse({'error': f'Arquivo não encontrado: {file_path}'}, status=404)
        
        # Get file size
        file_size = default_storage.size(file_path)
        logger.info(f"[GET_CERT] Tamanho do arquivo: {file_size} bytes")
        
        if file_size == 0:
            logger.error(f"[GET_CERT] Arquivo vazio: {file_path}")
            return JsonResponse({'error': 'Arquivo de certificado vazio'}, status=400)
        
        # Read file content
        with default_storage.open(file_path, 'rb') as f:
            pdf_bytes = f.read()
        
        if not pdf_bytes:
            logger.error(f"[GET_CERT] Conteúdo vazio após leitura: {file_path}")
            return JsonResponse({'error': 'Não foi possível ler o conteúdo do arquivo'}, status=400)
        
        # Validate PDF header
        if not pdf_bytes.startswith(b'%PDF'):
            logger.error(f"[GET_CERT] Arquivo não é um PDF válido: {file_path}")
            return JsonResponse({'error': 'Arquivo não é um PDF válido'}, status=400)
        
        logger.info(f"[GET_CERT] Certificado lido com sucesso: {len(pdf_bytes)} bytes")
        
        return HttpResponse(
            pdf_bytes,
            content_type='application/pdf',
            headers={'Content-Disposition': f'inline; filename="{os.path.basename(file_path)}"'}
        )
    except Exception as e:
        logger.error(f"[GET_CERT] Erro ao ler certificado para historico {historico_id}: {str(e)}", exc_info=True)
        return JsonResponse({'error': f'Erro ao ler certificado: {str(e)}'}, status=500)


@login_required
def debug_certificado_view(request, historico_id):
    """Debug view to check certificate status."""
    historico = get_object_or_404(HistoricoCalibracao, id=historico_id)
    
    data = {
        'historico_id': historico_id,
        'certificado_original': {
            'exists': bool(historico.certificado),
            'name': historico.certificado.name if historico.certificado else None,
            'size': historico.certificado.size if historico.certificado else None,
        },
        'certificado_carimbado': {
            'exists': bool(historico.certificado_carimbado),
            'name': historico.certificado_carimbado.name if historico.certificado_carimbado else None,
            'size': historico.certificado_carimbado.size if historico.certificado_carimbado else None,
        },
        'certificado_validado': historico.certificado_validado,
    }
    
    return JsonResponse(data)


@login_required
def aplicar_carimbo_certificado_view(request, historico_id):
    """Apply a stamp/seal to a certificate PDF."""
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from io import BytesIO
    from django.core.files.base import ContentFile
    
    historico = get_object_or_404(HistoricoCalibracao, id=historico_id)
    
    if request.method == 'POST':
        try:
            # Log incoming POST data for debugging
            logger.info(f"🔄 POST request received for historico {historico_id}")
            logger.info(f"📋 POST data: {dict(request.POST)}")
            
            # Get stamp data from POST
            resultado = request.POST.get('resultado', '')
            data_validacao = request.POST.get('data_validacao', '')
            nome_validador = request.POST.get('nome_validador', request.user.get_full_name() or request.user.username)
            # Coordinates are in PDF space based on frontend's measurement
            stamp_x = float(request.POST.get('carimbo_x', 450))
            stamp_y = float(request.POST.get('carimbo_y', 100))
            carimbo_page = int(request.POST.get('carimbo_page', 1))
            frontend_pdf_width = float(request.POST.get('carimbo_pdf_width', 595))
            frontend_pdf_height = float(request.POST.get('carimbo_pdf_height', 842))
            
            logger.info(f"✅ Stamp coordinates (from frontend): x={stamp_x}, y={stamp_y}")
            logger.info(f"📐 Frontend measured PDF dimensions: {frontend_pdf_width}x{frontend_pdf_height}")
            
            if not historico.certificado and not historico.certificado_carimbado:
                logger.warning(f"⚠️  No certificate available for historico {historico_id}")
                messages.error(request, 'Nenhum certificado disponível para carimbar.')
                return redirect('editar_historico_calibracao', historico_id=historico_id)
            
            # Use the original certificate if available, otherwise use the stamped version
            cert_file = historico.certificado if historico.certificado else historico.certificado_carimbado
            logger.info(f"📄 Using certificate: {cert_file.name}")
            
            # Read original PDF - keep bytes in memory to avoid file closure issues
            pdf_file = cert_file.open('rb')
            pdf_bytes = pdf_file.read()
            pdf_file.close()
            
            pdf_buffer = BytesIO(pdf_bytes)
            original_pdf = PdfReader(pdf_buffer)
            
            # Create stamp overlay using ReportLab
            stamp_buffer = BytesIO()
            
            # Get the original page to determine dimensions
            original_page = original_pdf.pages[carimbo_page - 1]
            page_width = float(original_page.mediabox.width)
            page_height = float(original_page.mediabox.height)
            
            logger.info(f"📐 Original page dimensions: {page_width}x{page_height} points")
            
            # Create canvas with actual page dimensions
            stamp_canvas = canvas.Canvas(stamp_buffer, pagesize=(page_width, page_height))
            
            # If frontend's PDF dimensions differ from actual PDF, need to rescale coordinates
            if abs(frontend_pdf_width - page_width) > 1 or abs(frontend_pdf_height - page_height) > 1:
                logger.warning(f"⚠️  Dimension mismatch! Frontend: {frontend_pdf_width}x{frontend_pdf_height}, Actual: {page_width}x{page_height}")
                # Rescale coordinates proportionally
                stamp_x = (stamp_x / frontend_pdf_width) * page_width
                stamp_y = (stamp_y / frontend_pdf_height) * page_height
                logger.info(f"✏️ Rescaled coordinates to: x={stamp_x}, y={stamp_y}")
            else:
                logger.info(f"✅ Dimensions match, using coordinates as-is: x={stamp_x}, y={stamp_y}")
            
            # CRITICAL: Frontend sends coordinates with TOP-origin (Y=0 at top, like canvas)
            # PDF uses BOTTOM-origin (Y=0 at bottom)
            # Convert Y from top-origin to bottom-origin
            try:
                stamp_y_pdf = page_height - stamp_y
            except Exception as e:
                logger.error(f"❌ Error converting Y coordinate: page_height={page_height}, stamp_y={stamp_y}, error={str(e)}")
                stamp_y_pdf = 100  # Fallback value
            
            # IMPORTANT: In canvas (preview), the stamp expands DOWN and RIGHT from the origin point
            # In PDF, it expands UP and RIGHT from the origin point
            # Stamp height is ~90 points, so we need to move the origin DOWN by that amount
            # to compensate for the different expansion direction
            stamp_y_pdf = stamp_y_pdf - 90  # Move down by stamp height to match preview origin
            
            logger.info(f"🔄 Y-coordinate conversion: frontend Y={stamp_y} (top-origin) → PDF Y={stamp_y_pdf} (bottom-origin, adjusted for expansion direction)")
            
            # Map resultado to display name and color
            resultado_map = {
                'APROVADO_SEM_CORRECAO': ('Aprovado sem Correção', (0, 0.7, 0)),  # Green
                'APROVADO_COM_CORRECAO': ('Aprovado com Correção', (1, 0.8, 0)),  # Yellow/Orange
                'REPROVADO': ('Reprovado/Restrição', (1, 0, 0))  # Red
            }
            resultado_display, (r, g, b) = resultado_map.get(resultado, (resultado, (0.5, 0.5, 0.5)))
            
            # Draw colored text for resultado only (no background)
            stamp_canvas.setLineWidth(0)
            stamp_canvas.setFillColorRGB(r, g, b)  # Use color for text only
            stamp_canvas.setFont("Helvetica-Bold", 9)
            
            # NO line breaks - draw resultado in one line
            stamp_canvas.drawString(stamp_x + 3, stamp_y_pdf + 65, resultado_display)
            
            # Draw black text for data and validador
            stamp_canvas.setFillColorRGB(0, 0, 0)  # Black text
            stamp_canvas.setFont("Helvetica", 8)
            stamp_canvas.drawString(stamp_x + 3, stamp_y_pdf + 45, f"{data_validacao}")
            
            # Draw validador (validator) - no line breaks
            stamp_canvas.setFont("Helvetica", 8)
            validador_text = nome_validador[:25]  # Limit to 25 chars (was 18)
            stamp_canvas.drawString(stamp_x + 3, stamp_y_pdf + 25, validador_text)
            
            stamp_canvas.save()
            stamp_buffer.seek(0)
            
            logger.info(f"🎨 Stamp created with color: RGB({r}, {g}, {b}) for {resultado}")
            
            try:
                # Read stamp from buffer - convert to bytes
                stamp_buffer_bytes = BytesIO(stamp_buffer.getvalue())
                stamp_pdf = PdfReader(stamp_buffer_bytes)
            except Exception as e:
                logger.error(f"❌ Error reading stamp PDF from buffer: {str(e)}", exc_info=True)
                raise Exception(f"Erro ao processar carimbo: {str(e)}")
            stamp_page = stamp_pdf.pages[0]
            
            # Apply stamp to specific page or all pages
            try:
                writer = PdfWriter()
                for idx, page in enumerate(original_pdf.pages):
                    # Only apply stamp to the specified page
                    if idx == (carimbo_page - 1):  # carimbo_page is 1-indexed
                        page.merge_page(stamp_page)
                    writer.add_page(page)
            except Exception as e:
                logger.error(f"❌ Error merging stamp with original PDF: {str(e)}", exc_info=True)
                raise Exception(f"Erro ao aplicar carimbo ao PDF: {str(e)}")
            
            # Save stamped PDF
            stamped_buffer = BytesIO()
            writer.write(stamped_buffer)
            stamped_buffer.seek(0)
            
            logger.info(f"🔄 Saving stamped PDF to model...")
            # Save to model
            filename = f"certificado_carimbado_{historico_id}.pdf"
            historico.certificado_carimbado.save(
                filename,
                ContentFile(stamped_buffer.read()),
                save=True
            )
            logger.info(f"✅ File saved to field: {historico.certificado_carimbado.name}")
            
            historico.certificado_validado = True
            historico.save()
            logger.info(f"✅ Model saved successfully! File size: {historico.certificado_carimbado.size} bytes")
            
            try:
                messages.success(request, 'Carimbo aplicado com sucesso!')
            except Exception as msg_error:
                logger.warning(f"⚠️  Could not send success message: {str(msg_error)}")
            
            return redirect('editar_historico_calibracao', historico_id=historico_id)
            
        except Exception as e:
            import traceback
            logger.error(f'❌ Erro ao aplicar carimbo: {str(e)}', exc_info=True)
            messages.error(request, f'Erro ao aplicar carimbo: {str(e)}')
            return redirect('editar_historico_calibracao', historico_id=historico_id)
    
    # GET request - show form
    context = {
        'historico': historico,
        'resultado_choices': HistoricoCalibracao.RESULTADO_CHOICES if hasattr(HistoricoCalibracao, 'RESULTADO_CHOICES') else [
            ('APROVADO_SEM_CORRECAO', 'Aprovado sem Correção'),
            ('APROVADO_COM_CORRECAO', 'Aprovado com Correção'),
            ('REPROVADO', 'Reprovado'),
        ]
    }
    return render(request, 'metrologia/certificado_preview.html', context)


@login_required
def remover_carimbo_certificado_view(request, historico_id):
    """Remove the stamped certificate to allow re-stamping."""
    import os
    
    historico = get_object_or_404(HistoricoCalibracao, id=historico_id)
    
    if request.method == 'POST':
        try:
            logger.info(f"🔄 Removing stamped certificate for historico {historico_id}")
            
            # Check if there's a stamped certificate
            if not historico.certificado_carimbado:
                logger.warning(f"⚠️  No stamped certificate to remove for historico {historico_id}")
                try:
                    messages.warning(request, 'Nenhum carimbo para remover.')
                except Exception as msg_error:
                    logger.warning(f"⚠️  Could not send warning message: {str(msg_error)}")
                return redirect('editar_historico_calibracao', historico_id=historico_id)
            
            # Delete the physical file
            stamped_file_path = historico.certificado_carimbado.path
            if os.path.exists(stamped_file_path):
                try:
                    os.remove(stamped_file_path)
                    logger.info(f"✅ Deleted file: {stamped_file_path}")
                except Exception as e:
                    logger.warning(f"⚠️  Could not delete file {stamped_file_path}: {str(e)}")
            
            # Clear the database field
            historico.certificado_carimbado.delete()
            historico.certificado_validado = False
            historico.save()
            
            logger.info(f"✅ Stamped certificate removed for historico {historico_id}")
            try:
                messages.success(request, 'Carimbo removido com sucesso! Você pode agora carimbar novamente.')
            except Exception as msg_error:
                logger.warning(f"⚠️  Could not send success message: {str(msg_error)}")
            return redirect('editar_historico_calibracao', historico_id=historico_id)
            
        except Exception as e:
            logger.error(f'❌ Error removing stamped certificate: {str(e)}', exc_info=True)
            try:
                messages.error(request, f'Erro ao remover carimbo: {str(e)}')
            except Exception as msg_error:
                logger.warning(f"⚠️  Could not send error message: {str(msg_error)}")
            return redirect('editar_historico_calibracao', historico_id=historico_id)
    
    # GET request - show confirmation
    context = {'historico': historico}
    return render(request, 'metrologia/certificado_preview.html', context)


# ==============================================================================
# STANDARD FILES VIEWS
# ==============================================================================

@login_required
def renomear_arquivo_padrao_view(request, arquivo_id):
    """Rename a standard file."""
    # TODO: Implement standard file model and logic
    if request.method == 'POST':
        novo_nome = request.POST.get('novo_nome')
        if novo_nome:
            # TODO: Update file name
            messages.success(request, 'Arquivo renomeado com sucesso.')
            return redirect('modulo_metrologia')
    
    return HttpResponse('Not implemented yet', status=501)


@login_required
@login_required
def remover_arquivo_padrao_view(request, arquivo_id):
    """Remove a standard file (fallback POST version)."""
    from metrologia.models import ArquivoPadrao
    
    if request.method == 'POST':
        try:
            padrao = ArquivoPadrao.objects.get(id=arquivo_id)
            padrao_nome = padrao.nome
            padrao.delete()
            messages.success(request, f'Padrão "{padrao_nome}" removido com sucesso.')
            # Redirect to referrer if available
            referrer = request.META.get('HTTP_REFERER')
            return redirect(referrer) if referrer else redirect('modulo_metrologia')
        except ArquivoPadrao.DoesNotExist:
            messages.error(request, 'Padrão não encontrado.')
            return redirect('modulo_metrologia')
        except Exception as e:
            messages.error(request, f'Erro ao remover padrão: {str(e)}')
            return redirect('modulo_metrologia')
    
    return HttpResponse('Método não permitido', status=405)


@login_required
def download_arquivo_padrao_view(request, arquivo_id):
    """Download a standard file with correct PDF headers."""
    from metrologia.models import ArquivoPadrao
    from django.http import FileResponse
    
    try:
        padrao = ArquivoPadrao.objects.get(id=arquivo_id)
        arquivo = padrao.arquivo
        
        if not arquivo:
            raise Http404("Arquivo não encontrado")
        
        # Garantir que o arquivo existe
        if not arquivo.storage.exists(arquivo.name):
            raise Http404("Arquivo não existe no servidor")
        
        # Abrir arquivo
        arquivo_aberto = arquivo.open('rb')
        
        # Gerar nome do arquivo para download (garantir que tem .pdf)
        nome_arquivo = f"{padrao.nome}.pdf"
        if not nome_arquivo.endswith('.pdf'):
            nome_arquivo = f"{nome_arquivo}.pdf"
        
        # Criar resposta com headers corretos para PDF
        response = FileResponse(arquivo_aberto, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
        response['Content-Type'] = 'application/pdf'
        
        return response
    except ArquivoPadrao.DoesNotExist:
        raise Http404("Padrão não encontrado")


# ==============================================================================
# IMPORT VIEWS
# ==============================================================================

@login_required
def import_jobs_view(request):
    """View list of import jobs."""
    jobs = ImportJob.objects.all().order_by('-created_at')
    
    paginator = Paginator(jobs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'jobs': page_obj.object_list,
    }
    return render(request, 'shared/dashboard.html', context)


@login_required
def retry_import_job_view(request, job_id):
    """Retry a failed import job."""
    job = get_object_or_404(ImportJob, id=job_id)
    
    if request.method == 'POST':
        # TODO: Implement retry logic
        messages.success(request, 'Importação reiniciada.')
        return redirect('import_jobs')
    
    context = {
        'job': job,
    }
    return render(request, 'shared/dashboard.html', context)


@login_required
def imp_instr_view(request):
    """Importa instrumentos de calibração a partir de arquivo Excel/CSV."""
    import os
    import tempfile
    from metrologia.forms import ImportacaoInstrumentosForm
    
    if request.method == "POST":
        form = ImportacaoInstrumentosForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                uploaded = request.FILES["arquivo_excel"]
                suffix = os.path.splitext(uploaded.name)[1] or ".xlsx"
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                for chunk in uploaded.chunks():
                    tmp.write(chunk)
                tmp.flush()
               
                job = ImportJob.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    filename=uploaded.name,
                    filepath=tmp.name,
                    job_type="INSTRUMENTOS",
                    status="PENDING",
                )

                from qms.tasks import import_instruments_task
                force_sync = os.environ.get("SYNC_IMPORTS", "1") == "1"
                if not force_sync:
                    try:
                        import_instruments_task.delay(str(job.id), tmp.name)
                        messages.success(request, f"Importação enfileirada (job {job.id}).")
                        return redirect("modulo_metrologia")
                    except Exception:
                        force_sync = True
                
                if force_sync:
                    import_instruments_task(job.id, tmp.name)
                    job.refresh_from_db()
                    messages.success(request, f"Importação concluída (job {job.id}). {job.result or ''}")
                    return redirect("modulo_metrologia")
            except Exception as e:
                messages.error(request, f"Erro ao enfileirar importação: {str(e)}")
                return redirect("importar_instrumentos")
    else:
        form = ImportacaoInstrumentosForm()
    
    # Get recent import jobs for this type
    jobs = ImportJob.objects.filter(job_type='INSTRUMENTOS').order_by('-created_at')[:5]
    
    context = {'form': form, 'jobs': jobs}
    return render(request, 'metrologia/imports/instrumentos.html', context)


@login_required
def imp_historico_view(request):
    """Importa históricos de calibração a partir de arquivo Excel/CSV."""
    import os
    import tempfile
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        from metrologia.forms import ImportacaoHistoricoForm
        from metrologia.models import Instrumento, HistoricoCalibracao
    except ImportError as ie:
        logger.error(f"Erro ao importar formulário ou models: {str(ie)}")
        messages.error(request, f"Erro ao importar dependências: {str(ie)}")
        return render(request, 'metrologia/imports/historico.html', {'form': None, 'jobs': []})
    
    if request.method == "POST":
        form = ImportacaoHistoricoForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                uploaded = request.FILES.get("arquivo_excel")
                if not uploaded:
                    messages.error(request, "Nenhum arquivo foi enviado.")
                    jobs = ImportJob.objects.filter(job_type='HISTORICO').order_by('-created_at')[:5]
                    return render(request, 'metrologia/imports/historico.html', {'form': form, 'jobs': jobs})
                
                suffix = os.path.splitext(uploaded.name)[1] or ".xlsx"
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                for chunk in uploaded.chunks():
                    tmp.write(chunk)
                tmp.flush()
                tmp.close()

                job = ImportJob.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    filename=uploaded.name,
                    filepath=tmp.name,
                    job_type="HISTORICO",
                    status="PENDING",
                )

                from qms.tasks import import_historico_task
                force_sync = os.environ.get("SYNC_IMPORTS", "1") == "1"
                if not force_sync:
                    try:
                        import_historico_task.delay(str(job.id), tmp.name)
                        messages.success(request, f"Importação histórico enfileirada (job {job.id}).")
                        return redirect("modulo_metrologia")
                    except Exception as ce:
                        logger.warning(f"Celery não disponível, usando sync: {str(ce)}")
                        force_sync = True
                
                if force_sync:
                    import_historico_task(str(job.id), tmp.name)
                    job.refresh_from_db()
                    try:
                        # Recalcula datas nos instrumentos afetados
                        afetados = HistoricoCalibracao.objects.filter(
                            criado_em__gte=job.created_at
                        ).values_list("instrumento_id", flat=True).distinct()
                        for iid in afetados:
                            inst = Instrumento.objects.filter(id=iid).first()
                            if inst:
                                ultima = HistoricoCalibracao.objects.filter(instrumento=inst).order_by("-data_calibracao").first()
                                if ultima:
                                    inst.data_ultima_calibracao = ultima.data_calibracao
                                    inst.data_proxima_calibracao = ultima.proxima_calibracao
                                else:
                                    inst.data_ultima_calibracao = None
                                    inst.data_proxima_calibracao = None
                                inst.save(update_fields=["data_ultima_calibracao", "data_proxima_calibracao"])
                    except Exception as ex:
                        logger.error(f"Erro ao recalcular datas: {str(ex)}")
                    messages.success(request, f"Histórico importado (job {job.id}). {job.result or ''}")
                    return redirect("modulo_metrologia")
            except Exception as e:
                logger.error(f"Erro na importação de histórico: {str(e)}", exc_info=True)
                messages.error(request, f"Erro ao enfileirar importação: {str(e)}")
                jobs = ImportJob.objects.filter(job_type='HISTORICO').order_by('-created_at')[:5]
                return render(request, 'metrologia/imports/historico.html', {'form': form, 'jobs': jobs})
        else:
            logger.warning(f"Formulário inválido: {form.errors}")
            messages.error(request, f"Formulário inválido: {form.errors}")
    else:
        form = ImportacaoHistoricoForm()
    
    try:
        jobs = ImportJob.objects.filter(job_type='HISTORICO').order_by('-created_at')[:5]
    except Exception as e:
        logger.error(f"Erro ao buscar jobs: {str(e)}")
        jobs = []
    
    context = {'form': form, 'jobs': jobs}
    return render(request, 'metrologia/imports/historico.html', context)


@login_required
def imp_colab_view(request):
    """Importa colaboradores a partir de arquivo Excel/CSV."""
    import os
    import tempfile
    from rh.forms import ImportacaoColaboradoresForm
    
    if request.method == "POST":
        form = ImportacaoColaboradoresForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                uploaded = request.FILES["arquivo_excel"]
                suffix = os.path.splitext(uploaded.name)[1] or ".xlsx"
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                for chunk in uploaded.chunks():
                    tmp.write(chunk)
                tmp.flush()
                tmp.close()

                job = ImportJob.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    filename=uploaded.name,
                    filepath=tmp.name,
                    job_type="COLABORADORES",
                    status="PENDING",
                )

                from qms.tasks import import_colab_task
                force_sync = os.environ.get("SYNC_IMPORTS", "1") == "1"
                if not force_sync:
                    try:
                        import_colab_task.delay(str(job.id), tmp.name)
                        messages.success(request, f"Importação de colaboradores enfileirada (job {job.id}).")
                        return redirect("modulo_rh")
                    except Exception:
                        force_sync = True
                
                if force_sync:
                    import_colab_task(job.id, tmp.name)
                    job.refresh_from_db()
                    messages.success(request, f"Colaboradores importados (job {job.id}). {job.result or ''}")
                    return redirect("modulo_rh")
            except Exception as e:
                messages.error(request, f"Erro ao enfileirar importação: {str(e)}")
                return redirect("importar_colaboradores")
    else:
        form = ImportacaoColaboradoresForm()
    
    jobs = ImportJob.objects.filter(job_type='COLABORADORES').order_by('-created_at')[:5]
    context = {'form': form, 'jobs': jobs}
    return render(request, 'rh/imports/colaboradores.html', context)


@login_required
def imp_hierarquia_view(request):
    """Importa hierarquia organizacional a partir de arquivo Excel/CSV."""
    import os
    import tempfile
    from rh.forms import ImportacaoHierarquiaForm
    
    if request.method == "POST":
        form = ImportacaoHierarquiaForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                uploaded = request.FILES["arquivo_excel"]
                suffix = os.path.splitext(uploaded.name)[1] or ".xlsx"
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                for chunk in uploaded.chunks():
                    tmp.write(chunk)
                tmp.flush()
                tmp.close()

                job = ImportJob.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    filename=uploaded.name,
                    filepath=tmp.name,
                    job_type="HIERARQUIA",
                    status="PENDING",
                )

                from qms.tasks import import_hierarquia_task
                force_sync = os.environ.get("SYNC_IMPORTS", "1") == "1"
                if not force_sync:
                    try:
                        import_hierarquia_task.delay(str(job.id), tmp.name)
                        messages.success(request, f"Importação de hierarquia enfileirada (job {job.id}).")
                        return redirect("modulo_rh")
                    except Exception:
                        force_sync = True
                
                if force_sync:
                    import_hierarquia_task(job.id, tmp.name)
                    job.refresh_from_db()
                    messages.success(request, f"Hierarquia importada (job {job.id}). {job.result or ''}")
                    return redirect("modulo_rh")
            except Exception as e:
                messages.error(request, f"Erro ao enfileirar importação: {str(e)}")
                return redirect("importar_hierarquia")
    else:
        form = ImportacaoHierarquiaForm()
    
    jobs = ImportJob.objects.filter(job_type='HIERARQUIA').order_by('-created_at')[:5]
    context = {'form': form, 'jobs': jobs}
    return render(request, 'rh/imports/hierarquia.html', context)


@login_required
def imp_ferias_view(request):
    """Importa férias a partir de arquivo Excel/CSV."""
    import os
    import tempfile
    from rh.forms import ImportacaoFeriasForm
    
    if request.method == "POST":
        form = ImportacaoFeriasForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                uploaded = request.FILES["arquivo_excel"]
                suffix = os.path.splitext(uploaded.name)[1] or ".xlsx"
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                for chunk in uploaded.chunks():
                    tmp.write(chunk)
                tmp.flush()
                tmp.close()

                job = ImportJob.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    filename=uploaded.name,
                    filepath=tmp.name,
                    job_type="FERIAS",
                    status="PENDING",
                )

                from qms.tasks import import_ferias_task
                force_sync = os.environ.get("SYNC_IMPORTS", "1") == "1"
                if not force_sync:
                    try:
                        import_ferias_task.delay(str(job.id), tmp.name)
                        messages.success(request, f"Importação de férias enfileirada (job {job.id}).")
                        return redirect("modulo_rh")
                    except Exception:
                        force_sync = True
                
                if force_sync:
                    import_ferias_task(job.id, tmp.name)
                    job.refresh_from_db()
                    messages.success(request, f"Férias importadas (job {job.id}). {job.result or ''}")
                    return redirect("modulo_rh")
            except Exception as e:
                messages.error(request, f"Erro ao enfileirar importação: {str(e)}")
                return redirect("importar_ferias")
    else:
        form = ImportacaoFeriasForm()
    
    jobs = ImportJob.objects.filter(job_type='FERIAS').order_by('-created_at')[:5]
    context = {'form': form, 'jobs': jobs}
    return render(request, 'rh/imports/ferias.html', context)


# ==============================================================================
# MEASUREMENT RANGE API VIEWS
# ==============================================================================

@login_required
def api_faixa_medicao_view(request, faixa_id):
    """API endpoint to get measurement range details."""
    try:
        faixa = FaixaMedicao.objects.get(id=faixa_id)
        return JsonResponse({
            'id': faixa.id,
            'minimo': float(faixa.minimo),
            'maximo': float(faixa.maximo),
            'incerteza': float(faixa.incerteza) if faixa.incerteza else None,
        })
    except FaixaMedicao.DoesNotExist:
        return JsonResponse({'error': 'Faixa não encontrada'}, status=404)


# ==============================================================================
# PROCEDURE VIEWS
# ==============================================================================

@login_required
def procedimentos_list_view(request):
    """View list of procedures."""
    procedimentos = Procedimento.objects.all()
    
    # Filter if needed
    search = request.GET.get('search')
    if search:
        procedimentos = procedimentos.filter(
            Q(titulo__icontains=search) | Q(descricao__icontains=search)
        )
    
    paginator = Paginator(procedimentos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'procedimentos': page_obj.object_list,
        'search': search,
    }
    return render(request, 'training/procedimento_lista.html', context)


@login_required
def novo_procedimento_view(request):
    """Create a new procedure."""
    if request.method == 'POST':
        # TODO: Implement form processing
        messages.success(request, 'Procedimento criado com sucesso.')
        return redirect('procedimentos_list')
    
    context = {}
    return render(request, 'training/procedimento_form.html', context)


@login_required
def detalhe_procedimento_view(request, procedimento_id):
    """View procedure details."""
    procedimento = get_object_or_404(Procedimento, id=procedimento_id)
    
    context = {
        'procedimento': procedimento,
    }
    return render(request, 'training/procedimento_detalhe.html', context)


@login_required
def editar_procedimento_view(request, procedimento_id):
    """Edit a procedure."""
    procedimento = get_object_or_404(Procedimento, id=procedimento_id)
    
    if request.method == 'POST':
        # TODO: Implement form processing
        messages.success(request, 'Procedimento atualizado com sucesso.')
        return redirect('detalhe_procedimento', procedimento_id=procedimento_id)
    
    context = {
        'procedimento': procedimento,
    }
    return render(request, 'training/procedimento_form.html', context)


# ==============================================================================
# TEMPLATE DOWNLOAD VIEWS
# ==============================================================================

@login_required
@login_required
def dl_template_historico(request):
    """Template para importação de históricos de calibração com exemplos."""
    import pandas as pd
    from datetime import date, timedelta
    
    # Criar DataFrame com exemplos
    exemplo_data = {
        "TAG": ["INS-001", "INS-002", "INS-003"],
        "FAIXA": ["0-100", "0-50", "-10 a 50"],
        "UNIDADE DE MEDIDA": ["mm", "°C", "mV"],
        "DATA CALIBRAÇÃO": [
            (date.today() - timedelta(days=30)).strftime("%d/%m/%Y"),
            (date.today() - timedelta(days=60)).strftime("%d/%m/%Y"),
            (date.today() - timedelta(days=90)).strftime("%d/%m/%Y"),
        ],
        "DATA APROVAÇÃO": [
            (date.today() - timedelta(days=29)).strftime("%d/%m/%Y"),
            (date.today() - timedelta(days=59)).strftime("%d/%m/%Y"),
            (date.today() - timedelta(days=89)).strftime("%d/%m/%Y"),
        ],
        "N CERTIFICADO": ["CERT-2025-001", "CERT-2025-002", "CERT-2025-003"],
        "CAMINHO DO CERTIFICADO": ["", "", ""],
        "ERRO ENCONTRADO": ["0.5", "0.3", "0.8"],
        "INCERTEZA": ["0.2", "0.15", "0.4"],
        "TOLERANCIA PROCESSO (+/-)": ["1.0", "0.5", "2.0"],
        "RBC (SIM/NAO)": ["SIM", "NAO", "SIM"],
        "RESULTADO": ["APROVADO", "CONDICIONAL", "APROVADO"],
        "FORNECEDOR": ["Laboratorio XYZ", "Laboratorio ABC", "Laboratorio XYZ"],
        "RESPONSÁVEL": ["João Silva", "Maria Santos", "Pedro Costa"],
        "OBSERVAÇÕES": ["Calibração OK", "Atenção a próxima data", "Dentro das especificações"],
    }
    
    df = pd.DataFrame(exemplo_data)
    return dl_df(df, "template_historico.xlsx")


# ==============================================================================
# COLLABORATOR VIEWS
# ==============================================================================

@login_required
def detalhe_colaborador_view(request, colab_id):
    """View collaborator/employee details."""
    colaborador = get_object_or_404(Colaborador, id=colab_id)
    
    context = {
        'colaborador': colaborador,
    }
    return render(request, 'rh/colaborador_detalhe.html', context)


@login_required
def editar_colaborador_view(request, colab_id):
    """Edit collaborator/employee details."""
    colaborador = get_object_or_404(Colaborador, id=colab_id)
    
    if request.method == 'POST':
        # TODO: Implement form processing
        messages.success(request, 'Colaborador atualizado com sucesso.')
        return redirect('detalhe_colaborador', colab_id=colab_id)
    
    context = {
        'colaborador': colaborador,
    }
    return render(request, 'rh/colaborador_form.html', context)


# ==============================================================================
# MEASUREMENT RANGE (FAIXA) MANAGEMENT VIEWS
# ==============================================================================

@login_required
def gerenciar_faixas_instrumento_view(request, instrumento_id):
    """Manage measurement ranges for an instrument."""
    from .forms import FaixaMedicaoForm
    from metrologia.forms import FaixaMedicaoFormWithValidation
    from metrologia.models import FaixaMedicao, FaixaMedicaoPadraoCategoria
    
    instrumento = get_object_or_404(Instrumento, id=instrumento_id)
    faixas = instrumento.faixas.all().order_by('valor_minimo')
    
    # Obter faixas padrão da categoria
    faixas_sugeridas = []
    if instrumento.categoria:
        faixas_sugeridas = FaixaMedicaoPadraoCategoria.objects.filter(
            categoria=instrumento.categoria,
            ativa=True
        ).select_related('unidade').order_by('valor_minimo')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add':
            form = FaixaMedicaoFormWithValidation(request.POST)
            if form.is_valid():
                faixa = form.save(commit=False)
                faixa.instrumento = instrumento
                faixa.save()
                messages.success(request, f'Faixa {faixa.valor_minimo}-{faixa.valor_maximo} adicionada com sucesso.')
                return redirect('gerenciar_faixas_instrumento', instrumento_id=instrumento_id)
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')
        
        elif action == 'add_suggested':
            faixa_sugerida_id = request.POST.get('faixa_sugerida_id')
            try:
                faixa_padrao = FaixaMedicaoPadraoCategoria.objects.get(
                    id=faixa_sugerida_id,
                    categoria=instrumento.categoria
                )
                
                # Verificar se já existe essa faixa
                faixa_existente = FaixaMedicao.objects.filter(
                    instrumento=instrumento,
                    unidade=faixa_padrao.unidade,
                    valor_minimo=faixa_padrao.valor_minimo,
                    valor_maximo=faixa_padrao.valor_maximo
                ).exists()
                
                if faixa_existente:
                    messages.warning(request, f'Faixa {faixa_padrao.valor_minimo}-{faixa_padrao.valor_maximo} já existe para este instrumento.')
                else:
                    # Criar nova faixa baseada na faixa padrão
                    nova_faixa = FaixaMedicao.objects.create(
                        instrumento=instrumento,
                        unidade=faixa_padrao.unidade,
                        valor_minimo=faixa_padrao.valor_minimo,
                        valor_maximo=faixa_padrao.valor_maximo,
                        resolucao=faixa_padrao.resolucao,
                        nominal=faixa_padrao.nominal,
                        tolerancia_mais_menos=faixa_padrao.tolerancia_mais_menos,
                    )
                    messages.success(request, f'Faixa {nova_faixa.valor_minimo}-{nova_faixa.valor_maximo} adicionada com sucesso.')
            except FaixaMedicaoPadraoCategoria.DoesNotExist:
                messages.error(request, 'Faixa sugerida não encontrada.')
            return redirect('gerenciar_faixas_instrumento', instrumento_id=instrumento_id)
        
        elif action == 'delete':
            faixa_id = request.POST.get('faixa_id')
            try:
                faixa = FaixaMedicao.objects.get(id=faixa_id, instrumento=instrumento)
                faixa_str = f"{faixa.valor_minimo}-{faixa.valor_maximo}"
                faixa.delete()
                messages.success(request, f'Faixa {faixa_str} removida com sucesso.')
            except FaixaMedicao.DoesNotExist:
                messages.error(request, 'Faixa não encontrada.')
            return redirect('gerenciar_faixas_instrumento', instrumento_id=instrumento_id)
    else:
        form = FaixaMedicaoFormWithValidation()
    
    context = {
        'instrumento': instrumento,
        'faixas': faixas,
        'faixas_sugeridas': faixas_sugeridas,
        'form': form,
    }
    return render(request, 'metrologia/gerenciar_faixas.html', context)


@login_required
def editar_faixa_view(request, faixa_id):
    """Edit a measurement range."""
    from metrologia.forms import FaixaMedicaoFormWithValidation
    from metrologia.models import FaixaMedicao
    
    faixa = get_object_or_404(FaixaMedicao, id=faixa_id)
    
    if request.method == 'POST':
        form = FaixaMedicaoFormWithValidation(request.POST, instance=faixa)
        if form.is_valid():
            faixa_obj = form.save()
            messages.success(request, 'Faixa atualizada com sucesso.')
            return redirect('gerenciar_faixas_instrumento', instrumento_id=faixa_obj.instrumento.id)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = FaixaMedicaoFormWithValidation(instance=faixa)
    
    context = {
        'form': form,
        'faixa': faixa,
        'instrumento': faixa.instrumento,
    }
    return render(request, 'metrologia/editar_faixa.html', context)


# ==============================================================================
# CALIBRATION HISTORY RESULTS MANAGEMENT VIEWS
# ==============================================================================

@login_required
def editar_historico_calibracao_view(request, historico_id):
    """Edit calibration history and its range results."""
    from .forms_historico import HistoricoCalibracaoForm, validate_pdf_file
    from .forms import ResultadoFaixaCalibracaoForm
    from metrologia.models import ResultadoFaixaCalibracao, FaixaMedicao
    from django.db.models import Prefetch
    
    # Prefetch padroes_arquivo para evitar N+1 queries e garantir que estejam carregados
    try:
        historico = HistoricoCalibracao.objects.prefetch_related('padroes_arquivo').get(id=historico_id)
    except HistoricoCalibracao.DoesNotExist:
        raise Http404("Histórico de calibração não encontrado")
    
    resultados_faixa = historico.resultados_faixa.all().select_related('faixa')
    
    if request.method == 'POST':
        action = request.POST.get('acao') or request.POST.get('action')

        # Handle standard PDF upload (simples)
        if action == 'upload_padroes':
            from metrologia.models import ArquivoPadrao
            uploaded_files = request.FILES.getlist('novos_arquivos_padroes')
            if uploaded_files:
                from .forms_historico import validate_pdf_file
                count = 0
                for uploaded_file in uploaded_files:
                    try:
                        validate_pdf_file(uploaded_file)
                        ArquivoPadrao.objects.create(
                            historico=historico,
                            nome=uploaded_file.name.replace('.pdf', ''),
                            arquivo=uploaded_file
                        )
                        count += 1
                    except Exception as e:
                        messages.error(request, f'Erro ao anexar {uploaded_file.name}: {str(e)}')
                if count > 0:
                    messages.success(request, f'{count} padrão(ões) anexado(s) com sucesso.')
            else:
                messages.warning(request, 'Selecione pelo menos um arquivo PDF.')
            return redirect('editar_historico_calibracao', historico_id=historico_id)

        # Handle certificate removal
        if action == 'remover_certificado_original':
            if historico.certificado:
                historico.certificado.delete()
                historico.save()
                messages.success(request, 'Certificado original removido com sucesso.')
            return redirect('editar_historico_calibracao', historico_id=historico_id)

        elif action == 'remover_certificado_carimbado':
            if historico.certificado_carimbado:
                historico.certificado_carimbado.delete()
                historico.certificado_validado = False
                historico.save()
                messages.success(request, 'Certificado carimbado removido com sucesso.')
            return redirect('editar_historico_calibracao', historico_id=historico_id)

        # Handle standard PDF removal
        elif action and action.startswith('remover_padrao_'):
            from metrologia.models import ArquivoPadrao
            padrao_id = action.replace('remover_padrao_', '')
            try:
                padrao = ArquivoPadrao.objects.get(id=padrao_id)
                padrao_nome = padrao.nome
                padrao.delete()
                messages.success(request, f'Padrão "{padrao_nome}" removido com sucesso.')
            except ArquivoPadrao.DoesNotExist:
                messages.error(request, 'Padrão não encontrado.')
            return redirect('editar_historico_calibracao', historico_id=historico_id)

        # Handle certificate upload
        elif action == 'anexar_certificado':
            if 'certificado' in request.FILES:
                try:
                    historico.certificado = request.FILES['certificado']
                    historico.save()
                    messages.success(request, 'Certificado anexado com sucesso.')
                except Exception as e:
                    messages.error(request, f'Erro ao anexar certificado: {str(e)}')
            else:
                messages.warning(request, 'Selecione um arquivo de certificado para anexar.')
            return redirect('editar_historico_calibracao', historico_id=historico_id)

        if action == 'update_history':
            form = HistoricoCalibracaoForm(request.POST, request.FILES, instance=historico)
            
            # Check if files were uploaded
            uploaded_files = request.FILES.getlist('novos_arquivos_padroes')
            has_files = any(f for f in uploaded_files if f)
            
            print(f"[DEBUG] FILES RECEIVED: {len(uploaded_files)} files")
            print(f"[DEBUG] HAS_FILES: {has_files}")
            for f in uploaded_files:
                if f:
                    print(f"[DEBUG] File: {f.name} ({f.size} bytes)")
            
            if form.is_valid():
                form.save()
                print(f"[DEBUG] Form saved for historico {historico_id}")
                
                # PROCESSAR ARQUIVOS DE PADRÃO MANUALMENTE
                if uploaded_files:
                    print(f"[DEBUG] Processing {len(uploaded_files)} files...")
                    for idx, uploaded_file in enumerate(uploaded_files):
                        if uploaded_file:
                            try:
                                validate_pdf_file(uploaded_file)
                                print(f"[DEBUG] File {idx+1} validated: {uploaded_file.name}")
                                
                                # Criar ArquivoPadrao vinculado diretamente ao histórico
                                novo_padrao = ArquivoPadrao.objects.create(
                                    historico=historico,
                                    nome=uploaded_file.name.replace('.pdf', ''),
                                    descricao='',
                                    arquivo=uploaded_file
                                )
                                print(f"[DEBUG] ArquivoPadrao created: {novo_padrao.id}")
                            except Exception as e:
                                print(f"[ERROR] Failed to process {uploaded_file.name}: {str(e)}")
                                import traceback
                                traceback.print_exc()
                
                # Verificar padrões salvos
                historico.refresh_from_db()
                padroes_count = historico.padroes_arquivo.count()
                print(f"[DEBUG] Total padrões agora: {padroes_count}")
                
                # Feedback message
                if has_files:
                    messages.success(request, f'Histórico atualizado e {len([f for f in uploaded_files if f])} arquivo(s) adicionado(s) com sucesso.')
                else:
                    messages.success(request, 'Histórico atualizado com sucesso.')
                
                return redirect('editar_historico_calibracao', historico_id=historico_id)
            else:
                # Mostrar erros específicos
                error_msg = 'Erro ao atualizar histórico: '
                for field, errors in form.errors.items():
                    error_msg += f"{field}: {', '.join(errors)}. "
                print(f"[ERROR] Form errors: {form.errors}")
                messages.error(request, error_msg)
        
        elif action == 'update_resultado':
            resultado_id = request.POST.get('resultado_id')
            try:
                resultado = ResultadoFaixaCalibracao.objects.get(id=resultado_id, historico=historico)
                form = ResultadoFaixaCalibracaoForm(request.POST, instance=resultado)
                if form.is_valid():
                    # Não atribuir o valor de resultado do formulário, deixar o save() calcular
                    resultado = form.save(commit=False)
                    # O método save() do modelo será chamado, que recalcula resultado automaticamente
                    resultado.save()
                    messages.success(request, 'Resultado da faixa atualizado com sucesso.')
                else:
                    # Exibir erros detalhados no feedback
                    error_msg = 'Erro ao atualizar resultado: '
                    for field, errors in form.errors.items():
                        error_msg += f"{field}: {', '.join(errors)}. "
                    messages.error(request, error_msg)
            except ResultadoFaixaCalibracao.DoesNotExist:
                messages.error(request, 'Resultado não encontrado.')
            return redirect('editar_historico_calibracao', historico_id=historico_id)
        
        elif action == 'delete_resultado':
            resultado_id = request.POST.get('resultado_id')
            try:
                resultado = ResultadoFaixaCalibracao.objects.get(id=resultado_id, historico=historico)
                resultado.delete()
                messages.success(request, 'Resultado removido com sucesso.')
            except ResultadoFaixaCalibracao.DoesNotExist:
                messages.error(request, 'Resultado não encontrado.')
            return redirect('editar_historico_calibracao', historico_id=historico_id)
        
        elif action == 'add_faixa':
            faixa_id = request.POST.get('faixa_id')
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            
            try:
                faixa = FaixaMedicao.objects.get(id=faixa_id, instrumento=historico.instrumento)
                # Check if result already exists
                resultado, created = ResultadoFaixaCalibracao.objects.get_or_create(
                    historico=historico,
                    faixa=faixa,
                    defaults={
                        'valor_minimo': faixa.valor_minimo,
                        'valor_maximo': faixa.valor_maximo,
                        'tolerancia': faixa.tolerancia_mais_menos,  # Auto-fill from faixa
                    }
                )
                if created:
                    messages.success(request, f'Faixa {faixa.valor_minimo} a {faixa.valor_maximo} adicionada com sucesso.')
                else:
                    messages.info(request, f'Faixa {faixa.valor_minimo} a {faixa.valor_maximo} já estava cadastrada.')
            except FaixaMedicao.DoesNotExist:
                messages.error(request, 'Faixa não encontrada.')
            
            # Return JSON for AJAX requests
            if is_ajax:
                from django.http import JsonResponse
                return JsonResponse({'status': 'success', 'message': 'Faixa adicionada com sucesso.'})
            
            return redirect('editar_historico_calibracao', historico_id=historico_id)
    
    historico_form = HistoricoCalibracaoForm(instance=historico)
    resultado_form = ResultadoFaixaCalibracaoForm()
    
    # Get measurement ranges for this instrument
    faixas_disponiveis = FaixaMedicao.objects.filter(
        instrumento=historico.instrumento
    ).order_by('valor_minimo')
    
    # Get faixas that already have results
    faixas_com_resultados = set(resultados_faixa.values_list('faixa_id', flat=True))
    
    # Get faixas that don't have results yet
    faixas_sem_resultados = [f for f in faixas_disponiveis if f.id not in faixas_com_resultados]
    
    # DEBUG: Log padroes count before rendering
    padroes_count = historico.padroes_arquivo.count()
    print(f"[DEBUG] Rendering editar_historico: historico={historico.id}, padroes_count={padroes_count}")
    
    context = {
        'historico': historico,
        'instrumento': historico.instrumento,
        'historico_form': historico_form,
        'resultados_faixa': resultados_faixa,
        'resultado_form': resultado_form,
        'faixas_disponiveis': faixas_disponiveis,
        'faixas_sem_resultados': faixas_sem_resultados,
    }
    return render(request, 'metrologia/editar_historico.html', context)


# ==============================================================================
# INSTRUMENT LISTING AND FILTERING VIEWS
# ==============================================================================

@login_required
def listar_instrumentos_view(request):
    """List all instruments with filtering and pagination."""
    from datetime import date, timedelta
    
    # Base query
    instrumentos = Instrumento.objects.all().select_related('setor', 'categoria').prefetch_related('faixas', 'historicos')
    
    # Get filters from request
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')
    categoria_filter = request.GET.get('categoria', '')
    setor_filter = request.GET.get('setor', '')
    ativo_filter = request.GET.get('ativo', '')
    sort_by = request.GET.get('sort', 'tag')  # Campo de ordenação
    sort_dir = request.GET.get('dir', 'asc')  # Direção: asc ou desc
    
    # Validar campo de ordenação para prevenir SQL injection
    VALID_SORT_FIELDS = ['tag', 'descricao', 'categoria__nome', 'setor__nome', 'data_proxima_calibracao', 'ativo']
    if sort_by not in VALID_SORT_FIELDS:
        sort_by = 'tag'
    if sort_dir not in ['asc', 'desc']:
        sort_dir = 'asc'
    
    # Apply search filter
    if search_query:
        instrumentos = instrumentos.filter(
            Q(tag__icontains=search_query) |
            Q(descricao__icontains=search_query) |
            Q(codigo__icontains=search_query)
        )
    
    # Apply status filter
    today = date.today()
    if status_filter == 'vencidos':
        instrumentos = instrumentos.filter(
            data_proxima_calibracao__lt=today,
            ativo=True
        )
    elif status_filter == 'avencer':
        thirty_days = today + timedelta(days=30)
        instrumentos = instrumentos.filter(
            data_proxima_calibracao__gte=today,
            data_proxima_calibracao__lte=thirty_days,
            ativo=True
        )
    elif status_filter == 'vigentes':
        thirty_days = today + timedelta(days=30)
        instrumentos = instrumentos.filter(
            data_proxima_calibracao__gt=thirty_days,
            ativo=True
        )
    
    # Apply categoria filter
    if categoria_filter:
        instrumentos = instrumentos.filter(categoria__id=categoria_filter)
    
    # Apply setor filter
    if setor_filter:
        instrumentos = instrumentos.filter(setor__id=setor_filter)
    
    # Apply ativo filter
    if ativo_filter == 'ativos':
        instrumentos = instrumentos.filter(ativo=True)
    elif ativo_filter == 'inativos':
        instrumentos = instrumentos.filter(ativo=False)
    
    # Apply sorting
    order_field = sort_by if sort_dir == 'asc' else f'-{sort_by}'
    instrumentos = instrumentos.order_by(order_field)
    
    # Pagination with caching for large datasets
    page_number = PaginationHelper.get_page_from_request(request)
    cache_key = f'instrumentos_count_filters_{search_query}_{status_filter}_{categoria_filter}_{setor_filter}_{ativo_filter}_{sort_by}_{sort_dir}'
    
    paginator = OffsetPaginator(page_size=50, cache_count=True)
    page_items, pagination_metadata = paginator.paginate_queryset(
        instrumentos,
        page=page_number,
        cache_key=cache_key
    )
    
    # Get filter options for dropdowns
    from django.db.models import F
    from django.db.models.functions import Lower
    categorias = CategoriaInstrumento.objects.all().order_by(Lower('nome'))
    setores = Setor.objects.all().order_by(Lower('nome'))
    
    context = {
        'page_obj': page_items,  # For compatibility with tests
        'paginator': paginator,  # Expose paginator for accessing per_page
        'page_items': page_items,
        'pagination': pagination_metadata.to_dict(),
        'instrumentos': page_items,
        'categorias': categorias,
        'setores': setores,
        'search_query': search_query,
        'status_filter': status_filter,
        'categoria_filter': categoria_filter,
        'setor_filter': setor_filter,
        'ativo_filter': ativo_filter,
        'total_instrumentos': pagination_metadata.total_items,
        'today': today,
        'today_30days': today + timedelta(days=30),
        'sort_by': sort_by,
        'sort_dir': sort_dir,
    }
    return render(request, 'metrologia/instrumentos_lista.html', context)


@login_required
def estatisticas_calibracao_view(request):
    """View calibration statistics and analytics."""
    from django.db.models import Count, Avg, Max, Min
    from datetime import date, timedelta
    
    today = date.today()
    
    # Overall statistics
    total_instrumentos = Instrumento.objects.count()
    total_vencidos = Instrumento.objects.filter(
        data_proxima_calibracao__lt=today,
        ativo=True
    ).count()
    
    vencer_30_dias = Instrumento.objects.filter(
        data_proxima_calibracao__gte=today,
        data_proxima_calibracao__lte=today + timedelta(days=30),
        ativo=True
    ).count()
    
    total_vigentes = Instrumento.objects.filter(
        data_proxima_calibracao__gte=today,
        ativo=True
    ).count()
    
    # Calibration history statistics
    total_historicos = HistoricoCalibracao.objects.count()
    aprovados = HistoricoCalibracao.objects.filter(
        resultado='APROVADO_SEM_CORRECAO'
    ).count()
    com_correcao = HistoricoCalibracao.objects.filter(
        resultado='APROVADO_COM_CORRECAO'
    ).count()
    reprovados = HistoricoCalibracao.objects.filter(
        resultado='REPROVADO'
    ).count()
    
    # Per category statistics
    por_categoria = CategoriaInstrumento.objects.annotate(
        total=Count('instrumento__id'),
        vencidos=Count('instrumento', filter=Q(instrumento__data_proxima_calibracao__lt=today, instrumento__ativo=True))
    ).filter(total__gt=0)
    
    # Per sector statistics
    por_setor = Setor.objects.annotate(
        total=Count('instrumento__id'),
        vencidos=Count('instrumento', filter=Q(instrumento__data_proxima_calibracao__lt=today, instrumento__ativo=True))
    ).filter(total__gt=0)
    
    context = {
        'total_instrumentos': total_instrumentos,
        'total_vencidos': total_vencidos,
        'vencer_30_dias': vencer_30_dias,
        'total_vigentes': total_vigentes,
        'total_historicos': total_historicos,
        'aprovados': aprovados,
        'com_correcao': com_correcao,
        'reprovados': reprovados,
        'por_categoria': por_categoria,
        'por_setor': por_setor,
        'percentage_vencidos': round((total_vencidos / total_instrumentos * 100) if total_instrumentos > 0 else 0, 1),
        'percentage_aprovados': round((aprovados / total_historicos * 100) if total_historicos > 0 else 0, 1),
    }
    return render(request, 'metrologia/estatisticas_calibracao.html', context)


# ==============================================================================
# EXPORT VIEWS - FASE 5
# ==============================================================================

@login_required
def exportar_instrumentos_view(request):
    """Export instruments list based on applied filters."""
    from metrologia.exportadores import ExportadorInstrumentos
    
    # Get filters from request
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')
    categoria_filter = request.GET.get('categoria', '')
    setor_filter = request.GET.get('setor', '')
    ativo_filter = request.GET.get('ativo', '')
    formato = request.GET.get('formato', 'excel')  # excel, csv, pdf
    
    # Build queryset with filters (same as listar_instrumentos_view)
    instrumentos = Instrumento.objects.all().select_related('setor', 'categoria')
    
    if search_query:
        instrumentos = instrumentos.filter(
            Q(tag__icontains=search_query) |
            Q(descricao__icontains=search_query) |
            Q(codigo__icontains=search_query)
        )
    
    today = date.today()
    if status_filter == 'vencidos':
        instrumentos = instrumentos.filter(
            data_proxima_calibracao__lt=today,
            ativo=True
        )
    elif status_filter == 'avencer':
        thirty_days = today + timedelta(days=30)
        instrumentos = instrumentos.filter(
            data_proxima_calibracao__gte=today,
            data_proxima_calibracao__lte=thirty_days,
            ativo=True
        )
    elif status_filter == 'vigentes':
        instrumentos = instrumentos.filter(
            data_proxima_calibracao__gte=today,
            ativo=True
        )
    
    if categoria_filter:
        instrumentos = instrumentos.filter(categoria__id=categoria_filter)
    
    if setor_filter:
        instrumentos = instrumentos.filter(setor__id=setor_filter)
    
    if ativo_filter == 'ativos':
        instrumentos = instrumentos.filter(ativo=True)
    elif ativo_filter == 'inativos':
        instrumentos = instrumentos.filter(ativo=False)
    
    # Order by tag
    instrumentos = instrumentos.order_by('tag')
    
    # Get exporter
    filtros = {
        'search': search_query,
        'status': status_filter,
        'categoria': categoria_filter,
        'setor': setor_filter,
        'ativo': ativo_filter,
    }
    exportador = ExportadorInstrumentos(instrumentos, filtros_aplicados=filtros)
    
    # Export in requested format
    try:
        if formato == 'excel':
            return exportador.exportar_excel()
        elif formato == 'csv':
            return exportador.exportar_csv()
        elif formato == 'pdf':
            return exportador.exportar_pdf()
        else:
            return exportador.exportar_excel()  # Default
    except ImportError as e:
        messages.error(request, f'Erro: {str(e)}')
        return redirect('listar_instrumentos')


@login_required
def exportar_estatisticas_view(request):
    """Export statistics report."""
    from metrologia.exportadores import ExportadorEstatisticas
    
    formato = request.GET.get('formato', 'excel')  # excel, pdf
    
    # Get statistics data (same as estatisticas_calibracao_view)
    today = date.today()
    
    total_instrumentos = Instrumento.objects.count()
    total_vencidos = Instrumento.objects.filter(
        data_proxima_calibracao__lt=today,
        ativo=True
    ).count()
    
    vencer_30_dias = Instrumento.objects.filter(
        data_proxima_calibracao__gte=today,
        data_proxima_calibracao__lte=today + timedelta(days=30),
        ativo=True
    ).count()
    
    total_vigentes = Instrumento.objects.filter(
        data_proxima_calibracao__gte=today,
        ativo=True
    ).count()
    
    total_historicos = HistoricoCalibracao.objects.count()
    aprovados = HistoricoCalibracao.objects.filter(
        resultado='APROVADO_SEM_CORRECAO'
    ).count()
    com_correcao = HistoricoCalibracao.objects.filter(
        resultado='APROVADO_COM_CORRECAO'
    ).count()
    reprovados = HistoricoCalibracao.objects.filter(
        resultado='REPROVADO'
    ).count()
    
    por_categoria = CategoriaInstrumento.objects.annotate(
        total=Count('instrumento__id'),
        vencidos=Count('instrumento', filter=Q(instrumento__data_proxima_calibracao__lt=today, instrumento__ativo=True))
    ).filter(total__gt=0)
    
    por_setor = Setor.objects.annotate(
        total=Count('instrumento__id'),
        vencidos=Count('instrumento', filter=Q(instrumento__data_proxima_calibracao__lt=today, instrumento__ativo=True))
    ).filter(total__gt=0)
    
    data = {
        'total_instrumentos': total_instrumentos,
        'total_vencidos': total_vencidos,
        'vencer_30_dias': vencer_30_dias,
        'total_vigentes': total_vigentes,
        'total_historicos': total_historicos,
        'aprovados': aprovados,
        'com_correcao': com_correcao,
        'reprovados': reprovados,
        'por_categoria': por_categoria,
        'por_setor': por_setor,
        'percentage_vencidos': round((total_vencidos / total_instrumentos * 100) if total_instrumentos > 0 else 0, 1),
        'percentage_aprovados': round((aprovados / total_historicos * 100) if total_historicos > 0 else 0, 1),
    }
    
    exportador = ExportadorEstatisticas(data)
    
    try:
        if formato == 'excel':
            return exportador.exportar_excel()
        elif formato == 'pdf':
            return exportador.exportar_pdf()
        else:
            return exportador.exportar_excel()  # Default
    except ImportError as e:
        messages.error(request, f'Erro: {str(e)}')
        return redirect('estatisticas_calibracao')


@login_required
def relatorio_vencidos_view(request):
    """Gera relatório de instrumentos vencidos."""
    formato = request.GET.get('formato', 'excel')  # excel, pdf
    
    today = date.today()
    
    # Pegar apenas instrumentos vencidos
    instrumentos_vencidos = Instrumento.objects.filter(
        data_proxima_calibracao__lt=today,
        ativo=True
    ).select_related('setor', 'categoria').order_by('data_proxima_calibracao')
    
    if formato == 'excel':
        from metrologia.exportadores import ExportadorInstrumentos
        exportador = ExportadorInstrumentos(instrumentos_vencidos)
        return exportador.exportar_excel()
    elif formato == 'pdf':
        from metrologia.exportadores import ExportadorInstrumentos
        exportador = ExportadorInstrumentos(instrumentos_vencidos)
        return exportador.exportar_pdf()
    else:
        from metrologia.exportadores import ExportadorInstrumentos
        exportador = ExportadorInstrumentos(instrumentos_vencidos)
        return exportador.exportar_excel()


# ==============================================================================
# INSTRUMENT SUBSTITUTION AND REFERENCE MANAGEMENT
# ==============================================================================

@login_required
def substituir_instrumento_view(request, instrumento_id):
    """
    View para substituição de instrumento com reutilização de código.
    Permite vincular um instrumento a uma InstrumentoReferencia existente
    ou criar uma nova referência.
    """
    from metrologia.models import Instrumento, InstrumentoReferencia, FaixaMedicaoPadrao
    from django.db import transaction
    
    instrumento = get_object_or_404(Instrumento, id=instrumento_id)
    
    if request.method == 'POST':
        referencia_id = request.POST.get('referencia_id')
        copiar_faixas = request.POST.get('copiar_faixas', 'off') == 'on'
        
        # Atualizar dados do instrumento se fornecidos
        novo_fabricante = request.POST.get('fabricante', '').strip()
        novo_modelo = request.POST.get('modelo', '').strip()
        nova_serie = request.POST.get('serie', '').strip()
        
        try:
            with transaction.atomic():
                # Atualizar dados do instrumento
                if novo_fabricante:
                    instrumento.fabricante = novo_fabricante
                if novo_modelo:
                    instrumento.modelo = novo_modelo
                if nova_serie:
                    instrumento.serie = nova_serie
                
                if referencia_id:
                    # Vincular a referência existente
                    referencia = get_object_or_404(InstrumentoReferencia, id=referencia_id)
                    instrumento.referencia = referencia
                    instrumento.save()
                    
                    # Copiar faixas da template se solicitado
                    if copiar_faixas:
                        faixas_padrao = FaixaMedicaoPadrao.objects.filter(
                            referencia_instrumento=referencia,
                            ativa=True
                        )
                        
                        for faixa_padrao in faixas_padrao:
                            FaixaMedicao.objects.create(
                                instrumento=instrumento,
                                unidade=faixa_padrao.unidade,
                                valor_minimo=faixa_padrao.valor_minimo,
                                valor_maximo=faixa_padrao.valor_maximo,
                                resolucao=faixa_padrao.resolucao,
                                nominal=faixa_padrao.nominal,
                                tolerancia_mais_menos=faixa_padrao.tolerancia_mais_menos,
                                faixa_padrao=faixa_padrao
                            )
                    
                    messages.success(request, f'Instrumento vinculado a referência "{referencia.codigo_referencia}"')
                else:
                    messages.error(request, 'Selecione uma referência válida.')
                    
        except Exception as e:
            logger.error(f"Erro ao substituir instrumento {instrumento_id}: {str(e)}")
            messages.error(request, f'Erro ao vincular instrumento: {str(e)}')
        
        return redirect('visualizar_instrumento', instrumento_id=instrumento_id)
    
    # GET request - mostrar formulário
    referencias = InstrumentoReferencia.objects.filter(
        categoria=instrumento.categoria
    ).order_by('codigo_referencia')
    
    referencia_atual = instrumento.referencia
    
    # Se tem referência atual, mostrar as faixas padrão disponíveis
    faixas_disponiveis = []
    if referencia_atual:
        faixas_disponiveis = list(
            FaixaMedicaoPadrao.objects.filter(
                referencia_instrumento=referencia_atual,
                ativa=True
            ).select_related('unidade')
        )
    
    context = {
        'instrumento': instrumento,
        'referencias': referencias,
        'referencia_atual': referencia_atual,
        'faixas_disponiveis': faixas_disponiveis,
    }
    return render(request, 'metrologia/substituir_instrumento.html', context)


@login_required
def copiar_faixas_padrao_view(request, instrumento_id):
    """
    View para copiar faixas de uma template FaixaMedicaoPadrao
    para um instrumento existente.
    """
    from metrologia.models import Instrumento, FaixaMedicaoPadrao, FaixaMedicao
    from django.db import transaction
    
    instrumento = get_object_or_404(Instrumento, id=instrumento_id)
    
    if not instrumento.referencia:
        messages.error(request, 'Instrumento não está vinculado a uma referência.')
        return redirect('visualizar_instrumento', instrumento_id=instrumento_id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Remover faixas existentes (opcional)
                remover_existentes = request.POST.get('remover_existentes', 'off') == 'on'
                
                if remover_existentes:
                    FaixaMedicao.objects.filter(instrumento=instrumento).delete()
                
                # Copiar faixas padrão
                faixas_padrao = FaixaMedicaoPadrao.objects.filter(
                    referencia_instrumento=instrumento.referencia,
                    ativa=True
                )
                
                criadas = 0
                for faixa_padrao in faixas_padrao:
                    faixa, created = FaixaMedicao.objects.get_or_create(
                        instrumento=instrumento,
                        unidade=faixa_padrao.unidade,
                        valor_minimo=faixa_padrao.valor_minimo,
                        valor_maximo=faixa_padrao.valor_maximo,
                        defaults={
                            'resolucao': faixa_padrao.resolucao,
                            'nominal': faixa_padrao.nominal,
                            'tolerancia_mais_menos': faixa_padrao.tolerancia_mais_menos,
                            'faixa_padrao': faixa_padrao
                        }
                    )
                    if created:
                        criadas += 1
                
                messages.success(request, f'{criadas} faixa(s) copiada(s) da template.')
                
        except Exception as e:
            logger.error(f"Erro ao copiar faixas padrão para instrumento {instrumento_id}: {str(e)}")
            messages.error(request, f'Erro ao copiar faixas: {str(e)}')
        
        return redirect('visualizar_instrumento', instrumento_id=instrumento_id)
    
    # GET request - mostrar confirmação
    faixas_padrao = list(
        FaixaMedicaoPadrao.objects.filter(
            referencia_instrumento=instrumento.referencia,
            ativa=True
        ).select_related('unidade')
    )
    
    context = {
        'instrumento': instrumento,
        'faixas_padrao': faixas_padrao,
    }
    return render(request, 'metrologia/copiar_faixas_padrao.html', context)


@login_required
def listar_substitucoes_view(request, codigo_referencia):
    """
    View para listar todos os instrumentos relacionados a uma referência,
    mostrando histórico de substituições.
    """
    from metrologia.models import InstrumentoReferencia, Instrumento
    
    referencia = get_object_or_404(InstrumentoReferencia, codigo_referencia=codigo_referencia)
    
    # Listar todos os instrumentos vinculados
    instrumentos = Instrumento.objects.filter(
        referencia=referencia
    ).select_related('categoria').order_by('-id')
    
    # Agrupar por instrumento ativo e substituídos
    ativo = instrumentos.filter(ativo=True).first()
    substituidos = instrumentos.filter(ativo=False).order_by('-id')
    
    context = {
        'referencia': referencia,
        'instrumento_ativo': ativo,
        'instrumentos_substituidos': substituidos,
        'total_substituicoes': instrumentos.count() - 1,
    }
    return render(request, 'metrologia/historico_substitucoes.html', context)


# ==============================================================================
# EDIÇÃO DE INSTRUMENTO
# ==============================================================================

@login_required
def editar_instrumento_view(request, instrumento_id):
    """View para editar instrumento com formulário customizado."""
    from django.db import transaction
    
    instrumento = get_object_or_404(Instrumento, id=instrumento_id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Atualizar campos básicos
                instrumento.tag = request.POST.get('tag', instrumento.tag)
                instrumento.codigo = request.POST.get('codigo', instrumento.codigo)
                instrumento.descricao = request.POST.get('descricao', instrumento.descricao)
                instrumento.fabricante = request.POST.get('fabricante', instrumento.fabricante)
                instrumento.modelo = request.POST.get('modelo', instrumento.modelo)
                instrumento.serie = request.POST.get('serie', instrumento.serie)
                
                # Atualizar categoria
                categoria_id = request.POST.get('categoria')
                if categoria_id:
                    try:
                        instrumento.categoria = CategoriaInstrumento.objects.get(id=categoria_id)
                    except CategoriaInstrumento.DoesNotExist:
                        pass
                
                # Atualizar setor
                setor_id = request.POST.get('setor')
                if setor_id:
                    try:
                        from organization.models import Setor
                        instrumento.setor = Setor.objects.get(id=setor_id)
                    except:
                        pass
                
                # Atualizar responsável
                responsavel_id = request.POST.get('responsavel')
                if responsavel_id:
                    try:
                        from rh.models import Colaborador
                        instrumento.responsavel = Colaborador.objects.get(id=responsavel_id)
                    except:
                        pass
                
                instrumento.localizacao = request.POST.get('localizacao', instrumento.localizacao)
                
                # Atualizar datas e frequência
                data_ultima = request.POST.get('data_ultima_calibracao')
                if data_ultima:
                    try:
                        instrumento.data_ultima_calibracao = datetime.strptime(data_ultima, '%Y-%m-%d').date()
                    except:
                        pass
                
                data_proxima = request.POST.get('data_proxima_calibracao')
                if data_proxima:
                    try:
                        instrumento.data_proxima_calibracao = datetime.strptime(data_proxima, '%Y-%m-%d').date()
                    except:
                        pass
                
                frequencia = request.POST.get('frequencia_meses')
                if frequencia:
                    try:
                        instrumento.frequencia_meses = int(frequencia)
                    except:
                        pass
                
                # Atualizar tolerância
                tolerancia = request.POST.get('tolerancia_processo')
                if tolerancia:
                    try:
                        instrumento.tolerancia_processo = Decimal(tolerancia)
                    except:
                        pass
                
                # Atualizar status
                instrumento.ativo = request.POST.get('ativo') == 'on'
                
                instrumento.save()
                messages.success(request, 'Instrumento atualizado com sucesso!')
                return redirect('visualizar_instrumento', instrumento_id=instrumento.id)
                
        except Exception as e:
            logger.error(f"Erro ao editar instrumento {instrumento_id}: {str(e)}")
            messages.error(request, f'Erro ao atualizar instrumento: {str(e)}')
    
    # Preparar contexto com dados para o formulário
    from organization.models import Setor
    from rh.models import Colaborador
    
    categorias = CategoriaInstrumento.objects.all()
    setores = Setor.objects.all()
    responsaveis = Colaborador.objects.all()
    
    context = {
        'instrumento': instrumento,
        'categorias': categorias,
        'setores': setores,
        'responsaveis': responsaveis,
    }
    
    return render(request, 'metrologia/editar_instrumento.html', context)


@login_required
@require_POST
def atualizar_datas_calibracao_view(request, instrumento_id):
    """Atualiza as datas de calibração do instrumento baseado no histórico."""
    from dateutil.relativedelta import relativedelta
    
    instrumento = get_object_or_404(Instrumento, id=instrumento_id)
    
    try:
        # Buscar o histórico mais recente
        ultimo_historico = HistoricoCalibracao.objects.filter(
            instrumento=instrumento
        ).order_by('-data_calibracao').first()
        
        if not ultimo_historico:
            messages.warning(request, 'Nenhum histórico de calibração encontrado para este instrumento.')
            return redirect('detalhe_instrumento', instrumento_id=instrumento_id)
        
        # Atualizar data da última calibração
        instrumento.data_ultima_calibracao = ultimo_historico.data_calibracao
        
        # Recalcular próxima calibração baseado na frequência do instrumento
        # Prioridade: 1) frequencia_meses do instrumento, 2) frequência da categoria, 3) proxima_calibracao do histórico
        meses = None
        
        if instrumento.frequencia_meses:
            # Usar frequência específica do instrumento
            meses = instrumento.frequencia_meses
        elif instrumento.categoria and instrumento.categoria.frequencia_calibracao_meses:
            # Usar frequência padrão da categoria
            meses = instrumento.categoria.frequencia_calibracao_meses
        
        if meses:
            instrumento.data_proxima_calibracao = ultimo_historico.data_calibracao + relativedelta(months=meses)
        else:
            # Se não tiver frequência configurada, usar o valor do histórico se existir
            instrumento.data_proxima_calibracao = ultimo_historico.proxima_calibracao if hasattr(ultimo_historico, 'proxima_calibracao') else None
        
        instrumento.save(update_fields=['data_ultima_calibracao', 'data_proxima_calibracao'])
        
        logger.info(f"Datas de calibração atualizadas para instrumento {instrumento.tag}")
        messages.success(
            request, 
            f'Datas de calibração atualizadas: Última: {instrumento.data_ultima_calibracao.strftime("%d/%m/%Y")}, '
            f'Próxima: {instrumento.data_proxima_calibracao.strftime("%d/%m/%Y") if instrumento.data_proxima_calibracao else "N/A"}'
        )
    except Exception as e:
        logger.error(f"Erro ao atualizar datas de calibração: {str(e)}", exc_info=True)
        messages.error(request, f'Erro ao atualizar datas: {str(e)}')
    
    return redirect('detalhe_instrumento', instrumento_id=instrumento_id)


# ==============================================================================
# SOLICITAÇÕES DE INSTRUMENTO - Cross-App Management
# ==============================================================================

@login_required
def solicitacao_list(request):
    """Lista solicitações de instrumentos com filtros"""
    # Get all solicitações or filter by status
    queryset = SolicitacaoInstrumento.objects.select_related('solicitante', 'instrumento_alvo').order_by('-data_solicitacao')
    
    # Filter by status if provided
    status = request.GET.get('status', '')
    if status:
        queryset = queryset.filter(status=status)
    
    # Filter by tipo if provided
    tipo = request.GET.get('tipo', '')
    if tipo:
        queryset = queryset.filter(tipo=tipo)
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(queryset, 20)
    try:
        solicitacoes = paginator.page(page)
    except Exception as e:
        solicitacoes = paginator.page(1)
    
    context = {
        'solicitacoes': solicitacoes,
        'status_choices': SolicitacaoInstrumento.STATUS_CHOICES,
        'tipo_choices': SolicitacaoInstrumento.TIPO_CHOICES,
        'selected_status': status,
        'selected_tipo': tipo,
    }
    
    return render(request, 'qms/solicitacao_list.html', context)


@login_required
@require_POST
def atualizar_todas_datas_calibracao_view(request):
    """Atualiza em massa as datas de próximas calibrações de todos os instrumentos."""
    from dateutil.relativedelta import relativedelta
    
    try:
        atualizado_count = 0
        erro_count = 0
        
        # Buscar todos os instrumentos
        instrumentos = Instrumento.objects.filter(ativo=True)
        
        for instrumento in instrumentos:
            try:
                # Buscar o histórico mais recente
                ultimo_historico = HistoricoCalibracao.objects.filter(
                    instrumento=instrumento
                ).order_by('-data_calibracao').first()
                
                if not ultimo_historico:
                    continue
                
                # Atualizar data da última calibração
                instrumento.data_ultima_calibracao = ultimo_historico.data_calibracao
                
                # Recalcular próxima calibração baseado na frequência do instrumento
                meses = None
                
                if instrumento.frequencia_meses:
                    meses = instrumento.frequencia_meses
                elif instrumento.categoria and instrumento.categoria.frequencia_calibracao_meses:
                    meses = instrumento.categoria.frequencia_calibracao_meses
                
                if meses:
                    instrumento.data_proxima_calibracao = ultimo_historico.data_calibracao + relativedelta(months=meses)
                else:
                    instrumento.data_proxima_calibracao = ultimo_historico.proxima_calibracao if hasattr(ultimo_historico, 'proxima_calibracao') else None
                
                instrumento.save(update_fields=['data_ultima_calibracao', 'data_proxima_calibracao'])
                atualizado_count += 1
                
            except Exception as e:
                logger.error(f"Erro ao atualizar instrumento {instrumento.id}: {str(e)}")
                erro_count += 1
        
        message = f'Datas de calibração atualizadas para {atualizado_count} instrumentos.'
        if erro_count > 0:
            message += f' {erro_count} erros encontrados.'
        
        logger.info(f"Atualização em massa concluída: {atualizado_count} sucesso, {erro_count} erros")
        
        return JsonResponse({
            'success': True,
            'message': message,
            'atualizado': atualizado_count,
            'erros': erro_count
        })
        
    except Exception as e:
        logger.error(f"Erro ao atualizar datas em massa: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f'Erro ao atualizar datas: {str(e)}'
        }, status=400)


# ==============================================================================
# LISTAGEM DE HISTÓRICOS DE CALIBRAÇÃO
# ==============================================================================

@login_required
def listar_historicos_calibracao_view(request):
    """Lista todos os históricos de calibração com filtros e paginação."""
    from django.core.paginator import Paginator
    
    # Base query - ordenado por data de calibração decrescente
    historicos = HistoricoCalibracao.objects.all().select_related(
        'instrumento', 'instrumento__categoria', 'instrumento__setor', 'atendimento'
    ).order_by('-data_calibracao')
    
    # Aplicar filtros
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')
    resultado_filter = request.GET.get('resultado', '')
    tipo_filter = request.GET.get('tipo', '')
    instrumento_filter = request.GET.get('instrumento', '')
    categoria_filter = request.GET.get('categoria', '')
    
    # Filtro de busca por instrumento, código ou número de certificado
    if search_query:
        historicos = historicos.filter(
            Q(instrumento__tag__icontains=search_query) |
            Q(instrumento__descricao__icontains=search_query) |
            Q(instrumento__codigo__icontains=search_query) |
            Q(numero_certificado__icontains=search_query) |
            Q(fornecedor__icontains=search_query)
        )
    
    # Filtro por status de vencimento
    if status_filter == 'vencidas':
        today = date.today()
        historicos = historicos.filter(proxima_calibracao__lt=today)
    elif status_filter == 'avencer':
        today = date.today()
        thirty_days = today + timedelta(days=30)
        historicos = historicos.filter(
            proxima_calibracao__gte=today,
            proxima_calibracao__lte=thirty_days
        )
    elif status_filter == 'vigentes':
        today = date.today()
        historicos = historicos.filter(proxima_calibracao__gte=today)
    
    # Filtro por resultado
    if resultado_filter:
        historicos = historicos.filter(resultado=resultado_filter)
    
    # Filtro por tipo de calibração
    if tipo_filter:
        historicos = historicos.filter(tipo_calibracao=tipo_filter)
    
    # Filtro por instrumento
    if instrumento_filter:
        historicos = historicos.filter(instrumento__id=instrumento_filter)
    
    # Filtro por categoria
    if categoria_filter:
        historicos = historicos.filter(instrumento__categoria__id=categoria_filter)
    
    # Paginação
    page = request.GET.get('page', 1)
    paginator = Paginator(historicos, 50)  # 50 históricos por página
    
    try:
        page_obj = paginator.page(page)
    except Exception as e:
        page_obj = paginator.page(1)
    
    # Dados para os filtros
    categorias = CategoriaInstrumento.objects.all().order_by('nome')
    instrumentos = Instrumento.objects.filter(ativo=True).order_by('tag')
    
    # Data de hoje para comparações no template
    hoje = date.today()
    
    # Preparar dados dos instrumentos em JSON para o modal
    import json
    instrumentos_json = json.dumps([
        {
            'id': inst.id,
            'tag': inst.tag,
            'descricao': inst.descricao,
            'categoria': inst.categoria.nome if inst.categoria else 'Sem categoria',
        }
        for inst in instrumentos
    ])
    
    context = {
        'page_obj': page_obj,
        'historicos': page_obj.object_list,
        'total_count': paginator.count,
        'categorias': categorias,
        'instrumentos': instrumentos,
        'instrumentos_json': instrumentos_json,
        'search_query': search_query,
        'status_filter': status_filter,
        'resultado_filter': resultado_filter,
        'tipo_filter': tipo_filter,
        'instrumento_filter': instrumento_filter,
        'categoria_filter': categoria_filter,
        'hoje': hoje,
    }
    
    return render(request, 'qms/historicos_calibracao_list.html', context)


@login_required
def novo_historico_calibracao_from_listagem_view(request, instrumento_id):
    """Cria novo histórico de calibração a partir da listagem, redirecionando para edição."""
    from datetime import date
    
    try:
        # Validar que o instrumento existe e está ativo
        instrumento = get_object_or_404(Instrumento, id=instrumento_id, ativo=True)
        logger.info(f"Criar novo histórico: instrumento_id={instrumento_id}, user={request.user}")
        
        # Criar histórico vazio com valores padrão
        historico = HistoricoCalibracao.objects.create(
            instrumento=instrumento,
            data_calibracao=date.today(),
            data_aprovacao=date.today(),
            numero_certificado="S/N",
            tipo_calibracao="EXTERNA",
            resultado="APROVADO_SEM_CORRECAO"
        )
        
        logger.info(f"✓ Novo histórico {historico.id} criado para {instrumento.tag}")
        messages.success(request, f"✓ Novo registro criado para {instrumento.tag}! Preencha os dados.")
        
        # Redirecionar para a tela de edição
        return redirect('editar_historico_calibracao', historico_id=historico.id)
        
    except Instrumento.DoesNotExist:
        messages.error(request, 'Instrumento não encontrado ou inativo.')
        return redirect('qms:listar_historicos_calibracao')
    except Exception as e:
        logger.error(f"❌ Erro ao criar histórico: {e}", exc_info=True)
        messages.error(request, f'Erro ao criar registro: {str(e)}')
        return redirect('qms:listar_historicos_calibracao')

