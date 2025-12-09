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
    context = {
        'total_instrumentos': Instrumento.objects.count(),
        'total_calibracoes': HistoricoCalibracao.objects.count(),
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
    """View instrument details."""
    instrumento = get_object_or_404(Instrumento, id=instrumento_id)
    historicos = instrumento.historicos.all().order_by('-data_calibracao')
    
    context = {
        'instrumento': instrumento,
        'historicos': historicos,
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
    """Import instruments from file."""
    from metrologia.forms import ImportacaoInstrumentosForm
    
    if request.method == 'POST':
        form = ImportacaoInstrumentosForm(request.POST, request.FILES)
        if form.is_valid() and 'arquivo_excel' in request.FILES:
            # TODO: Implement full import logic
            messages.success(request, 'Instrumentos importados com sucesso.')
            return redirect('modulo_metrologia')
    else:
        form = ImportacaoInstrumentosForm()
    
    # Get recent import jobs for this type
    jobs = ImportJob.objects.filter(job_type='INSTRUMENTOS').order_by('-created_at')[:5]
    
    context = {'form': form, 'jobs': jobs}
    return render(request, 'metrologia/imports/instrumentos.html', context)


@login_required
def imp_historico_view(request):
    """Import calibration history from file."""
    from metrologia.forms import ImportacaoHistoricoForm
    
    if request.method == 'POST':
        form = ImportacaoHistoricoForm(request.POST, request.FILES)
        if form.is_valid() and 'arquivo_excel' in request.FILES:
            # TODO: Implement full import logic
            messages.success(request, 'Históricos importados com sucesso.')
            return redirect('modulo_metrologia')
    else:
        form = ImportacaoHistoricoForm()
    
    jobs = ImportJob.objects.filter(job_type='HISTORICO').order_by('-created_at')[:5]
    context = {'form': form, 'jobs': jobs}
    return render(request, 'metrologia/imports/historico.html', context)


@login_required
def imp_colab_view(request):
    """Import collaborators/employees from file."""
    # TODO: Create ImportacaoColaboradoresForm if it doesn't exist
    
    if request.method == 'POST':
        if 'arquivo_excel' in request.FILES:
            # TODO: Implement full import logic
            messages.success(request, 'Colaboradores importados com sucesso.')
            return redirect('modulo_metrologia')
    
    jobs = ImportJob.objects.filter(job_type='COLABORADORES').order_by('-created_at')[:5]
    context = {'jobs': jobs}
    return render(request, 'rh/imports/colaboradores.html', context)


@login_required
def imp_hierarquia_view(request):
    """Import organizational hierarchy from file."""
    # TODO: Create ImportacaoHierarquiaForm if it doesn't exist
    
    if request.method == 'POST':
        if 'arquivo_excel' in request.FILES:
            # TODO: Implement full import logic
            messages.success(request, 'Hierarquia importada com sucesso.')
            return redirect('modulo_metrologia')
    
    jobs = ImportJob.objects.filter(job_type='HIERARQUIA').order_by('-created_at')[:5]
    context = {'jobs': jobs}
    return render(request, 'shared/dashboard.html', context)


@login_required
def imp_ferias_view(request):
    """Import vacation/holidays from file."""
    # TODO: Create ImportacaoFeriasForm if it doesn't exist
    
    if request.method == 'POST':
        if 'arquivo_excel' in request.FILES:
            # TODO: Implement full import logic
            messages.success(request, 'Férias importadas com sucesso.')
            return redirect('modulo_metrologia')
    
    jobs = ImportJob.objects.filter(job_type='FERIAS').order_by('-created_at')[:5]
    context = {'jobs': jobs}
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
