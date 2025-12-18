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
    
    # Faixas padrão da categoria
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


@login_required
@require_http_methods(["POST"])
def faixa_categoria_add_to_instrument_view(request, categoria_id):
    """Adicionar uma faixa padrão da categoria a um instrumento."""
    categoria = get_object_or_404(CategoriaInstrumento, id=categoria_id)
    
    instrumento_id = request.POST.get('instrumento_id')
    faixa_padrao_id = request.POST.get('faixa_padrao_id')
    
    instrumento = get_object_or_404(Instrumento, id=instrumento_id, categoria=categoria)
    faixa_padrao = get_object_or_404(FaixaMedicaoPadraoCategoria, id=faixa_padrao_id, categoria=categoria)
    
    # Verificar se já existe essa faixa no instrumento
    faixa_existente = FaixaMedicao.objects.filter(
        instrumento=instrumento,
        unidade=faixa_padrao.unidade,
        valor_minimo=faixa_padrao.valor_minimo,
        valor_maximo=faixa_padrao.valor_maximo
    ).exists()
    
    if faixa_existente:
        messages.warning(request, 'Esta faixa já existe para este instrumento.')
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
    """Substituir uma faixa de um instrumento por uma faixa padrão."""
    categoria = get_object_or_404(CategoriaInstrumento, id=categoria_id)
    faixa_atual = get_object_or_404(FaixaMedicao, id=faixa_id, instrumento__categoria=categoria)
    
    # Faixas padrão disponíveis
    faixas_padrao = FaixaMedicaoPadraoCategoria.objects.filter(
        categoria=categoria
    ).select_related('unidade').order_by('valor_minimo')
    
    if request.method == 'POST':
        faixa_padrao_id = request.POST.get('faixa_padrao_id')
        faixa_padrao = get_object_or_404(FaixaMedicaoPadraoCategoria, id=faixa_padrao_id, categoria=categoria)
        
        # Verificar se a nova faixa já existe no instrumento
        faixa_existente = FaixaMedicao.objects.filter(
            instrumento=faixa_atual.instrumento,
            unidade=faixa_padrao.unidade,
            valor_minimo=faixa_padrao.valor_minimo,
            valor_maximo=faixa_padrao.valor_maximo
        ).exclude(id=faixa_atual.id).exists()
        
        if faixa_existente:
            messages.warning(request, 'A faixa padrão selecionada já existe para este instrumento.')
            return redirect('metrologia:faixa_instrumento_replace', categoria_id=categoria_id, faixa_id=faixa_id)
        
        # Atualizar a faixa com valores da faixa padrão
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
            f'Faixa do instrumento "{faixa_atual.instrumento.tag}" substituída de "{faixa_antiga}" para "{faixa_nova}".'
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
    """Remover múltiplas faixas de instrumentos em massa."""
    categoria = get_object_or_404(CategoriaInstrumento, id=categoria_id)
    
    faixa_ids = request.POST.getlist('faixa_ids')
    
    if not faixa_ids:
        messages.warning(request, 'Nenhuma faixa foi selecionada.')
        return redirect('metrologia:categoria_detail', categoria_id=categoria_id)
    
    # Validar que todas as faixas pertencem à categoria
    faixas = FaixaMedicao.objects.filter(
        id__in=faixa_ids,
        instrumento__categoria=categoria
    )
    
    if faixas.count() != len(faixa_ids):
        messages.error(request, 'Algumas faixas selecionadas não pertencem a esta categoria.')
        return redirect('metrologia:categoria_detail', categoria_id=categoria_id)
    
    quantidade = faixas.count()
    faixas.delete()
    
    messages.success(request, f'{quantidade} faixa(s) removida(s) com sucesso.')
    return redirect('metrologia:categoria_detail', categoria_id=categoria_id)


