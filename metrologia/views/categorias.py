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

from metrologia.models import CategoriaInstrumento, Instrumento, FaixaMedicao
from metrologia.forms import CategoriaInstrumentoForm


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
    faixas = FaixaMedicao.objects.filter(
        instrumento__categoria=categoria
    ).select_related('instrumento', 'unidade').distinct()
    
    context = {
        'categoria': categoria,
        'instrumentos': instrumentos,
        'total_instrumentos': instrumentos.count(),
        'faixas': faixas,
        'total_faixas': faixas.count(),
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
