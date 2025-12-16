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
from django.views.decorators.http import require_POST, require_GET, require_http_methods
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
    """Cria uma nova solicitação de cotação - ETAPA 1"""
    # Criar a solicitação automaticamente com valores defaults
    try:
        solicitacao = SolicitacaoCotacao.objects.create(
            responsavel=request.user,
            dias_vencimento=30,
        )
        messages.success(request, f"Solicitação {solicitacao.numero} criada com sucesso!")
        return redirect('metrologia:solicitacao_detail', pk=solicitacao.id)
    except Exception as e:
        messages.error(request, f"Erro ao criar solicitação: {str(e)}")
        return redirect('metrologia:solicitacao_list')


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
def solicitacao_update(request, pk):
    """Atualiza informações da solicitação de cotação - ETAPA 1"""
    solicitacao = get_object_or_404(SolicitacaoCotacao, pk=pk)
    
    if request.method == 'POST':
        form = SolicitacaoCotacaoForm(request.POST, instance=solicitacao)
        if form.is_valid():
            form.save()
            messages.success(request, f"Solicitação {solicitacao.numero} atualizada com sucesso!")
            return redirect('metrologia:solicitacao_detail', pk=solicitacao.id)
    else:
        form = SolicitacaoCotacaoForm(instance=solicitacao)
    
    context = {
        'solicitacao': solicitacao,
        'form': form,
        'titulo': f'Editar Solicitação {solicitacao.numero}',
    }
    return render(request, 'metrologia/novo_fluxo/solicitacao_form.html', context)


@login_required
def solicitacao_delete(request, pk):
    """Deleta uma solicitação de cotação com todas suas dependências"""
    solicitacao = get_object_or_404(SolicitacaoCotacao, pk=pk)
    
    if request.method == 'POST':
        numero = solicitacao.numero
        
        try:
            # Deletar em cascata: Atendimentos → ItemCotações → Cotações → Itens → Solicitação
            
            # 1. Deletar atendimentos (deletam referências a items)
            solicitacao.atendimentos.all().delete()
            
            # 2. Deletar cotações (deletam item cotações em cascata)
            solicitacao.cotacoes_fornecedores.all().delete()
            
            # 3. Deletar itens da solicitação
            solicitacao.itens.all().delete()
            
            # 4. Deletar a solicitação
            solicitacao.delete()
            
            messages.success(request, f"Solicitação {numero} deletada com sucesso.")
            return redirect('metrologia:solicitacao_list')
            
        except Exception as e:
            messages.error(request, f"Erro ao deletar solicitação: {str(e)}")
            return redirect('metrologia:solicitacao_detail', pk=pk)
    
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
            return redirect('metrologia:solicitacao_detail', pk=solicitacao_id)
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
            
            # Criar automaticamente ItemCotacao para cada instrumento da solicitação
            for item_solicitacao in solicitacao.itens.all():
                ItemCotacao.objects.get_or_create(
                    cotacao_fornecedor=cotacao,
                    instrumento=item_solicitacao.instrumento,
                    defaults={
                        'item_solicitacao': item_solicitacao,
                        'valor_unitario': Decimal('0.00'),
                    }
                )
            
            messages.success(request, f"Cotação {cotacao.numero} criada. Preencha os dados e itens.")
            return redirect('metrologia:cotacao_fornecedor_update', pk=cotacao.id)
    else:
        form = CotacaoFornecedorForm()
    
    context = {
        'form': form,
        'solicitacao': solicitacao,
        'titulo': 'Criar Cotação de Fornecedor'
    }
    return render(request, 'metrologia/novo_fluxo/cotacao_fornecedor_form.html', context)