@login_required
@require_http_methods(["GET", "POST"])
def faixa_instrumento_bulk_replace_view(request, categoria_id):
    """Substituir múltiplas faixas por uma faixa padrão."""
    categoria = get_object_or_404(CategoriaInstrumento, id=categoria_id)
    
    # Faixas padrão disponíveis
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
            messages.error(request, 'Nenhuma faixa padrão foi selecionada.')
            return redirect('metrologia:categoria_detail', categoria_id=categoria_id)
        
        faixa_padrao = get_object_or_404(FaixaMedicaoPadraoCategoria, id=faixa_padrao_id, categoria=categoria)
        
        # Validar e atualizar faixas
        faixas = FaixaMedicao.objects.filter(
            id__in=faixa_ids,
            instrumento__categoria=categoria
        )
        
        if faixas.count() != len(faixa_ids):
            messages.error(request, 'Algumas faixas selecionadas não pertencem a esta categoria.')
            return redirect('metrologia:categoria_detail', categoria_id=categoria_id)
        
        quantidade = 0
        for faixa in faixas:
            # Verificar se a nova faixa já existe neste instrumento
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
                f'{quantidade} faixa(s) substituída(s) pela faixa padrão "{faixa_padrao.valor_minimo} - {faixa_padrao.valor_maximo} {faixa_padrao.unidade.nome}".'
            )
        else:
            messages.warning(request, 'Nenhuma faixa foi substituída (todas já existem nos instrumentos).')
        
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
    """Alterar categoria de múltiplos instrumentos em massa."""
    categoria_destino = get_object_or_404(CategoriaInstrumento, id=categoria_id)
    
    instrumento_ids = request.POST.getlist('instrumento_ids')
    
    if not instrumento_ids:
        messages.warning(request, 'Nenhum instrumento foi selecionado.')
        return redirect('metrologia:categoria_detail', categoria_id=categoria_id)
    
    # Obter instrumentos de qualquer categoria
    instrumentos = Instrumento.objects.filter(id__in=instrumento_ids)
    
    if instrumentos.count() != len(instrumento_ids):
        messages.error(request, 'Alguns instrumentos selecionados não foram encontrados.')
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
        messages.info(request, 'Os instrumentos selecionados já estão nesta categoria.')
    
    return redirect('metrologia:categoria_detail', categoria_id=categoria_id)


@login_required
@require_http_methods(["POST"])
def categoria_bulk_update_sigla_view(request, categoria_id):
    """Atualizar sigla da categoria e aplicar a todos os instrumentos."""
    categoria = get_object_or_404(CategoriaInstrumento, id=categoria_id)
    
    nova_sigla = request.POST.get('sigla', '').strip()
    aplicar_instrumentos = request.POST.get('aplicar_instrumentos') == 'on'
    
    if not nova_sigla:
        messages.error(request, 'Sigla não pode ser vazia.')
        return redirect('metrologia:categoria_update', categoria_id=categoria_id)
    
    # Atualizar sigla da categoria
    categoria.sigla = nova_sigla
    categoria.save()
    
    mensagem = f'Categoria atualizada com sigla "{nova_sigla}".'
    
    # Se opção marcada, atualizar tags dos instrumentos
    if aplicar_instrumentos:
        instrumentos = Instrumento.objects.filter(categoria=categoria)
        atualizados = 0
        
        for instrumento in instrumentos:
            # Atualizar tag para começar com a sigla
            partes_tag = instrumento.tag.split('-')
            if len(partes_tag) >= 2:
                # Substituir o prefixo existente pela nova sigla
                nova_tag = f"{nova_sigla}-{'-'.join(partes_tag[1:])}"
            else:
                # Se a tag não tem hífen, adicionar sigla como prefixo
                nova_tag = f"{nova_sigla}-{instrumento.tag}"
            
            # Verificar se a nova tag já existe
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
    """Atualizar tratativa de calibração da categoria e aplicar a todos os instrumentos."""
    categoria = get_object_or_404(CategoriaInstrumento, id=categoria_id)
    
    nova_tratativa = request.POST.get('tratativa_calibracao', '').strip()
    aplicar_instrumentos = request.POST.get('aplicar_instrumentos') == 'on'
    
    # Validar opção de tratativa
    opcoes_validas = [choice[0] for choice in CategoriaInstrumento.TRATATIVA_CHOICES]
    if nova_tratativa not in opcoes_validas:
        messages.error(request, 'Tratativa de calibração inválida.')
        return redirect('metrologia:categoria_update', categoria_id=categoria_id)
    
    # Atualizar tratativa da categoria
    categoria.tratativa_calibracao = nova_tratativa
    categoria.save()
    
    mensagem = f'Categoria atualizada com tratativa "{dict(CategoriaInstrumento.TRATATIVA_CHOICES).get(nova_tratativa)}".'
    
    # Se opção marcada, atualizar tratativa de todos os instrumentos
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
