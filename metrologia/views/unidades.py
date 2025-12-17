"""
metrologia/views/unidades.py

Views para gerenciamento de Unidades de Medida
- CRUD completo (Create, Read, Update, Delete)
- Listagem com paginação
- Validação de dados
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.db.models import Q, Count
from django.core.paginator import Paginator

from core.models import UnidadeMedida
from metrologia.forms import UnidadeMedidaForm


# ============================================================================
# LISTAR UNIDADES
# ============================================================================

@login_required
@require_http_methods(['GET'])
def unidades_list_view(request):
    """
    Listar todas as unidades de medida com busca e paginação
    """
    unidades = UnidadeMedida.objects.all()
    
    # Busca
    search = request.GET.get('search', '').strip()
    if search:
        unidades = unidades.filter(
            Q(nome__icontains=search) |
            Q(descricao__icontains=search)
        )
    
    # Paginação
    paginator = Paginator(unidades, 10)
    page_number = request.GET.get('page', 1)
    unidades_page = paginator.get_page(page_number)
    
    context = {
        'unidades': unidades_page,
        'search': search,
        'total_count': paginator.count,
    }
    
    return render(request, 'metrologia/unidade_list.html', context)


# ============================================================================
# CRIAR UNIDADE
# ============================================================================

@login_required
@require_http_methods(['GET', 'POST'])
def unidade_create_view(request):
    """
    Criar nova unidade de medida
    """
    if request.method == 'POST':
        form = UnidadeMedidaForm(request.POST)
        if form.is_valid():
            unidade = form.save()
            messages.success(request, f'Unidade "{unidade.nome}" criada com sucesso!')
            return redirect('metrologia:unidades_list')
    else:
        form = UnidadeMedidaForm()
    
    context = {
        'form': form,
        'title': 'Criar Nova Unidade de Medida',
    }
    
    return render(request, 'metrologia/unidade_form.html', context)


# ============================================================================
# EDITAR UNIDADE
# ============================================================================

@login_required
@require_http_methods(['GET', 'POST'])
def unidade_update_view(request, unidade_id):
    """
    Editar unidade de medida existente
    """
    unidade = get_object_or_404(UnidadeMedida, pk=unidade_id)
    
    if request.method == 'POST':
        form = UnidadeMedidaForm(request.POST, instance=unidade)
        if form.is_valid():
            unidade = form.save()
            messages.success(request, f'Unidade "{unidade.nome}" atualizada com sucesso!')
            return redirect('metrologia:unidades_list')
    else:
        form = UnidadeMedidaForm(instance=unidade)
    
    context = {
        'form': form,
        'unidade': unidade,
        'title': f'Editar Unidade: {unidade.nome}',
    }
    
    return render(request, 'metrologia/unidade_form.html', context)


# ============================================================================
# DELETAR UNIDADE
# ============================================================================

@login_required
@require_http_methods(['GET', 'POST'])
def unidade_delete_view(request, unidade_id):
    """
    Deletar unidade de medida com confirmação
    Verifica se há faixas usando essa unidade antes de deletar
    """
    unidade = get_object_or_404(UnidadeMedida, pk=unidade_id)
    
    # Contar quantas faixas usam essa unidade
    from metrologia.models import FaixaMedicaoPadraoCategoria, FaixaMedicao
    
    faixas_padrao_count = FaixaMedicaoPadraoCategoria.objects.filter(unidade=unidade).count()
    faixas_instrumento_count = FaixaMedicao.objects.filter(unidade=unidade).count()
    
    if request.method == 'POST':
        if faixas_padrao_count > 0 or faixas_instrumento_count > 0:
            messages.error(
                request,
                f'Não é possível deletar a unidade "{unidade.nome}". '
                f'Há {faixas_padrao_count} faixas padrão e {faixas_instrumento_count} '
                f'faixas de instrumentos usando essa unidade.'
            )
            return redirect('metrologia:unidade_detail', unidade_id=unidade.id)
        
        nome_unidade = unidade.nome
        unidade.delete()
        messages.success(request, f'Unidade "{nome_unidade}" deletada com sucesso!')
        return redirect('metrologia:unidades_list')
    
    context = {
        'unidade': unidade,
        'faixas_padrao_count': faixas_padrao_count,
        'faixas_instrumento_count': faixas_instrumento_count,
        'total_faixas': faixas_padrao_count + faixas_instrumento_count,
    }
    
    return render(request, 'metrologia/unidade_confirm_delete.html', context)


# ============================================================================
# DETALHE UNIDADE
# ============================================================================

@login_required
@require_http_methods(['GET'])
def unidade_detail_view(request, unidade_id):
    """
    Visualizar detalhes de uma unidade de medida
    Mostra todas as faixas que usam essa unidade
    """
    unidade = get_object_or_404(UnidadeMedida, pk=unidade_id)
    
    # Faixas padrão usando essa unidade
    faixas_padrao = unidade.faixamedicaopadraocategoria_set.all().order_by('categoria')
    
    # Faixas de instrumentos usando essa unidade
    faixas_instrumento = unidade.faixamedicao_set.all().order_by('instrumento')
    
    context = {
        'unidade': unidade,
        'faixas_padrao': faixas_padrao,
        'faixas_instrumento': faixas_instrumento,
        'faixas_padrao_count': faixas_padrao.count(),
        'faixas_instrumento_count': faixas_instrumento.count(),
    }
    
    return render(request, 'metrologia/unidade_detail.html', context)
