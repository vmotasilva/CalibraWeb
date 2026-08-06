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
    """Lista todas as categorias de instrumentos com estatÃ­sticas."""
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
    
    # Faixas padrÃ£o da categoria
    faixas_padrao = FaixaMedicaoPadraoCategoria.objects.filter(
        categoria=categoria
    ).select_related('unidade').order_by('valor_minimo')
    
    context = {
        'form': form,
        'categoria': categoria,
        'titulo': f'Editar Categoria: {categoria.nome}',
        'acao': 'Atualizar',
        'total_instrumentos': total_instrumentos,
        'faixas_padrao': faixas_padrao,
        'total_faixas_padrao': faixas_padrao.count(),
    }
    return render(request, 'metrologia/categoria_form.html', context)


@login_required
@require_http_methods(["POST"])
def categoria_delete_view(request, categoria_id):
    """Deletar categoria de instrumento (se nÃ£o tiver instrumentos)."""
    categoria = get_object_or_404(CategoriaInstrumento, id=categoria_id)
    
    # Verificar se hÃ¡ instrumentos nesta categoria
    total_instrumentos = categoria.instrumento_set.count()
    
    if total_instrumentos > 0:
        messages.error(
            request, 
            f'NÃ£o Ã© possÃ­vel deletar a categoria "{categoria.nome}" pois ela possui {total_instrumentos} instrumento(s) cadastrado(s).'
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
    
    # Instrumentos nesta categoria (ordenados por TAG em ordem crescente)
    instrumentos = Instrumento.objects.filter(
        categoria=categoria
    ).select_related('setor', 'responsavel').prefetch_related('faixas').order_by('tag')
    
    # Faixas de mediÃ§Ã£o (agregadas de todos os instrumentos da categoria, ordenadas por TAG do instrumento)
    faixas_instrumentos = FaixaMedicao.objects.filter(
        instrumento__categoria=categoria
    ).select_related('instrumento', 'unidade').distinct().order_by('instrumento__tag')
    
    # Faixas padrÃ£o da categoria
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
    """API para listar categorias em JSON (para selects dinÃ¢micos)."""
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
# GERENCIAMENTO DE FAIXAS PADRÃO DE CATEGORIAS
# ==============================================================================

@login_required
def faixa_categoria_create_view(request, categoria_id):
    """Criar nova faixa padrÃ£o para uma categoria."""
    categoria = get_object_or_404(CategoriaInstrumento, id=categoria_id)
    
    if request.method == 'POST':
        form = FaixaMedicaoPadraoCategoriForm(request.POST)
        if form.is_valid():
            faixa = form.save(commit=False)
            faixa.categoria = categoria
            faixa.save()
            messages.success(request, f'Faixa padrÃ£o adicionada com sucesso Ã  categoria.')
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
        'titulo': f'Nova Faixa PadrÃ£o - {categoria.nome}',
    }
    return render(request, 'metrologia/faixa_categoria_form.html', context)


@login_required
def faixa_categoria_update_view(request, faixa_id):
    """Atualizar faixa padrÃ£o de uma categoria."""
    faixa = get_object_or_404(FaixaMedicaoPadraoCategoria, id=faixa_id)
    categoria = faixa.categoria
    
    if request.method == 'POST':
        form = FaixaMedicaoPadraoCategoriForm(request.POST, instance=faixa)
        if form.is_valid():
            faixa = form.save()
            messages.success(request, 'Faixa padrÃ£o atualizada com sucesso.')
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
        'titulo': f'Editar Faixa PadrÃ£o - {categoria.nome}',
    }
    return render(request, 'metrologia/faixa_categoria_form.html', context)


@login_required
@require_http_methods(["POST"])
def faixa_categoria_delete_view(request, faixa_id):
    """Deletar faixa padrÃ£o de uma categoria."""
    faixa = get_object_or_404(FaixaMedicaoPadraoCategoria, id=faixa_id)
    categoria_id = faixa.categoria.id
    
    faixa.delete()
    messages.success(request, 'Faixa padrÃ£o removida com sucesso.')
    
    return redirect('metrologia:categoria_detail', categoria_id=categoria_id)


