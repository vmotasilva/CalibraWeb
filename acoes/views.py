from django.shortcuts import render

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import AcaoCorretiva, AcaoComentario


@login_required
def listar_acoes(request):
    """Lista todas as ações corretivas/preventivas com filtros."""
    acoes = AcaoCorretiva.objects.all()
    
    # Filtros
    filtro_tipo = request.GET.get('tipo', '')
    filtro_status = request.GET.get('status', '')
    filtro_prioridade = request.GET.get('prioridade', '')
    filtro_busca = request.GET.get('busca', '')
    
    if filtro_tipo:
        acoes = acoes.filter(tipo=filtro_tipo)
    
    if filtro_status:
        acoes = acoes.filter(status=filtro_status)
    
    if filtro_prioridade:
        acoes = acoes.filter(prioridade=filtro_prioridade)
    
    if filtro_busca:
        acoes = acoes.filter(
            Q(titulo__icontains=filtro_busca) |
            Q(descricao__icontains=filtro_busca)
        )
    
    context = {
        'acoes': acoes,
        'filtro_tipo': filtro_tipo,
        'filtro_status': filtro_status,
        'filtro_prioridade': filtro_prioridade,
        'filtro_busca': filtro_busca,
        'total_aberta': AcaoCorretiva.objects.filter(status='aberta').count(),
        'total_em_progresso': AcaoCorretiva.objects.filter(status='em_progresso').count(),
        'total_concluida': AcaoCorretiva.objects.filter(status='concluida').count(),
    }
    
    return render(request, 'acoes/listar_acoes.html', context)


@login_required
def detalhe_acao(request, acao_id):
    """Exibe detalhes de uma ação."""
    acao = get_object_or_404(AcaoCorretiva, id=acao_id)
    
    context = {
        'acao': acao,
        'comentarios': acao.comentarios.all(),
    }
    
    return render(request, 'acoes/detalhe_acao.html', context)
