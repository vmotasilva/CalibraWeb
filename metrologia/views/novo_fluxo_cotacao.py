# -*- coding: utf-8 -*-
"""
Views para o novo fluxo de cotações - ETAPAS 1-4

Fluxo:
1. ETAPA 1: Abrir Solicitação de Cotação + Seleção de Instrumentos
2. ETAPA 2: Cotações de Fornecedores
3. ETAPA 3: Seleção de Cotações para Atender Necessidades
4. ETAPA 4: Automatizações (signals)
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Prefetch
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from datetime import datetime, timedelta
from decimal import Decimal

from metrologia.models import (
    SolicitacaoCotacao, ItemSolicitacaoCotacao, CotacaoFornecedor,
    ItemCotacao, AtendimentoSolicitacao, Instrumento, ProcessoAutomatizacao,
    ItemSolicitacaoFaixa
)
from metrologia.forms import (
    SolicitacaoCotacaoForm, ItemSolicitacaoCotacaoForm, CotacaoFornecedorForm,
    ItemCotacaoForm, AtendimentoSolicitacaoForm
)


# ==============================================================================
# ETAPA 1: SOLICITAÇÃO DE COTAÇÃO
# ==============================================================================

@login_required
def solicitacao_list(request):
    """Lista todas as solicitações de cotação"""
    solicitacoes = SolicitacaoCotacao.objects.all().prefetch_related(
        'itens',
        'cotacoes_fornecedores',
        'atendimentos'
    )
    
    # Filtros
    status = request.GET.get('status')
    if status:
        solicitacoes = solicitacoes.filter(status=status)

    context = {
        'solicitacoes': solicitacoes,
        'status_choices': SolicitacaoCotacao._meta.get_field('status').choices,
    }
    return render(request, 'metrologia/novo_fluxo/solicitacao_list.html', context)


@login_required
def solicitacao_create(request):
    """Cria uma nova solicitação de cotação automaticamente - ETAPA 1"""
    # Criar solicitação com valores padrão
    solicitacao = SolicitacaoCotacao.objects.create(
        responsavel=request.user,
        dias_vencimento=30,  # Valor padrão
        status='ABERTA'
    )
    
    messages.success(request, f"Solicitação {solicitacao.numero} criada com sucesso!")
    return redirect('metrologia:solicitacao_detail', pk=solicitacao.id)


@login_required
def solicitacao_detail(request, pk):
    """Detalha uma solicitação e permite gerenciar itens - ETAPA 1"""
    solicitacao = get_object_or_404(SolicitacaoCotacao, pk=pk)
    itens = solicitacao.itens.all()
    cotacoes = solicitacao.cotacoes_fornecedores.prefetch_related('itens')
    atendimentos = solicitacao.atendimentos.select_related('item_cotacao__cotacao_fornecedor__fornecedor')
    
    # Listar instrumentos disponíveis para seleção
    instrumentos_disponiveis = Instrumento.objects.filter(ativo=True).order_by('tag')
    
    # Datas para filtro de vencimento
    hoje = datetime.now().date()
    dias_30 = hoje + timedelta(days=30)
    dias_60 = hoje + timedelta(days=60)
    dias_90 = hoje + timedelta(days=90)
    dias_120 = hoje + timedelta(days=120)
    
    context = {
        'solicitacao': solicitacao,
        'itens': itens,
        'cotacoes': cotacoes,
        'atendimentos': atendimentos,
        'instrumentos_disponiveis': instrumentos_disponiveis,
        'hoje': hoje,
        'dias_30': dias_30,
        'dias_60': dias_60,
        'dias_90': dias_90,
        'dias_120': dias_120,
    }
    return render(request, 'metrologia/novo_fluxo/solicitacao_detail.html', context)


@login_required
def solicitacao_delete(request, pk):
    """Deleta uma solicitação de cotação"""
    solicitacao = get_object_or_404(SolicitacaoCotacao, pk=pk)
    
    if request.method == 'POST':
        numero = solicitacao.numero
        solicitacao.delete()
        messages.success(request, f"Solicitação {numero} deletada com sucesso.")
        return redirect('metrologia:solicitacao_list')
    
    context = {'solicitacao': solicitacao}
    return render(request, 'metrologia/novo_fluxo/solicitacao_confirm_delete.html', context)


@login_required
def solicitacao_itens(request, pk):
    """Gerencia items de uma solicitação - ETAPA 1"""
    solicitacao = get_object_or_404(SolicitacaoCotacao, pk=pk)
    
    if request.method == 'POST':
        # Verificar se é adição em massa (do modal)
        instrumento_ids = request.POST.getlist('instrumentos_selecionados')
        
        if instrumento_ids:
            # Adicionar múltiplos instrumentos via modal
            count_adicionados = 0
            count_duplicados = 0
            
            for instr_id in instrumento_ids:
                try:
                    instrumento = Instrumento.objects.get(id=instr_id)
                    
                    # Verifica se instrumento já foi adicionado
                    if ItemSolicitacaoCotacao.objects.filter(
                        solicitacao=solicitacao,
                        instrumento=instrumento
                    ).exists():
                        count_duplicados += 1
                    else:
                        ItemSolicitacaoCotacao.objects.create(
                            solicitacao=solicitacao,
                            instrumento=instrumento
                        )
                        count_adicionados += 1
                except Instrumento.DoesNotExist:
                    pass
            
            # Mensagens de feedback
            if count_adicionados > 0:
                messages.success(request, f"{count_adicionados} instrumento(s) adicionado(s) com sucesso!")
            if count_duplicados > 0:
                messages.warning(request, f"{count_duplicados} instrumento(s) já estava(m) adicionado(s).")
            
            return redirect('metrologia:solicitacao_detail', pk=solicitacao.id)
        else:
            # Adicionar item via formulário individual (fallback)
            form = ItemSolicitacaoCotacaoForm(request.POST)
            if form.is_valid():
                item = form.save(commit=False)
                item.solicitacao = solicitacao
                
                # Verifica se instrumento já foi adicionado
                if ItemSolicitacaoCotacao.objects.filter(
                    solicitacao=solicitacao,
                    instrumento=item.instrumento
                ).exists():
                    messages.warning(request, f"Instrumento {item.instrumento.tag} já foi adicionado.")
                else:
                    item.save()
                    messages.success(request, f"Instrumento {item.instrumento.tag} adicionado.")
                
                return redirect('metrologia:solicitacao_detail', pk=solicitacao.id)
    else:
        form = ItemSolicitacaoCotacaoForm()
    
    # Listar todos os instrumentos ativos disponíveis para seleção
    instrumentos_disponiveis = Instrumento.objects.filter(ativo=True).order_by('tag')

    itens = solicitacao.itens.all()
    
    # Datas para filtro de vencimento
    hoje = datetime.now().date()
    dias_30 = hoje + timedelta(days=30)
    dias_60 = hoje + timedelta(days=60)
    dias_90 = hoje + timedelta(days=90)
    dias_120 = hoje + timedelta(days=120)
    
    # Para compatibilidade com template
    trinta_dias = dias_30

    context = {
        'solicitacao': solicitacao,
        'form': form,
        'itens': itens,
        'instrumentos_disponiveis': instrumentos_disponiveis,
        'hoje': hoje,
        'trinta_dias': trinta_dias,
        'dias_30': dias_30,
        'dias_60': dias_60,
        'dias_90': dias_90,
        'dias_120': dias_120,
        'titulo': 'Gerenciar Itens da Solicitação'
    }
    return render(request, 'metrologia/novo_fluxo/solicitacao_itens.html', context)


@login_required
def item_solicitacao_edit(request, pk):
    """Edita um item da solicitação - permite preencher pontos de calibração"""
    item = get_object_or_404(ItemSolicitacaoCotacao, pk=pk)
    solicitacao_id = item.solicitacao.id
    
    if request.method == 'POST':
        form = ItemSolicitacaoCotacaoForm(request.POST, instance=item)
        
        # IDs das faixas selecionadas - vindo do campo hidden
        faixas_hidden = request.POST.get('faixas_selecionadas_hidden', '')
        print(f"DEBUG: faixas_hidden = '{faixas_hidden}'")
        faixa_ids = [fid.strip() for fid in faixas_hidden.split(',') if fid.strip()]
        print(f"DEBUG: faixa_ids após parsing = {faixa_ids}")
        
        # Fallback para checkboxes normais (se não houver hidden)
        if not faixa_ids:
            faixa_ids = request.POST.getlist('faixas_selecionadas')
            print(f"DEBUG: faixa_ids após fallback = {faixa_ids}")
        
        if form.is_valid():
            form.save()
            
            # Atualizar faixas selecionadas e pontos
            # Remover faixas não selecionadas
            ItemSolicitacaoFaixa.objects.filter(item_solicitacao=item).delete()
            
            # Se não houver faixas selecionadas, pegar TODAS as faixas do instrumento com 3 pontos
            if not faixa_ids:
                from metrologia.models import FaixaMedicao
                faixa_ids = list(item.instrumento.faixas.values_list('id', flat=True))
                print(f"DEBUG: Ativando automação. faixa_ids = {faixa_ids}")
                print(f"DEBUG: Total de faixas a adicionar: {len(faixa_ids)}")
            else:
                print(f"DEBUG: Usando faixas selecionadas manualmente: {faixa_ids}")
            
            # Adicionar novas faixas selecionadas com seus pontos
            for faixa_id in faixa_ids:
                try:
                    from metrologia.models import FaixaMedicao
                    faixa = FaixaMedicao.objects.get(id=faixa_id)
                    print(f"DEBUG: Processando faixa {faixa_id}")
                    
                    # Obter número de pontos selecionado
                    num_pontos_key = f'pontos_faixa_{faixa_id}'
                    numero_pontos = int(request.POST.get(num_pontos_key, 3))
                    print(f"DEBUG: Faixa {faixa_id} com {numero_pontos} pontos")
                    
                    # Criar registro da faixa
                    faixa_item = ItemSolicitacaoFaixa.objects.create(
                        item_solicitacao=item,
                        faixa_medicao=faixa,
                        numero_pontos=numero_pontos
                    )
                    print(f"DEBUG: ItemSolicitacaoFaixa criado: {faixa_item.id}")
                    

                    # Salvar os pontos de calibração
                    for i in range(1, numero_pontos + 1):
                        ponto_key = f'ponto_{faixa_id}_{i}'
                        ponto_value = request.POST.get(ponto_key)
                        if ponto_value:
                            try:
                                setattr(faixa_item, f'ponto_{i}', float(ponto_value))
                            except (ValueError, TypeError):
                                pass
                    
                    faixa_item.save()
                    
                except FaixaMedicao.DoesNotExist:
                    pass
            
            messages.success(request, f"Instrumento {item.instrumento.tag} atualizado com sucesso!")
            return redirect('metrologia:solicitacao_itens', pk=solicitacao_id)
    else:
        form = ItemSolicitacaoCotacaoForm(instance=item)
    
    # Carregar faixas do instrumento
    faixas = item.instrumento.faixas.all()
    faixas_selecionadas = item.faixas_selecionadas.all()
    
    # Construir dicionário de faixas selecionadas para o template
    faixas_selecionadas_dict = {}
    for faixa_item in faixas_selecionadas:
        faixas_selecionadas_dict[faixa_item.faixa_medicao_id] = faixa_item
    
    context = {
        'form': form,
        'item': item,
        'solicitacao': item.solicitacao,
        'faixas': faixas,
        'faixas_selecionadas': faixas_selecionadas_dict.keys(),
        'faixas_selecionadas_dict': faixas_selecionadas_dict,
        'titulo': f'Editar Item - {item.instrumento.tag}'
    }
    return render(request, 'metrologia/novo_fluxo/item_solicitacao_form.html', context)


@login_required
def item_solicitacao_delete(request, pk):
    """Remove um item da solicitação"""
    item = get_object_or_404(ItemSolicitacaoCotacao, pk=pk)
    solicitacao_id = item.solicitacao.id
    
    if request.method == 'POST':
        instrumento_tag = item.instrumento.tag
        item.delete()
        messages.success(request, f"Instrumento {instrumento_tag} removido.")
        return redirect('metrologia:solicitacao_detail', pk=solicitacao_id)
    
    context = {'item': item}
    return render(request, 'metrologia/novo_fluxo/item_solicitacao_confirm_delete.html', context)


# ==============================================================================
# ETAPA 2: COTAÇÕES DE FORNECEDORES
# ==============================================================================

@login_required
def cotacao_fornecedor_create(request, solicitacao_pk):
    """Cria uma cotação de fornecedor - ETAPA 2"""
    solicitacao = get_object_or_404(SolicitacaoCotacao, pk=solicitacao_pk)
    
    if request.method == 'POST':
        form = CotacaoFornecedorForm(request.POST)
        if form.is_valid():
            cotacao = form.save(commit=False)
            cotacao.solicitacao = solicitacao
            cotacao.criado_por = request.user
            cotacao.save()
            messages.success(request, f"Cotação {cotacao.numero} criada. Agora adicione os itens.")
            return redirect('metrologia:cotacao_fornecedor_itens', pk=cotacao.id)
    else:
        form = CotacaoFornecedorForm()
    
    context = {
        'form': form,
        'solicitacao': solicitacao,
        'titulo': 'Criar Cotação de Fornecedor'
    }
    return render(request, 'metrologia/novo_fluxo/cotacao_fornecedor_form.html', context)


@login_required
def cotacao_fornecedor_detail(request, pk):
    """Detalha uma cotação de fornecedor - ETAPA 2"""
    cotacao = get_object_or_404(CotacaoFornecedor, pk=pk)
    itens = cotacao.itens.select_related('instrumento', 'item_solicitacao')
    
    # Calcula valor total
    valor_total = sum(item.valor_total for item in itens)
    
    context = {
        'cotacao': cotacao,
        'itens': itens,
        'valor_total': valor_total,
    }
    return render(request, 'metrologia/novo_fluxo/cotacao_fornecedor_detail.html', context)


@login_required
def cotacao_fornecedor_itens(request, pk):
    """Gerencia items de uma cotação do fornecedor - ETAPA 2"""
    cotacao = get_object_or_404(CotacaoFornecedor, pk=pk)
    solicitacao = cotacao.solicitacao
    
    if request.method == 'POST':
        form = ItemCotacaoForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.cotacao_fornecedor = cotacao
            
            # Verifica se já existe
            if ItemCotacao.objects.filter(
                cotacao_fornecedor=cotacao,
                instrumento=item.instrumento
            ).exists():
                messages.warning(request, "Este instrumento já foi adicionado a esta cotação.")
            else:
                item.save()
                messages.success(request, f"Item adicionado: {item.instrumento.tag}")
            
            return redirect('metrologia:cotacao_fornecedor_itens', pk=cotacao.id)
    else:
        form = ItemCotacaoForm()
    
    # Filtra apenas itens da solicitação dessa cotação
    form.fields['item_solicitacao'].queryset = solicitacao.itens.all()
    form.fields['instrumento'].queryset = Instrumento.objects.filter(
        solicitacoes_itens__solicitacao=solicitacao
    ).distinct()
    
    itens = cotacao.itens.select_related('instrumento', 'item_solicitacao')
    valor_total = sum(item.valor_total for item in itens)
    
    context = {
        'cotacao': cotacao,
        'solicitacao': solicitacao,
        'form': form,
        'itens': itens,
        'valor_total': valor_total,
        'titulo': 'Gerenciar Itens da Cotação'
    }
    return render(request, 'metrologia/novo_fluxo/cotacao_fornecedor_itens.html', context)


@login_required
def item_cotacao_delete(request, pk):
    """Remove um item da cotação"""
    item = get_object_or_404(ItemCotacao, pk=pk)
    cotacao_id = item.cotacao_fornecedor.id
    
    if request.method == 'POST':
        item.delete()
        messages.success(request, "Item removido.")
        return redirect('metrologia:cotacao_fornecedor_itens', pk=cotacao_id)
    
    context = {'item': item}
    return render(request, 'metrologia/novo_fluxo/item_cotacao_confirm_delete.html', context)


# ==============================================================================
# ETAPA 3: SELEÇÃO DE COTAÇÕES PARA ATENDER NECESSIDADES
# ==============================================================================

@login_required
def atendimento_create(request, solicitacao_pk, item_pk):
    """Cria atendimento: seleciona qual cotação atenderá qual necessidade - ETAPA 3"""
    solicitacao = get_object_or_404(SolicitacaoCotacao, pk=solicitacao_pk)
    item_solicitacao = get_object_or_404(ItemSolicitacaoCotacao, pk=item_pk)
    
    if request.method == 'POST':
        form = AtendimentoSolicitacaoForm(request.POST)
        if form.is_valid():
            atendimento = form.save(commit=False)
            atendimento.solicitacao = solicitacao
            atendimento.item_solicitacao = item_solicitacao
            atendimento.responsavel = request.user
            atendimento.save()
            
            messages.success(request, "Cotação selecionada para atender necessidade.")
            return redirect('metrologia:solicitacao_detail', pk=solicitacao.id)
    else:
        form = AtendimentoSolicitacaoForm()
        
        # Filtra apenas cotações que podem atender este instrumento
        cotacoes_disponiveis = ItemCotacao.objects.filter(
            cotacao_fornecedor__solicitacao=solicitacao,
            instrumento=item_solicitacao.instrumento,
            pode_atender=True
        )
        form.fields['item_cotacao'].queryset = cotacoes_disponiveis
    
    context = {
        'solicitacao': solicitacao,
        'item_solicitacao': item_solicitacao,
        'form': form,
        'titulo': 'Selecionar Cotação para Atender Necessidade'
    }
    return render(request, 'metrologia/novo_fluxo/atendimento_form.html', context)


@login_required
def atendimento_detail(request, pk):
    """Detalha um atendimento selecionado"""
    atendimento = get_object_or_404(AtendimentoSolicitacao, pk=pk)
    
    context = {'atendimento': atendimento}
    return render(request, 'metrologia/novo_fluxo/atendimento_detail.html', context)


# ==============================================================================
# API ENDPOINTS
# ==============================================================================

@login_required
@require_GET
def api_instrumentos_vencendo(request):
    """API: Retorna instrumentos vencendo em um período"""
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    
    if not (data_inicio and data_fim):
        return JsonResponse({'error': 'Parâmetros inválidos'}, status=400)
    
    try:
        data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Formato de data inválido'}, status=400)
    
    instrumentos = Instrumento.objects.filter(
        ativo=True,
        data_proxima_calibracao__gte=data_inicio,
        data_proxima_calibracao__lte=data_fim
    ).values('id', 'tag', 'descricao', 'data_proxima_calibracao')
    
    return JsonResponse({'instrumentos': list(instrumentos)})


@login_required
@require_POST
def atendimento_confirmar(request, pk):
    """Confirma um atendimento (muda status para CONFIRMADA)"""
    atendimento = get_object_or_404(AtendimentoSolicitacao, pk=pk)
    
    atendimento.status = 'CONFIRMADA'
    atendimento.save()
    
    # TODO: Disparar sinais para automatizações (ETAPA 4)
    # trigger_automatizacao(atendimento)
    
    messages.success(request, "Atendimento confirmado! Automatizações podem ter sido acionadas.")
    return redirect('metrologia:atendimento_detail', pk=atendimento.id)