@login_required
def faixas_categoria_api_view(request, categoria_id):
    """API para obter faixas padrÃ£o de uma categoria em JSON."""
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


@login_required
@require_http_methods(["POST"])
def faixa_categoria_add_to_instrument_view(request, categoria_id):
    """Adicionar uma faixa padrÃ£o da categoria a um instrumento."""
    categoria = get_object_or_404(CategoriaInstrumento, id=categoria_id)
    
    instrumento_id = request.POST.get('instrumento_id')
    faixa_padrao_id = request.POST.get('faixa_padrao_id')
    
    instrumento = get_object_or_404(Instrumento, id=instrumento_id, categoria=categoria)
    faixa_padrao = get_object_or_404(FaixaMedicaoPadraoCategoria, id=faixa_padrao_id, categoria=categoria)
    
    # Verificar se jÃ¡ existe essa faixa no instrumento
    faixa_existente = FaixaMedicao.objects.filter(
        instrumento=instrumento,
        unidade=faixa_padrao.unidade,
        valor_minimo=faixa_padrao.valor_minimo,
        valor_maximo=faixa_padrao.valor_maximo
    ).exists()
    
    if faixa_existente:
        messages.warning(request, 'Esta faixa jÃ¡ existe para este instrumento.')
    else:
        # Criar nova faixa baseada na faixa padrÃ£o
        nova_faixa = FaixaMedicao.objects.create(
            instrumento=instrumento,
            unidade=faixa_padrao.unidade,
            valor_minimo=faixa_padrao.valor_minimo,
            valor_maximo=faixa_padrao.valor_maximo,
            resolucao=faixa_padrao.resolucao,
            nominal=faixa_padrao.nominal,
            tolerancia_mais_menos=faixa_padrao.tolerancia_mais_menos,
        )
        messages.success(
            request, 
            f'Faixa ({faixa_padrao.valor_minimo} - {faixa_padrao.valor_maximo} {faixa_padrao.unidade.nome}) adicionada ao instrumento "{instrumento.descricao}" com sucesso.'
        )
    
    return redirect('metrologia:categoria_detail', categoria_id=categoria_id)


@login_required
@require_http_methods(["POST"])
def faixa_instrumento_delete_view(request, categoria_id, faixa_id):
    """Remover uma faixa de um instrumento."""
    categoria = get_object_or_404(CategoriaInstrumento, id=categoria_id)
    faixa = get_object_or_404(FaixaMedicao, id=faixa_id, instrumento__categoria=categoria)
    
    instrumento_tag = faixa.instrumento.tag
    faixa_descricao = f"{faixa.valor_minimo} - {faixa.valor_maximo} {faixa.unidade.nome}"
    
    faixa.delete()
    messages.success(
        request, 
        f'Faixa "{faixa_descricao}" removida do instrumento "{instrumento_tag}".'
    )
    
    return redirect('metrologia:categoria_detail', categoria_id=categoria_id)


