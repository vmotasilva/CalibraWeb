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
from training.models import Procedimento
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
    # Retrieve all instruments and related data
    instrumentos = Instrumento.objects.all().select_related('setor', 'categoria').prefetch_related('faixas')
    
    # Get filter parameters from request
    status_filter = request.GET.get('status', '')
    categoria_filter = request.GET.get('categoria', '')
    setor_filter = request.GET.get('setor', '')
    search_query = request.GET.get('search', '')
    
    # Apply filters
    if status_filter == 'vencidos':
        from datetime import date
        instrumentos = instrumentos.filter(data_proxima_calibracao__lt=date.today(), ativo=True)
    elif status_filter == 'avencer':
        from datetime import date, timedelta
        today = date.today()
        thirty_days = today + timedelta(days=30)
        instrumentos = instrumentos.filter(
            data_proxima_calibracao__gte=today,
            data_proxima_calibracao__lte=thirty_days,
            ativo=True
        )
    
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
    
    # Get available categories and sectors for filter options
    categorias_filtro = CategoriaInstrumento.objects.all()
    setores_filtro = Setor.objects.all()
    
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
    """View instrument details with calibration history."""
    from datetime import date
    
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

    context = {
        'instrumento': instrumento,
        'historicos': historicos,
        'ocorrencias': ocorrencias,
        'faixas': faixas,
        'today': date.today(),
        'edit_url': f"/instrumento/{instrumento.id}/editar/",
    }
    return render(request, 'metrologia/instrumento_detalhe.html', context)


# ==============================================================================
# CALIBRATION HISTORY VIEWS
# ==============================================================================

@login_required
def registrar_historico_calibracao_view(request, instrumento_id):
    """Register a new calibration history record."""
    from metrologia.models import FaixaMedicao
    
    instrumento = get_object_or_404(Instrumento, id=instrumento_id)
    
    if request.method == 'POST':
        # Handle form submission
        # TODO: Implement form processing
        messages.success(request, 'Histórico de calibração registrado com sucesso.')
        return redirect('visualizar_instrumento', instrumento_id=instrumento_id)
    
    # Get measurement ranges for this instrument
    faixas_medicao = FaixaMedicao.objects.filter(instrumento=instrumento).order_by('valor_minimo')
    
    context = {
        'instrumento': instrumento,
        'faixas_medicao': faixas_medicao,
    }
    return render(request, 'metrologia/historico_calibracao_form.html', context)


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
    
    if historico.certificado:
        response = FileResponse(historico.certificado.open('rb'))
        response['Content-Disposition'] = f'attachment; filename="{historico.certificado.name}"'
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
def aplicar_carimbo_certificado_view(request, historico_id):
    """Apply a stamp/seal to a certificate."""
    historico = get_object_or_404(HistoricoCalibracao, id=historico_id)
    
    if request.method == 'POST':
        # TODO: Implement stamp application logic
        messages.success(request, 'Carimbo aplicado com sucesso.')
        return redirect('visualizar_historico_calibracao', historico_id=historico_id)
    
    context = {
        'historico': historico,
    }
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
def remover_arquivo_padrao_view(request, arquivo_id):
    """Remove a standard file."""
    # TODO: Implement standard file model and logic
    if request.method == 'POST':
        # TODO: Delete file
        messages.success(request, 'Arquivo removido com sucesso.')
        return redirect('modulo_metrologia')
    
    return HttpResponse('Not implemented yet', status=501)


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
    from metrologia.models import FaixaMedicao
    
    instrumento = get_object_or_404(Instrumento, id=instrumento_id)
    faixas = instrumento.faixas.all().order_by('valor_minimo')
    
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
    from .forms_historico import HistoricoCalibracaoForm
    from .forms import ResultadoFaixaCalibracaoForm
    from metrologia.models import ResultadoFaixaCalibracao, FaixaMedicao
    
    historico = get_object_or_404(HistoricoCalibracao, id=historico_id)
    resultados_faixa = historico.resultados_faixa.all().select_related('faixa')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_history':
            form = HistoricoCalibracaoForm(request.POST, request.FILES, instance=historico)
            if form.is_valid():
                form.save()
                messages.success(request, 'Histórico atualizado com sucesso.')
                return redirect('editar_historico_calibracao', historico_id=historico_id)
            else:
                # Mostrar erros específicos
                error_msg = 'Erro ao atualizar histórico: '
                for field, errors in form.errors.items():
                    error_msg += f"{field}: {', '.join(errors)}. "
                messages.error(request, error_msg)
        
        elif action == 'update_resultado':
            resultado_id = request.POST.get('resultado_id')
            try:
                resultado = ResultadoFaixaCalibracao.objects.get(id=resultado_id, historico=historico)
                form = ResultadoFaixaCalibracaoForm(request.POST, instance=resultado)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Resultado da faixa atualizado com sucesso.')
                else:
                    messages.error(request, 'Erro ao atualizar resultado.')
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
        instrumentos = instrumentos.filter(
            data_proxima_calibracao__gte=today,
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
    
    # Order by tag
    instrumentos = instrumentos.order_by('tag')
    
    # Pagination with caching for large datasets
    page_number = PaginationHelper.get_page_from_request(request)
    cache_key = f'instrumentos_count_filters_{search_query}_{status_filter}_{categoria_filter}_{setor_filter}_{ativo_filter}'
    
    paginator = OffsetPaginator(page_size=50, cache_count=True)
    page_items, pagination_metadata = paginator.paginate_queryset(
        instrumentos,
        page=page_number,
        cache_key=cache_key
    )
    
    # Get filter options for dropdowns
    categorias = CategoriaInstrumento.objects.all().order_by('nome')
    setores = Setor.objects.all().order_by('nome')
    
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




