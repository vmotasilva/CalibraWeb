# -*- coding: utf-8 -*-
"""
Views para o módulo de Cotação de Calibração
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone
from datetime import datetime

from metrologia.models import Cotacao, OcorrenciaCotacao, Instrumento
from metrologia.forms import CotacaoForm, CotacaoAprovarForm, OcorrenciaCotacaoForm
from fornecedores.models import Fornecedor


@login_required
def cotacao_list(request):
    """Lista todas as cotações com filtros"""
    cotacoes = Cotacao.objects.all().select_related('fornecedor').prefetch_related('instrumentos')
    
    # Filtros
    status = request.GET.get('status')
    fornecedor_id = request.GET.get('fornecedor')
    q = request.GET.get('q')  # busca
    
    if status:
        cotacoes = cotacoes.filter(status=status)
    
    if fornecedor_id:
        cotacoes = cotacoes.filter(fornecedor_id=fornecedor_id)
    
    if q:
        cotacoes = cotacoes.filter(
            Q(fornecedor__empresa__icontains=q) |
            Q(observacoes__icontains=q)
        )
    
    # Opções para filtros
    status_choices = Cotacao._meta.get_field('status').choices
    fornecedores = Fornecedor.objects.filter(ativo=True).order_by('empresa')
    
    context = {
        'cotacoes': cotacoes,
        'status_choices': status_choices,
        'fornecedores': fornecedores,
        'status_selecionado': status,
        'fornecedor_selecionado': fornecedor_id,
        'q': q,
    }
    return render(request, 'metrologia/cotacao/list.html', context)


@login_required
def cotacao_create(request):
    """Cria nova cotação"""
    if request.method == 'POST':
        form = CotacaoForm(request.POST)
        if form.is_valid():
            cotacao = form.save(commit=False)
            cotacao.criado_por = request.user
            cotacao.save()
            form.save_m2m()  # Save many-to-many
            messages.success(request, f"Cotação #{cotacao.id} criada com sucesso!")
            return redirect('metrologia:cotacao_detail', pk=cotacao.id)
        else:
            messages.error(request, "Erro ao criar cotação. Verifique os dados.")
    else:
        form = CotacaoForm()
    
    context = {'form': form, 'titulo': 'Nova Cotação'}
    return render(request, 'metrologia/cotacao/form.html', context)


@login_required
def cotacao_detail(request, pk):
    """Detalhe da cotação"""
    cotacao = get_object_or_404(Cotacao, pk=pk)
    ocorrencias = cotacao.ocorrencias.all().order_by('-data')
    
    context = {
        'cotacao': cotacao,
        'ocorrencias': ocorrencias,
        'status_display': dict(Cotacao._meta.get_field('status').choices),
    }
    return render(request, 'metrologia/cotacao/detail.html', context)


@login_required
def cotacao_enviar(request, pk):
    """Envia cotação para fornecedor"""
    cotacao = get_object_or_404(Cotacao, pk=pk)
    
    if cotacao.status != 'CRIADA':
        messages.error(request, "Apenas cotações em status 'Criada' podem ser enviadas.")
        return redirect('metrologia:cotacao_detail', pk=pk)
    
    cotacao.status = 'ENVIADA'
    cotacao.data_envio = timezone.now()
    cotacao.save()
    
    messages.success(request, f"Cotação #{cotacao.id} enviada para {cotacao.fornecedor.empresa}!")
    return redirect('metrologia:cotacao_detail', pk=pk)


@login_required
def cotacao_receber_proposta(request, pk):
    """Marca que proposta foi recebida"""
    cotacao = get_object_or_404(Cotacao, pk=pk)
    
    if cotacao.status != 'ENVIADA':
        messages.error(request, "Apenas cotações 'Enviadas' podem ter proposta recebida.")
        return redirect('metrologia:cotacao_detail', pk=pk)
    
    if request.method == 'POST':
        form = CotacaoAprovarForm(request.POST, instance=cotacao)
        if form.is_valid():
            cotacao = form.save(commit=False)
            cotacao.status = 'PROPOSTA_RECEBIDA'
            cotacao.data_proposta = timezone.now()
            cotacao.save()
            messages.success(request, f"Proposta recebida para Cotação #{cotacao.id}!")
            return redirect('metrologia:cotacao_detail', pk=pk)
    else:
        form = CotacaoAprovarForm(instance=cotacao)
    
    context = {
        'form': form,
        'cotacao': cotacao,
        'titulo': 'Registrar Proposta Recebida',
    }
    return render(request, 'metrologia/cotacao/form.html', context)


@login_required
def cotacao_aprovar(request, pk):
    """Aprova cotação"""
    cotacao = get_object_or_404(Cotacao, pk=pk)
    
    if cotacao.status not in ['PROPOSTA_RECEBIDA', 'CRIADA']:
        messages.error(request, "Cotação não pode ser aprovada neste status.")
        return redirect('metrologia:cotacao_detail', pk=pk)
    
    cotacao.status = 'APROVADA'
    cotacao.data_decisao = timezone.now()
    cotacao.save()
    
    messages.success(request, f"Cotação #{cotacao.id} aprovada!")
    return redirect('metrologia:cotacao_detail', pk=pk)


@login_required
def cotacao_reprovar(request, pk):
    """Reprova cotação"""
    cotacao = get_object_or_404(Cotacao, pk=pk)
    
    if cotacao.status not in ['PROPOSTA_RECEBIDA', 'CRIADA']:
        messages.error(request, "Cotação não pode ser reprovada neste status.")
        return redirect('metrologia:cotacao_detail', pk=pk)
    
    if request.method == 'POST':
        observacao = request.POST.get('motivo_reprovacao')
        cotacao.status = 'REPROVADA'
        cotacao.data_decisao = timezone.now()
        if observacao:
            cotacao.observacoes = f"{cotacao.observacoes or ''}\n\nMotivo Reprovação: {observacao}"
        cotacao.save()
        messages.success(request, f"Cotação #{cotacao.id} reprovada!")
        return redirect('metrologia:cotacao_detail', pk=pk)
    
    context = {'cotacao': cotacao}
    return render(request, 'metrologia/cotacao/reprovar_confirm.html', context)


@login_required
def cotacao_cancelar(request, pk):
    """Cancela cotação"""
    cotacao = get_object_or_404(Cotacao, pk=pk)
    
    if cotacao.status == 'CANCELADA':
        messages.warning(request, "Cotação já foi cancelada.")
        return redirect('metrologia:cotacao_detail', pk=pk)
    
    cotacao.status = 'CANCELADA'
    cotacao.save()
    messages.success(request, f"Cotação #{cotacao.id} cancelada!")
    return redirect('metrologia:cotacao_list')


# ==============================================================================
# OCORRÊNCIAS DE COTAÇÃO
# ==============================================================================

@login_required
def ocorrencia_create(request, cotacao_id):
    """Registra nova ocorrência em uma cotação"""
    cotacao = get_object_or_404(Cotacao, pk=cotacao_id)
    
    if request.method == 'POST':
        form = OcorrenciaCotacaoForm(request.POST)
        if form.is_valid():
            ocorrencia = form.save(commit=False)
            ocorrencia.cotacao = cotacao
            ocorrencia.responsavel = request.user
            ocorrencia.save()
            messages.success(request, "Ocorrência registrada com sucesso!")
            return redirect('metrologia:cotacao_detail', pk=cotacao_id)
        else:
            messages.error(request, "Erro ao registrar ocorrência.")
    else:
        form = OcorrenciaCotacaoForm()
    
    context = {
        'form': form,
        'cotacao': cotacao,
        'titulo': 'Registrar Ocorrência',
    }
    return render(request, 'metrologia/cotacao/ocorrencia_form.html', context)


@login_required
@require_POST
def ocorrencia_resolver(request, ocorrencia_id):
    """Marca ocorrência como resolvida"""
    ocorrencia = get_object_or_404(OcorrenciaCotacao, pk=ocorrencia_id)
    cotacao_id = ocorrencia.cotacao.id
    
    ocorrencia.resolvida = True
    ocorrencia.data_resolucao = timezone.now()
    ocorrencia.save()
    
    messages.success(request, "Ocorrência marcada como resolvida!")
    return redirect('metrologia:cotacao_detail', pk=cotacao_id)


@login_required
def ocorrencia_edit(request, ocorrencia_id):
    """Edita ocorrência"""
    ocorrencia = get_object_or_404(OcorrenciaCotacao, pk=ocorrencia_id)
    cotacao_id = ocorrencia.cotacao.id
    
    if request.method == 'POST':
        form = OcorrenciaCotacaoForm(request.POST, instance=ocorrencia)
        if form.is_valid():
            form.save()
            messages.success(request, "Ocorrência atualizada!")
            return redirect('metrologia:cotacao_detail', pk=cotacao_id)
    else:
        form = OcorrenciaCotacaoForm(instance=ocorrencia)
    
    context = {
        'form': form,
        'ocorrencia': ocorrencia,
        'cotacao': ocorrencia.cotacao,
        'titulo': 'Editar Ocorrência',
    }
    return render(request, 'metrologia/cotacao/ocorrencia_form.html', context)


@login_required
@require_POST
def ocorrencia_delete(request, ocorrencia_id):
    """Delete ocorrência"""
    ocorrencia = get_object_or_404(OcorrenciaCotacao, pk=ocorrencia_id)
    cotacao_id = ocorrencia.cotacao.id
    
    ocorrencia.delete()
    messages.success(request, "Ocorrência removida!")
    return redirect('metrologia:cotacao_detail', pk=cotacao_id)