@login_required
@require_http_methods(["GET", "POST"])
def faixa_instrumento_replace_view(request, categoria_id, faixa_id):
    """Substituir uma faixa de um instrumento por uma faixa padrÃ£o."""
    categoria = get_object_or_404(CategoriaInstrumento, id=categoria_id)
    faixa_atual = get_object_or_404(FaixaMedicao, id=faixa_id, instrumento__categoria=categoria)
    
    # Faixas padrÃ£o disponÃ­veis
    faixas_padrao = FaixaMedicaoPadraoCategoria.objects.filter(
        categoria=categoria
    ).select_related('unidade').order_by('valor_minimo')
    
    if request.method == 'POST':
        faixa_padrao_id = request.POST.get('faixa_padrao_id')
        faixa_padrao = get_object_or_404(FaixaMedicaoPadraoCategoria, id=faixa_padrao_id, categoria=categoria)
        
        # Verificar se a nova faixa jÃ¡ existe no instrumento
        faixa_existente = FaixaMedicao.objects.filter(
            instrumento=faixa_atual.instrumento,
            unidade=faixa_padrao.unidade,
            valor_minimo=faixa_padrao.valor_minimo,
            valor_maximo=faixa_padrao.valor_maximo
        ).exclude(id=faixa_atual.id).exists()
        
        if faixa_existente:
            messages.warning(request, 'A faixa padrÃ£o selecionada jÃ¡ existe para este instrumento.')
            return redirect('metrologia:faixa_instrumento_replace', categoria_id=categoria_id, faixa_id=faixa_id)
        
        # Atualizar a faixa com valores da faixa padrÃ£o
        faixa_antiga = f"{faixa_atual.valor_minimo} - {faixa_atual.valor_maximo} {faixa_atual.unidade.nome}"
        
        faixa_atual.unidade = faixa_padrao.unidade
        faixa_atual.valor_minimo = faixa_padrao.valor_minimo
        faixa_atual.valor_maximo = faixa_padrao.valor_maximo
        faixa_atual.resolucao = faixa_padrao.resolucao
        faixa_atual.nominal = faixa_padrao.nominal
        faixa_atual.tolerancia_mais_menos = faixa_padrao.tolerancia_mais_menos
        faixa_atual.save()
        
        faixa_nova = f"{faixa_padrao.valor_minimo} - {faixa_padrao.valor_maximo} {faixa_padrao.unidade.nome}"
        messages.success(
            request, 
            f'Faixa do instrumento "{faixa_atual.instrumento.tag}" substituÃ­da de "{faixa_antiga}" para "{faixa_nova}".'
        )
        
        return redirect('metrologia:categoria_detail', categoria_id=categoria_id)
    
    context = {
        'categoria': categoria,
        'faixa_atual': faixa_atual,
        'faixas_padrao': faixas_padrao,
        'titulo': f'Substituir Faixa - {faixa_atual.instrumento.tag}',
    }
    return render(request, 'metrologia/faixa_instrumento_replace.html', context)


@login_required
@require_http_methods(["POST"])
def faixa_instrumento_bulk_delete_view(request, categoria_id):
    """Remover mÃºltiplas faixas de instrumentos em massa."""
    categoria = get_object_or_404(CategoriaInstrumento, id=categoria_id)
    
    faixa_ids = request.POST.getlist('faixa_ids')
    
    if not faixa_ids:
        messages.warning(request, 'Nenhuma faixa foi selecionada.')
        return redirect('metrologia:categoria_detail', categoria_id=categoria_id)
    
    # Validar que todas as faixas pertencem Ã  categoria
    faixas = FaixaMedicao.objects.filter(
        id__in=faixa_ids,
        instrumento__categoria=categoria
    )
    
    if faixas.count() != len(faixa_ids):
        messages.error(request, 'Algumas faixas selecionadas nÃ£o pertencem a esta categoria.')
        return redirect('metrologia:categoria_detail', categoria_id=categoria_id)
    
    quantidade = faixas.count()
    faixas.delete()
    
    messages.success(request, f'{quantidade} faixa(s) removida(s) com sucesso.')
    return redirect('metrologia:categoria_detail', categoria_id=categoria_id)


