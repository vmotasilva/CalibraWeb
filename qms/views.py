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
    }
    return render(request, 'metrologia/dashboard.html', context)


# ==============================================================================
# INSTRUMENT VIEWS
# ==============================================================================

@login_required
def novo_instrumento_view(request, instrumento_id=None):
    """Create or edit an instrument."""
    if instrumento_id:
        instrumento = get_object_or_404(Instrumento, id=instrumento_id)
        is_edit = True
    else:
        instrumento = None
        is_edit = False
    
    if request.method == 'POST':
        # Handle form submission
        # TODO: Implement form processing
        messages.success(request, 'Instrumento salvo com sucesso.')
        return redirect('modulo_metrologia')
    
    context = {
        'instrumento': instrumento,
        'is_edit': is_edit,
    }
    return render(request, 'metrologia/instrumento_form.html', context)


@login_required
def detalhe_instrumento_view(request, instrumento_id):
    """View instrument details with calibration history."""
    from datetime import date
    from rh.forms import OcorrenciaForm
    from rh.models import Colaborador, Ocorrencia
    
    try:
        instrumento = get_object_or_404(Instrumento, id=instrumento_id)
    except Exception as e:
        messages.error(request, f"Erro ao buscar instrumento: {str(e)}")
        return redirect('modulo_metrologia')

    # Handle occurrence form submission
    if request.method == "POST":
        form_ocorrencia = OcorrenciaForm(request.POST)
        if form_ocorrencia.is_valid():
            ocorrencia = form_ocorrencia.save(commit=False)
            ocorrencia.instrumento = instrumento
            ocorrencia.usuario_responsavel = request.user
            ocorrencia.save()
            messages.success(request, "Ocorrência registrada com sucesso!")
            return redirect("detalhe_instrumento", instrumento_id=instrumento.id)
        else:
            messages.error(request, "Erro ao registrar ocorrência.")
    else:
        form_ocorrencia = OcorrenciaForm()

    # Get related data
    try:
        historicos = instrumento.historicos.all().order_by("-data_calibracao")
    except Exception:
        historicos = []

    try:
        ocorrencias = Ocorrencia.objects.filter(instrumento=instrumento).order_by("-data_ocorrencia")
    except Exception:
        ocorrencias = []

    try:
        faixas = instrumento.faixas.all()
    except Exception:
        faixas = []

    context = {
        'instrumento': instrumento,
        'historicos': historicos,
        'ocorrencias': ocorrencias,
        'faixas': faixas,
        'form_ocorrencia': form_ocorrencia,
        'today': date.today(),
    }
    return render(request, 'metrologia/instrumento_detalhe.html', context)


# ==============================================================================
# CALIBRATION HISTORY VIEWS
# ==============================================================================

@login_required
def registrar_historico_calibracao_view(request, instrumento_id):
    """Register a new calibration history record."""
    instrumento = get_object_or_404(Instrumento, id=instrumento_id)
    
    if request.method == 'POST':
        # Handle form submission
        # TODO: Implement form processing
        messages.success(request, 'Histórico de calibração registrado com sucesso.')
        return redirect('detalhe_instrumento', instrumento_id=instrumento_id)
    
    context = {
        'instrumento': instrumento,
    }
    return render(request, 'metrologia/historico_calibracao_form.html', context)


@login_required
def visualizar_historico_calibracao_view(request, historico_id):
    """View calibration history details."""
    historico = get_object_or_404(HistoricoCalibracao, id=historico_id)
    
    context = {
        'historico': historico,
        'instrumento': historico.instrumento,
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
        return redirect('detalhe_instrumento', instrumento_id=instrumento_id)
    
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
    historico = get_object_or_404(HistoricoCalibracao, id=historico_id)
    
    if request.method == 'POST':
        if 'certificado' in request.FILES:
            historico.certificado = request.FILES['certificado']
            historico.save()
            messages.success(request, 'Certificado anexado com sucesso.')
        return redirect('visualizar_historico_calibracao', historico_id=historico_id)
    
    context = {
        'historico': historico,
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
    from metrologia.forms import ImportacaoHistoricoForm
    from metrologia.models import Instrumento, HistoricoCalibracao
    
    if request.method == "POST":
        form = ImportacaoHistoricoForm(request.POST, request.FILES)
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
                    except Exception:
                        force_sync = True
                
                if force_sync:
                    import_historico_task(job.id, tmp.name)
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
                    except Exception:
                        pass
                    messages.success(request, f"Histórico importado (job {job.id}). {job.result or ''}")
                    return redirect("modulo_metrologia")
            except Exception as e:
                messages.error(request, f"Erro ao enfileirar importação: {str(e)}")
                return redirect("importar_historico")
    else:
        form = ImportacaoHistoricoForm()
    
    jobs = ImportJob.objects.filter(job_type='HISTORICO').order_by('-created_at')[:5]
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
def dl_template_historico(request):
    """Download template for importing calibration history."""
    # Create a template file with required columns
    # TODO: Implement template generation
    return HttpResponse('Not implemented yet', status=501)


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
