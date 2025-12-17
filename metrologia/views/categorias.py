# -*- coding: utf-8 -*-
"""
Views para gerenciamento de Categorias de Instrumentos em Metrologia
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.db.models import Count, Q
from django.http import JsonResponse

from metrologia.models import CategoriaInstrumento, Instrumento, FaixaMedicao, FaixaMedicaoPadraoCategoria
from metrologia.forms import CategoriaInstrumentoForm, FaixaMedicaoPadraoCategoriForm


@login_required
def categorias_list_view(request):
    """Lista todas as categorias de instrumentos com estatísticas."""
    categorias = CategoriaInstrumento.objects.annotate(
        total_instrumentos=Count('instrumento', distinct=True),
        total_faixas=Count('instrumento__faixas', distinct=True)
    ).order_by('nome')
    
    context = {
        'categorias': categorias,
        'total_categorias': categorias.count(),
    }
    return render(request, 'metrologia/categorias_list.html', context)


@login_required
def categoria_create_view(request):
    """Criar nova categoria de instrumento."""
    if request.method == 'POST':
        form = CategoriaInstrumentoForm(request.POST)
        if form.is_valid():
            categoria = form.save()
            messages.success(request, f'Categoria "{categoria.nome}" criada com sucesso.')
            return redirect('metrologia:categorias_list')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = CategoriaInstrumentoForm()
    
    context = {
        'form': form,
        'titulo': 'Nova Categoria de Instrumento',
        'acao': 'Criar',
    }
    return render(request, 'metrologia/categoria_form.html', context)


@login_required
def categoria_update_view(request, categoria_id):
    """Atualizar categoria de instrumento."""
    categoria = get_object_or_404(CategoriaInstrumento, id=categoria_id)
    
    if request.method == 'POST':
        form = CategoriaInstrumentoForm(request.POST, instance=categoria)
        if form.is_valid():
            categoria = form.save()
            messages.success(request, f'Categoria "{categoria.nome}" atualizada com sucesso.')
            return redirect('metrologia:categorias_list')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = CategoriaInstrumentoForm(instance=categoria)
    
    # Contar instrumentos nesta categoria
    total_instrumentos = categoria.instrumento_set.count()
    
    context = {
        'form': form,
        'categoria': categoria,
        'titulo': f'Editar Categoria: {categoria.nome}',
        'acao': 'Atualizar',
        'total_instrumentos': total_instrumentos,
    }
    return render(request, 'metrologia/categoria_form.html', context)


@login_required
@require_http_methods(["POST"])
def categoria_delete_view(request, categoria_id):
    """Deletar categoria de instrumento (se não tiver instrumentos)."""
    categoria = get_object_or_404(CategoriaInstrumento, id=categoria_id)
    
    # Verificar se há instrumentos nesta categoria
    total_instrumentos = categoria.instrumento_set.count()
    
    if total_instrumentos > 0:
        messages.error(
            request, 
            f'Não é possível deletar a categoria "{categoria.nome}" pois ela possui {total_instrumentos} instrumento(s) cadastrado(s).'
        )
    else:
        nome = categoria.nome
        categoria.delete()
        messages.success(request, f'Categoria "{nome}" deletada com sucesso.')
    
    return redirect('metrologia:categorias_list')


@login_required
def categoria_detail_view(request, categoria_id):
    """Detalhar categoria e mostrar instrumentos relacionados."""
    categoria = get_object_or_404(CategoriaInstrumento, id=categoria_id)
    
    # Instrumentos nesta categoria
    instrumentos = Instrumento.objects.filter(
        categoria=categoria
    ).select_related('setor', 'responsavel').prefetch_related('faixas')
    
    # Faixas de medição (agregadas de todos os instrumentos da categoria)
    faixas_instrumentos = FaixaMedicao.objects.filter(
        instrumento__categoria=categoria
    ).select_related('instrumento', 'unidade').distinct()
    
    # Faixas padrão da categoria
    faixas_padrao = FaixaMedicaoPadraoCategoria.objects.filter(
        categoria=categoria
    ).select_related('unidade').order_by('valor_minimo')
    
    context = {
        'categoria': categoria,
        'instrumentos': instrumentos,
        'total_instrumentos': instrumentos.count(),
        'faixas_instrumentos': faixas_instrumentos,
        'total_faixas_instrumentos': faixas_instrumentos.count(),
        'faixas_padrao': faixas_padrao,
        'total_faixas_padrao': faixas_padrao.count(),
    }
    return render(request, 'metrologia/categoria_detail.html', context)


@login_required
def categorias_api_view(request):
    """API para listar categorias em JSON (para selects dinâmicos)."""
    search = request.GET.get('search', '').strip()
    
    categorias = CategoriaInstrumento.objects.all().order_by('nome')
    
    if search:
        categorias = categorias.filter(
            Q(nome__icontains=search) | Q(descricao__icontains=search)
        )
    
    data = [
        {
            'id': cat.id,
            'nome': cat.nome,
            'descricao': cat.descricao or '',
            'unidade_padrao': str(cat.unidade_padrao) if cat.unidade_padrao else '',
        }
        for cat in categorias[:20]
    ]
    
    return JsonResponse({'categorias': data})


# ==============================================================================
# GERENCIAMENTO DE FAIXAS PADRÃO DE CATEGORIAS
# ==============================================================================

@login_required
def faixa_categoria_create_view(request, categoria_id):
    """Criar nova faixa padrão para uma categoria."""
    categoria = get_object_or_404(CategoriaInstrumento, id=categoria_id)
    
    if request.method == 'POST':
        form = FaixaMedicaoPadraoCategoriForm(request.POST)
        if form.is_valid():
            faixa = form.save(commit=False)
            faixa.categoria = categoria
            faixa.save()
            messages.success(request, f'Faixa padrão adicionada com sucesso à categoria.')
            return redirect('metrologia:categoria_detail', categoria_id=categoria_id)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = FaixaMedicaoPadraoCategoriForm()
    
    context = {
        'form': form,
        'categoria': categoria,
        'titulo': f'Nova Faixa Padrão - {categoria.nome}',
    }
    return render(request, 'metrologia/faixa_categoria_form.html', context)


@login_required
def faixa_categoria_update_view(request, faixa_id):
    """Atualizar faixa padrão de uma categoria."""
    faixa = get_object_or_404(FaixaMedicaoPadraoCategoria, id=faixa_id)
    categoria = faixa.categoria
    
    if request.method == 'POST':
        form = FaixaMedicaoPadraoCategoriForm(request.POST, instance=faixa)
        if form.is_valid():
            faixa = form.save()
            messages.success(request, 'Faixa padrão atualizada com sucesso.')
            return redirect('metrologia:categoria_detail', categoria_id=categoria.id)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = FaixaMedicaoPadraoCategoriForm(instance=faixa)
    
    context = {
        'form': form,
        'faixa': faixa,
        'categoria': categoria,
        'titulo': f'Editar Faixa Padrão - {categoria.nome}',
    }
    return render(request, 'metrologia/faixa_categoria_form.html', context)


@login_required
@require_http_methods(["POST"])
def faixa_categoria_delete_view(request, faixa_id):
    """Deletar faixa padrão de uma categoria."""
    faixa = get_object_or_404(FaixaMedicaoPadraoCategoria, id=faixa_id)
    categoria_id = faixa.categoria.id
    
    faixa.delete()
    messages.success(request, 'Faixa padrão removida com sucesso.')
    
    return redirect('metrologia:categoria_detail', categoria_id=categoria_id)


@login_required
def faixas_categoria_api_view(request, categoria_id):
    """API para obter faixas padrão de uma categoria em JSON."""
    categoria = get_object_or_404(CategoriaInstrumento, id=categoria_id)
    
    faixas = FaixaMedicaoPadraoCategoria.objects.filter(
        categoria=categoria,
        ativa=True
    ).select_related('unidade')
    
    data = [
        {
            'id': faixa.id,
            'unidade': str(faixa.unidade.nome),
            'valor_minimo': str(faixa.valor_minimo),
            'valor_maximo': str(faixa.valor_maximo),
            'resolucao': str(faixa.resolucao) if faixa.resolucao else '',
            'nominal': str(faixa.nominal) if faixa.nominal else '',
            'tolerancia_mais_menos': str(faixa.tolerancia_mais_menos) if faixa.tolerancia_mais_menos else '',
        }
        for faixa in faixas
    ]
    
    return JsonResponse({'faixas': data})