@login_required
@require_http_methods(["GET", "POST"])
def faixa_instrumento_bulk_replace_view(request, categoria_id):
    """Substituir mÃºltiplas faixas por uma faixa padrÃ£o."""
    categoria = get_object_or_404(CategoriaInstrumento, id=categoria_id)
    
    # Faixas padrÃ£o disponÃ­veis
    faixas_padrao = FaixaMedicaoPadraoCategoria.objects.filter(
        categoria=categoria
    ).select_related('unidade').order_by('valor_minimo')
    
    if request.method == 'POST':
        faixa_ids = request.POST.getlist('faixa_ids')
        faixa_padrao_id = request.POST.get('faixa_padrao_id')
        
        if not faixa_ids:
            messages.warning(request, 'Nenhuma faixa foi selecionada.')
            return redirect('metrologia:categoria_detail', categoria_id=categoria_id)
        
        if not faixa_padrao_id:
            messages.error(request, 'Nenhuma faixa padrÃ£o foi selecionada.')
            return redirect('metrologia:categoria_detail', categoria_id=categoria_id)
        
        faixa_padrao = get_object_or_404(FaixaMedicaoPadraoCategoria, id=faixa_padrao_id, categoria=categoria)
        
        # Validar e atualizar faixas
        faixas = FaixaMedicao.objects.filter(
            id__in=faixa_ids,
            instrumento__categoria=categoria
        )
        
        if faixas.count() != len(faixa_ids):
            messages.error(request, 'Algumas faixas selecionadas nÃ£o pertencem a esta categoria.')
            return redirect('metrologia:categoria_detail', categoria_id=categoria_id)
        
        quantidade = 0
        for faixa in faixas:
            # Verificar se a nova faixa jÃ¡ existe neste instrumento
            faixa_existente = FaixaMedicao.objects.filter(
                instrumento=faixa.instrumento,
                unidade=faixa_padrao.unidade,
                valor_minimo=faixa_padrao.valor_minimo,
                valor_maximo=faixa_padrao.valor_maximo
            ).exclude(id=faixa.id).exists()
            
            if not faixa_existente:
                faixa.unidade = faixa_padrao.unidade
                faixa.valor_minimo = faixa_padrao.valor_minimo
                faixa.valor_maximo = faixa_padrao.valor_maximo
                faixa.resolucao = faixa_padrao.resolucao
                faixa.nominal = faixa_padrao.nominal
                faixa.tolerancia_mais_menos = faixa_padrao.tolerancia_mais_menos
                faixa.save()
                quantidade += 1
        
        if quantidade > 0:
            messages.success(
                request, 
                f'{quantidade} faixa(s) substituÃ­da(s) pela faixa padrÃ£o "{faixa_padrao.valor_minimo} - {faixa_padrao.valor_maximo} {faixa_padrao.unidade.nome}".'
            )
        else:
            messages.warning(request, 'Nenhuma faixa foi substituÃ­da (todas jÃ¡ existem nos instrumentos).')
        
        return redirect('metrologia:categoria_detail', categoria_id=categoria_id)
    
    context = {
        'categoria': categoria,
        'faixas_padrao': faixas_padrao,
        'titulo': f'Substituir Faixas em Massa - {categoria.nome}',
    }
    return render(request, 'metrologia/faixa_instrumento_bulk_replace.html', context)


@login_required
@require_http_methods(["POST"])
def instrumento_bulk_change_category_view(request, categoria_id):
    """Alterar categoria de mÃºltiplos instrumentos em massa."""
    categoria_destino = get_object_or_404(CategoriaInstrumento, id=categoria_id)
    
    instrumento_ids = request.POST.getlist('instrumento_ids')
    
    if not instrumento_ids:
        messages.warning(request, 'Nenhum instrumento foi selecionado.')
        return redirect('metrologia:categoria_detail', categoria_id=categoria_id)
    
    # Obter instrumentos de qualquer categoria
    instrumentos = Instrumento.objects.filter(id__in=instrumento_ids)
    
    if instrumentos.count() != len(instrumento_ids):
        messages.error(request, 'Alguns instrumentos selecionados nÃ£o foram encontrados.')
        return redirect('metrologia:categoria_detail', categoria_id=categoria_id)
    
    quantidade = 0
    for instrumento in instrumentos:
        if instrumento.categoria != categoria_destino:
            instrumento.categoria = categoria_destino
            instrumento.save()
            quantidade += 1
    
    if quantidade > 0:
        messages.success(
            request, 
            f'{quantidade} instrumento(s) movido(s) para a categoria "{categoria_destino.nome}" com sucesso.'
        )
    else:
        messages.info(request, 'Os instrumentos selecionados jÃ¡ estÃ£o nesta categoria.')
    
    return redirect('metrologia:categoria_detail', categoria_id=categoria_id)