@login_required
def cotacao_fornecedor_update(request, pk):
    """Edita uma cotação de fornecedor - ETAPA 2"""
    cotacao = get_object_or_404(CotacaoFornecedor, pk=pk)
    
    if request.method == 'POST':
        form = CotacaoFornecedorForm(request.POST, instance=cotacao)
        if form.is_valid():
            was_approved = cotacao.aprovada
            cotacao_obj = form.save(commit=False)
            
            # Atualizar status baseado na aprovação
            if cotacao_obj.aprovada:
                # Se foi aprovada agora e não estava antes
                if not was_approved:
                    from django.utils import timezone
                    cotacao_obj.data_aprovacao = timezone.now()
                    cotacao_obj.aprovado_por = request.user
                cotacao_obj.status = 'ACEITA'
            else:
                # Se desmarcar a aprovação, volta para rascunho
                cotacao_obj.status = 'RASCUNHO'
            
            cotacao_obj.save()
            
            # Processar itens se houver dados na tabela
            itens_solicitacao = cotacao.solicitacao.itens.all()
            
            for item_sol in itens_solicitacao:
                # Pegar ou criar o item de cotação
                item_cotacao, created = ItemCotacao.objects.get_or_create(
                    cotacao_fornecedor=cotacao,
                    instrumento=item_sol.instrumento,
                    defaults={
                        'item_solicitacao': item_sol,
                        'valor_unitario': Decimal('0.00'),
                    }
                )
                
                # Atualizar se o fornecedor pode atender
                pode_atender = f'item_{item_sol.id}_pode_atender' in request.POST
                item_cotacao.pode_atender = pode_atender
                
                # Atualizar valor
                valor = request.POST.get(f'item_{item_sol.id}_valor', '')
                if valor:
                    try:
                        item_cotacao.valor_unitario = Decimal(valor)
                    except:
                        item_cotacao.valor_unitario = Decimal('0.00')
                
                # Atualizar tipo de atendimento
                local = request.POST.get(f'item_{item_sol.id}_local', '')
                if local:
                    item_cotacao.local_atendimento = local
                
                item_cotacao.save()
            
            messages.success(request, f"Cotação {cotacao.numero} atualizada com sucesso!")
            return redirect('metrologia:cotacao_fornecedor_detail', pk=cotacao.id)
    else:
        form = CotacaoFornecedorForm(instance=cotacao)
    
    # Buscar itens da solicitação e preparar com dados já salvos
    itens_solicitacao = cotacao.solicitacao.itens.all()
    
    # Criar lista com dados combinados (item_solicitacao + item_cotacao)
    itens_com_dados = []
    for item_sol in itens_solicitacao:
        # Tenta buscar o item_cotacao correspondente
        try:
            item_cot = cotacao.itens.get(instrumento=item_sol.instrumento)
        except ItemCotacao.DoesNotExist:
            item_cot = None
        
        itens_com_dados.append({
            'solicitacao': item_sol,
            'cotacao': item_cot
        })
    
    context = {
        'form': form,
        'cotacao': cotacao,
        'solicitacao': cotacao.solicitacao,
        'itens_com_dados': itens_com_dados,
        'titulo': f'Editar Cotação {cotacao.numero}',
        'mode': 'edit'
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
            
            # Atualizar status da solicitação
            solicitacao.atualizar_status_automatico()
            
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


@login_required
def atendimento_create_from_cotacao(request, cotacao_id):
    """Cria atendimentos para os itens selecionados de uma cotação aprovada"""
    cotacao = get_object_or_404(CotacaoFornecedor, pk=cotacao_id)
    
    # Apenas cotações aprovadas podem gerar atendimentos
    if not cotacao.aprovada:
        messages.error(request, "Apenas cotações aprovadas podem gerar atendimentos.")
        return redirect('metrologia:cotacao_fornecedor_detail', pk=cotacao.id)
    
    if request.method == 'POST':
        itens_selecionados = request.POST.getlist('itens_selecionados')
        data_prevista = request.POST.get('data_prevista')
        
        if not itens_selecionados or not data_prevista:
            messages.error(request, "Selecione pelo menos um item e informe a data prevista.")
            return redirect('metrologia:cotacao_fornecedor_detail', pk=cotacao.id)
        
        # Converter data string para date object
        from datetime import datetime
        try:
            data_prevista = datetime.strptime(data_prevista, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, "Data inválida.")
            return redirect('metrologia:cotacao_fornecedor_detail', pk=cotacao.id)
        
        # Criar atendimentos para cada item selecionado
        atendimentos_criados = 0
        for item_id in itens_selecionados:
            try:
                item_cotacao = ItemCotacao.objects.get(id=item_id, cotacao_fornecedor=cotacao)
                item_solicitacao = item_cotacao.item_solicitacao
                
                # Verificar se já existe atendimento para este item
                if not AtendimentoSolicitacao.objects.filter(
                    item_solicitacao=item_solicitacao,
                    item_cotacao=item_cotacao
                ).exists():
                    atendimento = AtendimentoSolicitacao.objects.create(
                        solicitacao=cotacao.solicitacao,
                        item_solicitacao=item_solicitacao,
                        item_cotacao=item_cotacao,
                        data_prevista_atendimento=data_prevista,
                        responsavel=request.user,
                        status='PENDENTE'
                    )
                    atendimentos_criados += 1
            except ItemCotacao.DoesNotExist:
                continue
        
        if atendimentos_criados > 0:
            # Atualizar status da solicitação
            cotacao.solicitacao.atualizar_status_automatico()
            messages.success(request, f"{atendimentos_criados} atendimento(s) adicionado(s) com sucesso!")
        else:
            messages.warning(request, "Nenhum novo atendimento foi criado (itens podem já estar alocados).")
        
        return redirect('metrologia:solicitacao_detail', pk=cotacao.solicitacao.id)
    
    # GET request - mostrar o form
    itens = cotacao.itens.all()
    context = {
        'cotacao': cotacao,
        'itens': itens,
    }
    return redirect('metrologia:cotacao_fornecedor_detail', pk=cotacao.id)


@login_required
@require_http_methods(['POST'])
def atendimento_atualizar_dados(request):
    """API endpoint para atualizar dados dos atendimentos em lote"""
    import json
    
    try:
        data = json.loads(request.body)
        tipo = data.get('tipo')
        campos = data.get('campos', {})
        
        print(f"DEBUG: Recebido tipo={tipo}, campos={campos}")
        
        atualizados = 0
        solicitacao_ids = set()
        
        for atendimento_id_str, valores in campos.items():
            try:
                # Converter ID para inteiro
                atendimento_id = int(atendimento_id_str)
                atendimento = AtendimentoSolicitacao.objects.get(id=atendimento_id)
                solicitacao_ids.add(atendimento.solicitacao_id)
                
                print(f"DEBUG: Atualizando atendimento {atendimento_id} com valores {valores}")
                
                # Atualizar conforme o tipo
                if tipo == 'NO_LOCAL':
                    if valores.get('data_realizada'):
                        atendimento.data_realizada = valores.get('data_realizada')
                    atendimento.observacoes = f"Técnico: {valores.get('tecnico', 'N/A')}"
                    atendimento.save()
                    atualizados += 1
                    
                elif tipo == 'NO_LABORATORIO':
                    if valores.get('data_envio'):
                        atendimento.data_envio = valores.get('data_envio')
                    if valores.get('data_retorno'):
                        atendimento.data_retorno = valores.get('data_retorno')
                    obs = f"Envio: {valores.get('data_envio', 'N/A')}\nRetorno: {valores.get('data_retorno', 'N/A')}\nObs: {valores.get('observacoes', '')}"
                    atendimento.observacoes = obs
                    atendimento.save()
                    atualizados += 1
                    
                elif tipo == 'COMPRAR_NOVO':
                    if valores.get('data_chegada_realizada'):
                        atendimento.data_chegada = valores.get('data_chegada_realizada')
                    atendimento.observacoes = valores.get('observacoes', '')
                    atendimento.save()
                    atualizados += 1
                    
            except ValueError:
                print(f"DEBUG: ID inválido: {atendimento_id_str}")
                continue
            except AtendimentoSolicitacao.DoesNotExist:
                print(f"DEBUG: AtendimentoSolicitacao {atendimento_id_str} não encontrado")
                continue
            except Exception as e:
                print(f"DEBUG: Erro ao atualizar atendimento {atendimento_id_str}: {str(e)}")
                continue
        
        # Atualizar status das solicitações afetadas
        from metrologia.models import SolicitacaoCotacao
        for solicitacao_id in solicitacao_ids:
            try:
                solicitacao = SolicitacaoCotacao.objects.get(id=solicitacao_id)
                solicitacao.atualizar_status_automatico()
                print(f"DEBUG: Status da solicitação {solicitacao_id} atualizado para {solicitacao.status}")
            except Exception as e:
                print(f"DEBUG: Erro ao atualizar status da solicitação {solicitacao_id}: {str(e)}")
        
        print(f"DEBUG: Total atualizado: {atualizados}")
        
        return JsonResponse({
            'success': True,
            'message': f'{atualizados} atendimento(s) atualizado(s)',
            'atualizados': atualizados
        })
        
    except json.JSONDecodeError as e:
        print(f"DEBUG: Erro ao decodificar JSON: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Erro ao processar JSON: {str(e)}'
        }, status=400)
    except Exception as e:
        print(f"DEBUG: Erro geral: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@require_http_methods(['POST'])
def atendimento_atualizar_cotacao(request):
    """API endpoint para atualizar dados de entrega por cotação (seleção de instrumentos)"""
    import json
    
    try:
        data = json.loads(request.body)
        cotacao_id = data.get('cotacao_id')
        atendimento_ids = data.get('atendimento_ids', [])
        data_chegada = data.get('data_chegada')
        observacoes = data.get('observacoes', '')
        
        print(f"DEBUG: Atualizando cotação {cotacao_id}")
        print(f"DEBUG: Atendimentos: {atendimento_ids}")
        print(f"DEBUG: Data chegada: {data_chegada}")
        print(f"DEBUG: Observações: {observacoes}")
        
        atualizados = 0
        solicitacao_ids = set()
        
        # Atualizar os atendimentos selecionados
        for atendimento_id in atendimento_ids:
            try:
                atendimento = AtendimentoSolicitacao.objects.get(id=atendimento_id)
                solicitacao_ids.add(atendimento.solicitacao_id)
                atendimento.data_chegada = data_chegada
                atendimento.save()
                atualizados += 1
                print(f"DEBUG: Atendimento {atendimento_id} atualizado")
            except AtendimentoSolicitacao.DoesNotExist:
                print(f"DEBUG: Atendimento {atendimento_id} não encontrado")
                continue
            except Exception as e:
                print(f"DEBUG: Erro ao atualizar atendimento {atendimento_id}: {str(e)}")
                continue
        
        # Atualizar observações da cotação
        if cotacao_id:
            try:
                from metrologia.models import CotacaoFornecedor
                cotacao = CotacaoFornecedor.objects.get(id=cotacao_id)
                cotacao.observacoes_execucao = observacoes
                cotacao.save()
                print(f"DEBUG: Observações da cotação {cotacao_id} atualizadas")
            except Exception as e:
                print(f"DEBUG: Erro ao atualizar observações: {str(e)}")
        
        # Atualizar status das solicitações afetadas
        from metrologia.models import SolicitacaoCotacao
        for solicitacao_id in solicitacao_ids:
            try:
                solicitacao = SolicitacaoCotacao.objects.get(id=solicitacao_id)
                solicitacao.atualizar_status_automatico()
                print(f"DEBUG: Status da solicitação {solicitacao_id} atualizado para {solicitacao.status}")
            except Exception as e:
                print(f"DEBUG: Erro ao atualizar status da solicitação {solicitacao_id}: {str(e)}")
        
        print(f"DEBUG: Total atualizado: {atualizados}")
        
        return JsonResponse({
            'success': True,
            'message': f'{atualizados} atendimento(s) atualizado(s)',
            'atualizados': atualizados
        })
        
    except json.JSONDecodeError as e:
        print(f"DEBUG: Erro ao decodificar JSON: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Erro ao processar JSON: {str(e)}'
        }, status=400)
    except Exception as e:
        print(f"DEBUG: Erro geral: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


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


from django.views.decorators.http import require_POST
from django.http import JsonResponse

@require_POST
@login_required
def solicitacao_marcar_concluida(request, pk):
    solicitacao = get_object_or_404(SolicitacaoCotacao, pk=pk)
    solicitacao.marcar_concluida()
    return JsonResponse({'success': True, 'status': solicitacao.get_status_display()})

@require_POST
@login_required
def solicitacao_marcar_cancelada(request, pk):
    solicitacao = get_object_or_404(SolicitacaoCotacao, pk=pk)
    solicitacao.marcar_cancelada()
    return JsonResponse({'success': True, 'status': solicitacao.get_status_display()})

@require_POST
@login_required
def solicitacao_reativar(request, pk):
    solicitacao = get_object_or_404(SolicitacaoCotacao, pk=pk)
    solicitacao.reativar()
    return JsonResponse({'success': True, 'status': solicitacao.get_status_display()})

@require_POST
@login_required
def solicitacao_reabrir(request, pk):
    solicitacao = get_object_or_404(SolicitacaoCotacao, pk=pk)
    solicitacao.reabrir()
    return JsonResponse({'success': True, 'status': solicitacao.get_status_display()})


# ==============================================================================
# NOVOS ENDPOINTS: ATUALIZAR DADOS DE ATENDIMENTO
# ==============================================================================

@require_POST
@login_required
def atendimento_atualizar_data_calibracao(request, pk):
    """
    Atualiza data de calibração (NO_LOCAL) de um atendimento.
    
    POST data:
    - data_realizada: YYYY-MM-DD
    - tecnico_responsavel: string
    - observacoes: string
    """
    atendimento = get_object_or_404(AtendimentoSolicitacao, pk=pk)
    
    try:
        data_realizada = request.POST.get('data_realizada')
        tecnico_responsavel = request.POST.get('tecnico_responsavel', '')
        observacoes = request.POST.get('observacoes', '')
        
        # Validar data
        if not data_realizada:
            return JsonResponse({'success': False, 'error': 'Data realizada é obrigatória'}, status=400)
        
        # Atualizar atendimento
        atendimento.data_realizada = data_realizada
        if tecnico_responsavel:
            atendimento.tecnico_responsavel = tecnico_responsavel
        if observacoes:
            atendimento.observacoes = observacoes
        atendimento.save()
        
        # Atualizar status da solicitação (automaticamente)
        from metrologia.models import SolicitacaoCotacao
        solicitacao = atendimento.solicitacao
        solicitacao.atualizar_status_automatico()
        
        messages.success(request, "Data de calibração atualizada com sucesso!")
        return redirect('visualizar_instrumento', instrumento_id=atendimento.item_solicitacao.instrumento.id)
    
    except Exception as e:
        messages.error(request, f"Erro ao atualizar: {str(e)}")
        return redirect('visualizar_instrumento', instrumento_id=atendimento.item_solicitacao.instrumento.id)


@require_POST
@login_required
def atendimento_atualizar_chegada(request, pk):
    """
    Atualiza data de chegada (COMPRAR_NOVO) de um atendimento.
    
    POST data:
    - data_chegada: YYYY-MM-DD
    - observacoes: string
    """
    atendimento = get_object_or_404(AtendimentoSolicitacao, pk=pk)
    
    try:
        data_chegada = request.POST.get('data_chegada')
        observacoes = request.POST.get('observacoes', '')
        
        # Validar data
        if not data_chegada:
            return JsonResponse({'success': False, 'error': 'Data de chegada é obrigatória'}, status=400)
        
        # Atualizar atendimento
        atendimento.data_chegada = data_chegada
        if observacoes:
            atendimento.observacoes = observacoes
        atendimento.status = 'CONCLUIDA'  # Marcar como concluído
        atendimento.save()
        
        # Atualizar status da solicitação
        solicitacao = atendimento.solicitacao
        solicitacao.atualizar_status_automatico()
        
        messages.success(request, "Data de chegada registrada com sucesso!")
        return redirect('visualizar_instrumento', instrumento_id=atendimento.item_solicitacao.instrumento.id)
    
    except Exception as e:
        messages.error(request, f"Erro ao registrar chegada: {str(e)}")
        return redirect('visualizar_instrumento', instrumento_id=atendimento.item_solicitacao.instrumento.id)


@require_POST
@login_required
def atendimento_atualizar_rastreio(request, pk):
    """
    Atualiza dados de rastreio (NO_LABORATORIO) de um atendimento.
    
    POST data:
    - data_envio: YYYY-MM-DD
    - data_retorno_previsto: YYYY-MM-DD
    - data_retorno: YYYY-MM-DD
    - observacoes: string
    """
    atendimento = get_object_or_404(AtendimentoSolicitacao, pk=pk)
    
    try:
        data_envio = request.POST.get('data_envio')
        data_retorno_previsto = request.POST.get('data_retorno_previsto')
        data_retorno = request.POST.get('data_retorno')
        observacoes = request.POST.get('observacoes', '')
        
        # Atualizar campos
        if data_envio:
            atendimento.data_envio = data_envio
        if data_retorno_previsto:
            atendimento.data_retorno_previsto = data_retorno_previsto
        if data_retorno:
            atendimento.data_retorno = data_retorno
            atendimento.status = 'CONCLUIDA'  # Marcar como concluído quando retornar
        if observacoes:
            atendimento.observacoes = observacoes
        
        atendimento.save()
        
        # Atualizar status da solicitação
        solicitacao = atendimento.solicitacao
        solicitacao.atualizar_status_automatico()
        
        messages.success(request, "Rastreio atualizado com sucesso!")
        return redirect('visualizar_instrumento', instrumento_id=atendimento.item_solicitacao.instrumento.id)
    
    except Exception as e:
        messages.error(request, f"Erro ao atualizar rastreio: {str(e)}")
        return redirect('visualizar_instrumento', instrumento_id=atendimento.item_solicitacao.instrumento.id)


# ==============================================================================
# NEW: ETAPA 5: ATUALIZAÇÃO PÓS-COTAÇÃO
# ==============================================================================

@login_required
@require_POST
def atendimento_registrar_historico(request, atendimento_id):
    """Registrar novo histórico de calibração relacionado ao atendimento"""
    from metrologia.models import HistoricoCalibracao
    from datetime import date
    
    try:
        atendimento = get_object_or_404(AtendimentoSolicitacao, id=atendimento_id)
        instrumento = atendimento.item_solicitacao.instrumento
        
        # Obter dados do formulário
        data_calibracao = request.POST.get('data_calibracao')
        numero_certificado = request.POST.get('numero_certificado', 'S/N')
        resultado = request.POST.get('resultado', 'APROVADO_SEM_CORRECAO')
        responsavel = request.POST.get('responsavel', '')
        observacoes = request.POST.get('observacoes', '')
        
        if not data_calibracao:
            messages.error(request, "Data de calibração é obrigatória!")
            return redirect('visualizar_instrumento', instrumento_id=instrumento.id)
        
        # Criar histórico relacionado ao atendimento
        historico = HistoricoCalibracao.objects.create(
            instrumento=instrumento,
            atendimento=atendimento,  # NEW: Linkagem com atendimento
            data_calibracao=data_calibracao,
            data_aprovacao=date.today(),
            numero_certificado=numero_certificado,
            tipo_calibracao='EXTERNA',
            responsavel=responsavel,
            fornecedor=atendimento.item_cotacao.cotacao_fornecedor.fornecedor.nome_fantasia,
            resultado=resultado,
            observacoes=observacoes,
        )
        
        # Atualizar data_realizada do atendimento
        atendimento.data_realizada = data_calibracao
        atendimento.status = 'CONCLUIDA'
        atendimento.save()
        
        # Atualizar status da solicitação
        solicitacao = atendimento.solicitacao
        solicitacao.atualizar_status_automatico()
        
        messages.success(request, f"✓ Histórico de calibração registrado com sucesso! (ID: {historico.id})")
        return redirect('visualizar_instrumento', instrumento_id=instrumento.id)
    
    except Exception as e:
        messages.error(request, f"Erro ao registrar histórico: {str(e)}")
        return redirect('visualizar_instrumento', instrumento_id=atendimento.item_solicitacao.instrumento.id)


@login_required
@require_POST
def atendimento_iniciar_substituicao(request, atendimento_id):
    """Iniciar fluxo de substituição do instrumento"""
    from metrologia.models import Instrumento
    
    try:
        atendimento = get_object_or_404(AtendimentoSolicitacao, id=atendimento_id)
        instrumento_antigo = atendimento.item_solicitacao.instrumento
        
        # Obter dados do formulário
        data_entrega = request.POST.get('data_entrega')
        numero_serie = request.POST.get('numero_serie', '')
        observacoes = request.POST.get('observacoes', '')
        
        if not data_entrega:
            messages.error(request, "Data de entrega é obrigatória!")
            return redirect('visualizar_instrumento', instrumento_id=instrumento_antigo.id)
        
        # Marcar atendimento como em processo de substituição
        atendimento.data_entrega_nova_aquisicao = data_entrega
        atendimento.observacoes = observacoes
        atendimento.status = 'EXECUTANDO'
        atendimento.save()
        
        # Se houver número de série do novo instrumento, criar instrumento novo
        if numero_serie:
            novo_instrumento = Instrumento.objects.create(
                tag=f"{instrumento_antigo.tag}_NOVO",
                modelo=instrumento_antigo.modelo,
                fabricante=instrumento_antigo.fabricante,
                serie=numero_serie,
                categoria=instrumento_antigo.categoria,
                responsavel=instrumento_antigo.responsavel,
                localizacao=instrumento_antigo.localizacao,
            )
            messages.success(request, f"✓ Novo instrumento criado: {novo_instrumento.tag}")
        else:
            messages.info(request, "Aguardando número de série do novo instrumento...")
        
        # Atualizar status da solicitação
        solicitacao = atendimento.solicitacao
        solicitacao.atualizar_status_automatico()
        
        messages.success(request, "✓ Processo de substituição iniciado com sucesso!")
        return redirect('visualizar_instrumento', instrumento_id=instrumento_antigo.id)
    
    except Exception as e:
        messages.error(request, f"Erro ao iniciar substituição: {str(e)}")
        return redirect('visualizar_instrumento', instrumento_id=atendimento.item_solicitacao.instrumento.id)