@login_required
@require_http_methods(["POST"])
def categoria_bulk_update_sigla_view(request, categoria_id):
    """Atualizar sigla da categoria e aplicar a todos os instrumentos."""
    categoria = get_object_or_404(CategoriaInstrumento, id=categoria_id)
    
    nova_sigla = request.POST.get('sigla', '').strip()
    aplicar_instrumentos = request.POST.get('aplicar_instrumentos') == 'on'
    
    if not nova_sigla:
        messages.error(request, 'Sigla nÃ£o pode ser vazia.')
        return redirect('metrologia:categoria_update', categoria_id=categoria_id)
    
    # Atualizar sigla da categoria
    categoria.sigla = nova_sigla
    categoria.save()
    
    mensagem = f'Categoria atualizada com sigla "{nova_sigla}".'
    
    # Se opÃ§Ã£o marcada, atualizar tags dos instrumentos
    if aplicar_instrumentos:
        instrumentos = Instrumento.objects.filter(categoria=categoria)
        atualizados = 0
        
        for instrumento in instrumentos:
            # Atualizar tag para comeÃ§ar com a sigla
            partes_tag = instrumento.tag.split('-')
            if len(partes_tag) >= 2:
                # Substituir o prefixo existente pela nova sigla
                nova_tag = f"{nova_sigla}-{'-'.join(partes_tag[1:])}"
            else:
                # Se a tag nÃ£o tem hÃ­fen, adicionar sigla como prefixo
                nova_tag = f"{nova_sigla}-{instrumento.tag}"
            
            # Verificar se a nova tag jÃ¡ existe
            if not Instrumento.objects.filter(tag=nova_tag).exclude(id=instrumento.id).exists():
                instrumento.tag = nova_tag
                instrumento.save()
                atualizados += 1
        
        if atualizados > 0:
            mensagem += f' {atualizados} instrumento(s) tiveram suas tags atualizadas.'
    
    messages.success(request, mensagem)
    return redirect('metrologia:categoria_update', categoria_id=categoria_id)


@login_required
@require_http_methods(["POST"])
def categoria_bulk_update_tratativa_view(request, categoria_id):
    """Atualizar tratativa de calibraÃ§Ã£o da categoria e aplicar a todos os instrumentos."""
    categoria = get_object_or_404(CategoriaInstrumento, id=categoria_id)
    
    nova_tratativa = request.POST.get('tratativa_calibracao', '').strip()
    aplicar_instrumentos = request.POST.get('aplicar_instrumentos') == 'on'
    
    # Validar opÃ§Ã£o de tratativa
    opcoes_validas = [choice[0] for choice in CategoriaInstrumento.TRATATIVA_CHOICES]
    if nova_tratativa not in opcoes_validas:
        messages.error(request, 'Tratativa de calibraÃ§Ã£o invÃ¡lida.')
        return redirect('metrologia:categoria_update', categoria_id=categoria_id)
    
    # Atualizar tratativa da categoria
    categoria.tratativa_calibracao = nova_tratativa
    categoria.save()
    
    mensagem = f'Categoria atualizada com tratativa "{dict(CategoriaInstrumento.TRATATIVA_CHOICES).get(nova_tratativa)}".'
    
    # Se opÃ§Ã£o marcada, atualizar tratativa de todos os instrumentos
    if aplicar_instrumentos:
        instrumentos = Instrumento.objects.filter(categoria=categoria)
        atualizados = 0
        
        for instrumento in instrumentos:
            if instrumento.tratativa_calibracao != nova_tratativa:
                instrumento.tratativa_calibracao = nova_tratativa
                instrumento.save()
                atualizados += 1
        
        if atualizados > 0:
            mensagem += f' {atualizados} instrumento(s) tiveram suas tratativas atualizadas.'
    
    messages.success(request, mensagem)
    return redirect('metrologia:categoria_update', categoria_id=categoria_id)


@login_required
@require_http_methods(["POST"])
def categoria_bulk_update_frequencia_view(request, categoria_id):
    """Atualizar frequÃªncia de calibraÃ§Ã£o da categoria e aplicar a todos os instrumentos."""
    categoria = get_object_or_404(CategoriaInstrumento, id=categoria_id)
    
    try:
        nova_frequencia = int(request.POST.get('frequencia_calibracao_meses', 0))
    except (ValueError, TypeError):
        messages.error(request, 'FrequÃªncia deve ser um nÃºmero inteiro.')
        return redirect('metrologia:categoria_update', categoria_id=categoria_id)
    
    if nova_frequencia <= 0:
        messages.error(request, 'FrequÃªncia deve ser maior que zero.')
        return redirect('metrologia:categoria_update', categoria_id=categoria_id)
    
    # Atualizar frequÃªncia da categoria
    categoria.frequencia_calibracao_meses = nova_frequencia
    categoria.save()
    
    mensagem = f'Categoria atualizada com frequÃªncia de {nova_frequencia} mÃªs(es).'
    
    # Se opÃ§Ã£o marcada, atualizar frequÃªncia de todos os instrumentos
    aplicar_instrumentos = request.POST.get('aplicar_instrumentos') == 'on'
    if aplicar_instrumentos:
        from dateutil.relativedelta import relativedelta
        from metrologia.models import HistoricoCalibracao
        
        instrumentos = Instrumento.objects.filter(categoria=categoria, ativo=True)
        atualizados = 0
        
        for instrumento in instrumentos:
            # Atualizar a frequÃªncia do instrumento
            frequencia_anterior = instrumento.frequencia_meses
            instrumento.frequencia_meses = nova_frequencia
            
            # Recalcular prÃ³xima calibraÃ§Ã£o baseado na Ãºltima
            ultimo_historico = HistoricoCalibracao.objects.filter(
                instrumento=instrumento
            ).order_by('-data_calibracao').first()
            
            if ultimo_historico:
                instrumento.data_proxima_calibracao = (
                    ultimo_historico.data_calibracao + relativedelta(months=nova_frequencia)
                )
            
            instrumento.save(update_fields=['frequencia_meses', 'data_proxima_calibracao'])
            atualizados += 1
        
        if atualizados > 0:
            mensagem += f' {atualizados} instrumento(s) tiveram suas frequÃªncias atualizadas com recÃ¡lculo de prÃ³ximas datas.'
        else:
            mensagem += ' Nenhum instrumento ativo encontrado para atualizar.'
    
    messages.success(request, mensagem)
    return redirect('metrologia:categoria_update', categoria_id=categoria_id)

@login_required
@require_http_methods(["POST"])
def categoria_bulk_update_acao_view(request, categoria_id):
    "Atualizar a ao padro (Calibrao/Verificao) da categoria e aplicar a todos os instrumentos."
    categoria = get_object_or_404(CategoriaInstrumento, id=categoria_id)
    
    nova_acao = request.POST.get('acao')
    opcoes_validas = [choice[0] for choice in CategoriaInstrumento.ACAO_CHOICES]
    
    if nova_acao not in opcoes_validas:
        messages.error(request, 'Ao invlida.')
        return redirect('metrologia:categoria_update', categoria_id=categoria_id)
    
    # Atualizar ao da categoria
    categoria.acao = nova_acao
    categoria.save()
    
    mensagem = f'Categoria atualizada com ao padro "{dict(CategoriaInstrumento.ACAO_CHOICES).get(nova_acao)}".'
    
    # Se opo marcada, aplicar a todos os instrumentos
    aplicar_instrumentos = request.POST.get('aplicar_instrumentos') == 'on'
    if aplicar_instrumentos:
        instrumentos = Instrumento.objects.filter(categoria=categoria)
        atualizados = 0
        
        for instrumento in instrumentos:
            if instrumento.acao != nova_acao:
                instrumento.acao = nova_acao
                instrumento.save(update_fields=['acao'])
                atualizados += 1
        
        if atualizados > 0:
            mensagem += f' {atualizados} instrumento(s) tiveram suas aes atualizadas para "{dict(CategoriaInstrumento.ACAO_CHOICES).get(nova_acao)}".'
    
    messages.success(request, mensagem)
    return redirect('metrologia:categoria_update', categoria_id=categoria_id)
