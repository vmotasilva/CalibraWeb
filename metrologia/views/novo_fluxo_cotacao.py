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
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import ProtectedError
from django.db.models import Q, Prefetch
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET, require_http_methods
from datetime import datetime, timedelta
from decimal import Decimal

from metrologia.models import (
    SolicitacaoCotacao, ItemSolicitacaoCotacao, CotacaoFornecedor,
    ItemCotacao, AtendimentoSolicitacao, Instrumento, ProcessoAutomatizacao,
    ItemSolicitacaoFaixa, HistoricoCalibracao, CustoAdicionalCotacao
)
from metrologia.services.comparativo_cotacoes import comparar_fornecedores, comparar_versoes
from metrologia.forms import (
    SolicitacaoCotacaoForm, ItemSolicitacaoCotacaoForm, CotacaoFornecedorForm,
    ItemCotacaoForm, AtendimentoSolicitacaoForm
)


# ==============================================================================
# ETAPA 1: SOLICITAÇÃO DE COTAÇÃO
# ==============================================================================

@login_required
def solicitacao_list(request):
    """Acompanhamento enxuto das cotações (criadas a partir das telas de calibração)."""
    qs = SolicitacaoCotacao.objects.select_related('responsavel').prefetch_related(
        'itens__instrumento', 'cotacoes_fornecedores__fornecedor', 'atendimentos'
    )

    cobranca = (request.GET.get('cobranca') or '').strip().lower()
    if cobranca == 'prazo_vencido':
        hoje = timezone.localdate()
        qs = qs.exclude(status__in=STATUS_COTACAO_ENCERRADA).filter(
            data_solicitacao_orcamento__isnull=False,
            data_solicitacao_orcamento__lte=hoje,
        )

    # Abas: em andamento (padrão) / encerradas / todas
    aba = (request.GET.get('aba') or 'abertas').lower()
    total_abertas = SolicitacaoCotacao.objects.exclude(status__in=STATUS_COTACAO_ENCERRADA).count()
    total_encerradas = SolicitacaoCotacao.objects.filter(status__in=STATUS_COTACAO_ENCERRADA).count()
    if aba == 'abertas':
        qs = qs.exclude(status__in=STATUS_COTACAO_ENCERRADA)
    elif aba == 'encerradas':
        qs = qs.filter(status__in=STATUS_COTACAO_ENCERRADA)

    status = request.GET.get('status')
    if status:
        qs = qs.filter(status=status)

    busca = (request.GET.get('q') or '').strip()
    if busca:
        qs = qs.filter(
            Q(numero__icontains=busca)
            | Q(itens__instrumento__tag__icontains=busca)
            | Q(itens__instrumento__descricao__icontains=busca)
            | Q(cotacoes_fornecedores__fornecedor__empresa__icontains=busca)
        ).distinct()

    context = {
        'solicitacoes': qs,
        'status_choices': SolicitacaoCotacao._meta.get_field('status').choices,
        'status': status,
        'cobranca': cobranca,
        'aba': aba,
        'busca': busca,
        'total_abertas': total_abertas,
        'total_encerradas': total_encerradas,
        'total_geral': total_abertas + total_encerradas,
    }
    return render(request, 'metrologia/novo_fluxo/solicitacao_list.html', context)


STATUS_COTACAO_ENCERRADA = ("CONCLUIDA", "CANCELADA")


def instrumentos_em_cotacao():
    """Mapa {instrumento_id: (solicitacao_id, numero)} dos instrumentos que
    possuem alguma solicitação de cotação em aberto (não concluída/cancelada)."""
    itens = (
        ItemSolicitacaoCotacao.objects
        .exclude(solicitacao__status__in=STATUS_COTACAO_ENCERRADA)
        .select_related("solicitacao")
        .order_by("solicitacao__data_criacao")
    )
    return {i.instrumento_id: (i.solicitacao_id, i.solicitacao.numero) for i in itens}


def contexto_cotacoes_abertas(acompanhamento_map=None):
    """Dados do filtro "Cotações em aberto" dos dashboards.

    Uma cotação (solicitação) só deixa de estar em aberto quando é concluída, e a
    conclusão exige etapas realizadas e certificados recebidos (ver
    SolicitacaoCotacao.pendencias_conclusao).
    Devolve:
      cotacao_aberta_map: {instrumento_id: numero}
      cotacoes_abertas:   [{numero, total}] (códigos ordenados)
    """
    mapa = {inst_id: numero for inst_id, (_sol_id, numero) in instrumentos_em_cotacao().items()}
    contagem = {}
    for numero in mapa.values():
        contagem[numero] = contagem.get(numero, 0) + 1
    return {
        'cotacao_aberta_map': mapa,
        'cotacoes_abertas': [{'numero': n, 'total': contagem[n]} for n in sorted(contagem)],
        # instrumentos ativos que não estão em nenhuma cotação em aberto (opção "Sem cotações")
        'sem_cotacao_total': Instrumento.objects.filter(ativo=True).exclude(id__in=list(mapa.keys())).count(),
        # instrumentos ativos fora de qualquer status de acompanhamento (opção "Sem acompanhamento")
        'sem_acompanhamento_total': Instrumento.objects.filter(ativo=True).exclude(
            id__in=list((acompanhamento_map if acompanhamento_map is not None else acompanhamento_instrumentos()).keys())
        ).count(),
    }


ACOMPANHAMENTO_LABELS = {
    'COM_COMPRAS': 'Com o setor de compras',
    'EM_COTACAO': 'Em cotação',
    'CALIBRACAO_PROGRAMADA': 'Calibração programada',
    'ENVIADO_FORNECEDOR': 'Enviado ao fornecedor',
    'AGUARDANDO_CERTIFICADO': 'Calibrado: aguardando certificado',
}


def acompanhamento_instrumentos():
    """Mapa {instrumento_id: {codigo, label, url?}} do acompanhamento de equipamentos.

    Um instrumento tem no máximo um status, por prioridade (mais avançado vence):
      3. ENVIADO_FORNECEDOR     - instrumento enviado ao fornecedor (data de envio) e ainda sem retorno
      4. AGUARDANDO_CERTIFICADO - histórico gerado na conclusão, sem dados do certificado
      2. CALIBRACAO_PROGRAMADA  - orçamento aprovado e calibração ainda não realizada
      1. COM_COMPRAS / EM_COTACAO - solicitação de cotação em aberto (com o setor de compras, até
                                    a chegada das propostas; depois, em cotação)
    """
    from django.urls import reverse
    resultado = {}

    com_compras = {
        s.id: s for s in SolicitacaoCotacao.objects
        .filter(compras_solicitada_em__isnull=False, compras_concluida_em__isnull=True)
        .exclude(status__in=STATUS_COTACAO_ENCERRADA)
    }
    for inst_id, (sol_id, numero) in instrumentos_em_cotacao().items():
        url = reverse('metrologia:solicitacao_detail', args=[sol_id])
        if sol_id in com_compras:
            desde = com_compras[sol_id].compras_solicitada_em
            resultado[inst_id] = {
                'codigo': 'COM_COMPRAS',
                'label': f'Com o setor de compras ({numero}, desde {desde:%d/%m/%Y})',
                'url': url,
            }
        else:
            resultado[inst_id] = {'codigo': 'EM_COTACAO', 'label': f'Em cotação ({numero})', 'url': url}

    # Orçamento aprovado e calibração ainda não realizada (sem histórico gerado,
    # sem NAO_ATENDIDO na execução e sem o instrumento desconsiderado no planejamento).
    programados = (
        ItemCotacao.objects
        .filter(
            cotacao_fornecedor__aprovada=True,
            cotacao_fornecedor__ativa=True,
            pode_atender=True,
            tipo_servico='CALIBRACAO',
        )
        .exclude(cotacao_fornecedor__status__in=('CANCELADA', 'REJEITADA'))
        .exclude(cotacao_fornecedor__solicitacao__status__in=STATUS_COTACAO_ENCERRADA)
        .exclude(status_execucao='NAO_ATENDIDO')
        .exclude(historicos_gerados__isnull=False)
        .exclude(atendimentos__historicos_calibracao__isnull=False)
        .exclude(atendimentos__desconsiderado=True)
        .select_related('cotacao_fornecedor')
    )
    for item in programados:
        cot = item.cotacao_fornecedor
        quando = f' ({cot.data_visita:%d/%m/%Y})' if cot.data_visita else ''
        resultado[item.instrumento_id] = {
            'codigo': 'CALIBRACAO_PROGRAMADA',
            'label': f'Calibração programada{quando}',
            'url': reverse('metrologia:cotacao_fornecedor_detail', args=[cot.id]),
        }

    # Enviado ao laboratório do fornecedor e ainda sem retorno
    enviados = (
        AtendimentoSolicitacao.objects
        .filter(data_envio__isnull=False, data_retorno__isnull=True, desconsiderado=False,
                item_cotacao__tipo_servico='CALIBRACAO')
        .exclude(solicitacao__status__in=STATUS_COTACAO_ENCERRADA)
        .exclude(historicos_calibracao__isnull=False)
        .exclude(item_cotacao__historicos_gerados__isnull=False)
        .select_related('item_solicitacao', 'item_cotacao__cotacao_fornecedor__fornecedor')
        .order_by('data_envio', 'id')
    )
    for a in enviados:
        previsto = f', retorno previsto {a.data_retorno_previsto:%d/%m/%Y}' if a.data_retorno_previsto else ''
        resultado[a.item_solicitacao.instrumento_id] = {
            'codigo': 'ENVIADO_FORNECEDOR',
            'label': f'Enviado ao fornecedor (desde {a.data_envio:%d/%m/%Y}{previsto})',
            'url': reverse('metrologia:solicitacao_detail', args=[a.solicitacao_id]),
        }

    from metrologia.models import HistoricoCalibracao
    pendentes = (
        HistoricoCalibracao.objects
        .filter(aguardando_certificado=True, instrumento__isnull=False)
        .order_by('data_calibracao', 'id')
    )
    for h in pendentes:
        resultado[h.instrumento_id] = {
            'codigo': 'AGUARDANDO_CERTIFICADO',
            'label': 'Calibrado: aguardando certificado',
            'url': reverse('editar_historico_calibracao', args=[h.id]),
        }
    return resultado


@login_required
@require_POST
def solicitacao_compras(request, pk):
    """Etapa "Solicitação das cotações ao setor de compras" (acao: solicitar|editar|encerrar|reabrir|desfazer)."""
    solicitacao = get_object_or_404(SolicitacaoCotacao, pk=pk)
    voltar = redirect('metrologia:solicitacao_detail', pk=solicitacao.id)
    if solicitacao.status in STATUS_COTACAO_ENCERRADA:
        messages.error(request, "Esta cotação está encerrada; reabra-a antes de alterar a etapa de compras.")
        return voltar

    acao = request.POST.get('acao', '')
    hoje = timezone.localdate()

    def _data(campo, padrao):
        bruto = (request.POST.get(campo) or '').strip()
        if not bruto:
            return padrao
        return datetime.strptime(bruto, '%Y-%m-%d').date()

    try:
        if acao in ('solicitar', 'editar'):
            if acao == 'editar' and not solicitacao.compras_solicitada_em:
                messages.error(request, "A cotação ainda não foi solicitada ao setor de compras.")
                return voltar
            data = _data('data_solicitada', solicitacao.compras_solicitada_em or hoje)
            if data > hoje:
                messages.error(request, "A data da solicitação não pode ser futura.")
                return voltar
            solicitacao.compras_solicitada_em = data
            solicitacao.compras_responsavel = (request.POST.get('responsavel') or '').strip()[:150]
            solicitacao.compras_observacoes = (request.POST.get('observacoes') or '').strip()
            if acao == 'solicitar':
                solicitacao.compras_solicitada_por = request.user
                solicitacao.compras_concluida_em = None
            msg = "Demanda enviada ao setor de compras." if acao == 'solicitar' else "Dados da solicitação atualizados."
        elif acao == 'encerrar':
            if not solicitacao.compras_solicitada_em:
                messages.error(request, "A cotação ainda não foi solicitada ao setor de compras.")
                return voltar
            fim = _data('data_encerrada', hoje)
            if fim < solicitacao.compras_solicitada_em:
                messages.error(request, "O encerramento não pode ser anterior à solicitação.")
                return voltar
            solicitacao.compras_concluida_em = fim
            msg = "Etapa de compras encerrada."
        elif acao == 'reabrir':
            solicitacao.compras_concluida_em = None
            msg = "Etapa de compras reaberta: a demanda voltou ao setor de compras."
        elif acao == 'desfazer':
            solicitacao.compras_solicitada_em = None
            solicitacao.compras_solicitada_por = None
            solicitacao.compras_responsavel = ''
            solicitacao.compras_observacoes = ''
            solicitacao.compras_concluida_em = None
            msg = "Solicitação ao setor de compras desfeita."
        else:
            messages.error(request, "Ação inválida.")
            return voltar
    except ValueError:
        messages.error(request, "Data inválida.")
        return voltar

    solicitacao.save()          # recalcula o status (Com o Setor de Compras / etc.)
    messages.success(request, msg)
    return voltar


@login_required
@require_POST
def solicitacao_compras_link(request, pk):
    """Adiciona (um ou mais, um por linha) ou remove links das tratativas com o setor de compras."""
    from django.core.exceptions import ValidationError
    from django.core.validators import URLValidator
    from metrologia.models import LinkSolicitacaoCompras

    solicitacao = get_object_or_404(SolicitacaoCotacao, pk=pk)
    voltar = redirect('metrologia:solicitacao_detail', pk=solicitacao.id)
    acao = request.POST.get('acao', '')

    if acao == 'remover':
        link = solicitacao.links_compras.filter(pk=request.POST.get('link_id') or 0).first()
        if link:
            link.delete()
            messages.success(request, "Link removido.")
        return voltar

    if acao != 'adicionar':
        messages.error(request, "Ação inválida.")
        return voltar

    validador = URLValidator(schemes=['http', 'https'])
    linhas = [l.strip() for l in (request.POST.get('urls') or '').splitlines() if l.strip()]
    descricao = (request.POST.get('descricao') or '').strip()[:150] if len(linhas) == 1 else ''
    if not linhas:
        messages.error(request, "Informe o link.")
        return voltar

    criados, invalidos = 0, []
    existentes = set(solicitacao.links_compras.values_list('url', flat=True))
    for bruto in linhas:
        url = bruto if '://' in bruto else 'https://' + bruto
        try:
            validador(url)
        except ValidationError:
            invalidos.append(bruto)
            continue
        if len(url) > 500 or url in existentes:
            if len(url) > 500:
                invalidos.append(bruto[:60] + '...')
            continue
        LinkSolicitacaoCompras.objects.create(
            solicitacao=solicitacao, url=url, descricao=descricao, criado_por=request.user)
        existentes.add(url)
        criados += 1

    if criados:
        messages.success(request, f"{criados} link(s) adicionado(s).")
    if invalidos:
        messages.error(request, "Link inválido: " + ", ".join(invalidos))
    return voltar


@login_required
def solicitacao_create(request):
    """Cria uma solicitação de cotação já com os instrumentos selecionados.

    - POST ``instrumentos_ids`` (lista separada por vírgula ou múltiplos campos)
    - GET ``instrumento_id`` (atalho do botão "Cotar" de uma linha)
    As cotações são conduzidas a partir das telas de calibração; sem instrumentos
    o usuário é devolvido à tela de instrumentos.
    """
    ids = []
    if request.method == 'POST':
        for raw in request.POST.getlist('instrumentos_ids'):
            ids.extend(p.strip() for p in raw.split(',') if p.strip())
    elif request.GET.get('instrumento_id'):
        ids = [request.GET['instrumento_id']]
    ids = [int(i) for i in dict.fromkeys(ids) if str(i).isdigit()]

    if not ids:
        messages.info(request, "Selecione os instrumentos na tela de calibrações e clique em Cotar.")
        return redirect('modulo_metrologia')

    instrumentos = list(Instrumento.objects.filter(id__in=ids).order_by('tag'))
    ja_em_cotacao = instrumentos_em_cotacao()
    novos = [i for i in instrumentos if i.id not in ja_em_cotacao]
    repetidos = [i for i in instrumentos if i.id in ja_em_cotacao]

    if repetidos:
        tags = ", ".join(i.tag for i in repetidos)
        messages.warning(request, f"Já em cotação (ignorados): {tags}.")
    if not novos:
        # Leva ao acompanhamento da cotação já aberta do primeiro instrumento
        sol_id = ja_em_cotacao[repetidos[0].id][0] if repetidos else None
        if sol_id:
            return redirect('metrologia:solicitacao_detail', pk=sol_id)
        return redirect('modulo_metrologia')

    try:
        with transaction.atomic():
            solicitacao = SolicitacaoCotacao.objects.create(
                responsavel=request.user,
                dias_vencimento=30,
                data_solicitacao_orcamento=timezone.localdate(),
            )
            for inst in novos:
                ItemSolicitacaoCotacao.objects.create(solicitacao=solicitacao, instrumento=inst)
            solicitacao.atualizar_status_automatico()
        messages.success(
            request,
            f"Cotação {solicitacao.numero} criada com {len(novos)} instrumento(s). "
            "Registre abaixo as propostas dos fornecedores."
        )
        return redirect('metrologia:solicitacao_detail', pk=solicitacao.id)
    except Exception as e:
        messages.error(request, f"Erro ao criar cotação: {str(e)}")
        return redirect('modulo_metrologia')


@login_required
def solicitacao_detail(request, pk):
    """Detalha uma solicitação e permite gerenciar itens - ETAPA 1"""
    solicitacao = get_object_or_404(SolicitacaoCotacao, pk=pk)
    itens = solicitacao.itens.all()
    cotacoes = solicitacao.cotacoes_fornecedores.filter(ativa=True).prefetch_related('itens')
    cotacoes_obsoletas = solicitacao.cotacoes_fornecedores.filter(ativa=False).select_related(
        'fornecedor', 'inativada_por').prefetch_related('versoes_novas').order_by('-inativada_em')
    atendimentos = solicitacao.atendimentos.select_related(
        'item_cotacao__cotacao_fornecedor__fornecedor', 'item_solicitacao__instrumento'
    ).order_by(
        'item_cotacao__local_atendimento', 'item_cotacao__cotacao_fornecedor_id',
        'desconsiderado', 'item_solicitacao__instrumento__tag',
    )
    from django.contrib.auth.models import User
    usuarios_responsaveis = User.objects.filter(is_active=True).select_related(
        'colaborador', 'colaborador__setor'
    ).order_by('first_name', 'username')

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
        'cotacoes_obsoletas': cotacoes_obsoletas,
        'fornecedores_com_ativa': set(cotacoes.values_list('fornecedor_id', flat=True)),
        'comparativo': comparar_fornecedores(solicitacao),
        'atendimentos': atendimentos,
        'historicos_pendentes': {
            h.item_cotacao_id: h for h in HistoricoCalibracao.objects.filter(
                aguardando_certificado=True, item_cotacao__cotacao_fornecedor__solicitacao=solicitacao)
        },
        # último histórico de cada item (qualquer origem): base do botão "Associar certificado"
        'historicos_por_item': _ultimo_historico_por_item(solicitacao),
        'usuarios_responsaveis': usuarios_responsaveis,
        'locais_atendimento': {a.item_cotacao.local_atendimento for a in atendimentos},
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
        try:
            item.delete()
        except ProtectedError as exc:
            n_cotacoes = sum(1 for o in exc.protected_objects if isinstance(o, ItemCotacao))
            n_atend = sum(1 for o in exc.protected_objects if isinstance(o, AtendimentoSolicitacao))
            partes = []
            if n_cotacoes:
                partes.append(f"{n_cotacoes} item(ns) de cotação")
            if n_atend:
                partes.append(f"{n_atend} atendimento(s)")
            detalhe = " e ".join(partes) or "registros vinculados"
            messages.error(
                request,
                f"Instrumento {instrumento_tag} não pode ser removido da solicitação: "
                f"já possui {detalhe}. Para preservar o histórico, ele permanece na solicitação."
            )
            return redirect('metrologia:solicitacao_detail', pk=solicitacao_id)
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
        if form.is_valid() and solicitacao.cotacoes_fornecedores.filter(
                ativa=True, fornecedor=form.cleaned_data['fornecedor']).exists():
            form.add_error('fornecedor', "Já existe uma cotação ativa deste fornecedor nesta solicitação. "
                                         "Edite-a ou inative-a (obsoleta) para criar uma nova versão.")
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


def _restaurar_cotacao_obsoleta(cotacao):
    """Reativa uma cotação obsoleta (a aprovação volta se ela estava aceita)."""
    cotacao.ativa = True
    cotacao.inativada_em = None
    cotacao.inativada_por = None
    cotacao.motivo_inativacao = ''
    cotacao.aprovada = cotacao.status == 'ACEITA'
    cotacao.save()


def _copiar_para_nova_versao(cotacao, usuario):
    """Nova cotação do mesmo fornecedor com os dados da obsoleta, para atualizar os valores."""
    nova = CotacaoFornecedor.objects.create(
        solicitacao=cotacao.solicitacao, fornecedor=cotacao.fornecedor, versao_anterior=cotacao,
        data_solicitacao=timezone.localdate(), criado_por=usuario, status='RASCUNHO',
        observacoes=f"Nova versão de {cotacao.numero} (obsoleta). Atualize os valores.")
    for item in cotacao.itens.all():
        ItemCotacao.objects.create(
            cotacao_fornecedor=nova, item_solicitacao=item.item_solicitacao, instrumento=item.instrumento,
            pode_atender=item.pode_atender, tipo_servico=item.tipo_servico, local_atendimento=item.local_atendimento,
            valor_unitario=item.valor_unitario, quantidade=item.quantidade, prazo_dias=item.prazo_dias,
            descricao_servico=item.descricao_servico)
    for custo in cotacao.custos_adicionais.all():
        CustoAdicionalCotacao.objects.create(
            cotacao_fornecedor=nova, tipo=custo.tipo, descricao=custo.descricao,
            quantidade=custo.quantidade, valor_unitario=custo.valor_unitario)
    return nova


@login_required
@require_POST
def cotacao_fornecedor_ativacao(request, pk):
    """Inativa a cotação (obsoleta), opcionalmente criando a nova versão; ou a reativa."""
    cotacao = get_object_or_404(CotacaoFornecedor, pk=pk)
    solicitacao = cotacao.solicitacao
    voltar = redirect('metrologia:solicitacao_detail', pk=solicitacao.id)
    acao = request.POST.get('acao', '')

    if solicitacao.status in STATUS_COTACAO_ENCERRADA:
        messages.error(request, "A cotação está encerrada; reabra-a antes de alterar as propostas.")
        return voltar

    if acao in ('inativar', 'inativar_nova'):
        if not cotacao.ativa:
            messages.warning(request, f"{cotacao.numero} já está inativa.")
            return voltar
        motivo = (request.POST.get('motivo') or '').strip()[:255]
        if not motivo:
            messages.error(request, "Informe o motivo para inativar a cotação (ex.: valores desatualizados).")
            return voltar
        if cotacao.atendimentos_vinculados().exists():
            messages.error(request, f"{cotacao.numero} já tem instrumentos planejados. "
                                    "Desconsidere ou remova esses atendimentos antes de inativá-la.")
            return voltar
        with transaction.atomic():
            cotacao.ativa = False
            cotacao.aprovada = False
            cotacao.inativada_em = timezone.now()
            cotacao.inativada_por = request.user
            cotacao.motivo_inativacao = motivo
            cotacao.save()
            criar_nova = acao == 'inativar_nova' or bool(request.POST.get('nova_versao'))
            nova = _copiar_para_nova_versao(cotacao, request.user) if criar_nova else None
        if nova:
            messages.success(request, f"{cotacao.numero} inativada. Atualize os valores da nova versão {nova.numero}: "
                                      "o sistema vai comparar com a anterior.")
            return redirect('metrologia:cotacao_fornecedor_update', pk=nova.id)
        messages.success(request, f"{cotacao.numero} inativada (obsoleta).")
        return voltar

    if acao == 'nova_versao':
        # cotação que já ficou obsoleta sem a cópia: cria agora a nova versão
        if cotacao.ativa:
            messages.warning(request, f"{cotacao.numero} está ativa; inative-a para criar uma nova versão.")
            return voltar
        if solicitacao.cotacoes_fornecedores.filter(ativa=True, fornecedor=cotacao.fornecedor).exists():
            messages.error(request, "Este fornecedor já tem uma cotação ativa na solicitação.")
            return voltar
        nova = _copiar_para_nova_versao(cotacao, request.user)
        messages.success(request, f"Nova versão {nova.numero} criada a partir de {cotacao.numero}. "
                                  "Atualize os valores: o sistema vai comparar com a anterior.")
        return redirect('metrologia:cotacao_fornecedor_update', pk=nova.id)

    if acao == 'reativar':
        if cotacao.ativa:
            return voltar
        if solicitacao.cotacoes_fornecedores.filter(ativa=True, fornecedor=cotacao.fornecedor).exists():
            messages.error(request, "Este fornecedor já tem uma cotação ativa na solicitação; "
                                    "inative-a antes de reativar esta.")
            return voltar
        _restaurar_cotacao_obsoleta(cotacao)
        messages.success(request, f"{cotacao.numero} reativada.")
        return voltar

    if acao == 'desfazer_versao':
        # descarta a nova versão e volta para a cotação obsoleta que ela substituiu
        anterior = cotacao.versao_anterior
        if not anterior or not cotacao.ativa:
            messages.error(request, "Só dá para desfazer uma nova versão ativa que substitui outra cotação.")
            return voltar
        if cotacao.atendimentos_vinculados(incluir_desconsiderados=True).exists():
            messages.error(request, f"{cotacao.numero} já tem instrumentos planejados e não pode ser descartada.")
            return voltar
        numero_nova = cotacao.numero
        try:
            with transaction.atomic():
                cotacao.delete()                 # primeiro: libera a única-ativa do fornecedor
                _restaurar_cotacao_obsoleta(anterior)
        except Exception:
            messages.error(request, "Não foi possível desfazer a nova versão (há registros ligados a ela).")
            return voltar
        solicitacao.atualizar_status_automatico()
        messages.success(request, f"Nova versão {numero_nova} descartada. {anterior.numero} voltou a ser a cotação ativa.")
        return voltar

    messages.error(request, "Ação inválida.")
    return voltar


def _salvar_custos_adicionais(request, cotacao):
    """Substitui os custos adicionais pelos enviados no formulário (linhas vazias são ignoradas)."""
    from metrologia.models import CustoAdicionalCotacao
    tipos = request.POST.getlist('custo_tipo')
    descricoes = request.POST.getlist('custo_descricao')
    quantidades = request.POST.getlist('custo_quantidade')
    valores = request.POST.getlist('custo_valor')
    validos = dict(CustoAdicionalCotacao.TIPO_CHOICES)
    novos, ignorados = [], 0
    for i, bruto in enumerate(valores):
        valor_txt = (bruto or '').strip().replace(',', '.')
        descricao = (descricoes[i] if i < len(descricoes) else '').strip()[:150]
        if not valor_txt and not descricao:
            continue                                   # linha em branco
        try:
            valor = Decimal(valor_txt)
            qtd = int((quantidades[i] if i < len(quantidades) else '1').strip() or '1')
            if valor < 0 or qtd < 1:
                raise ValueError
        except Exception:
            ignorados += 1
            continue
        tipo = tipos[i] if i < len(tipos) and tipos[i] in validos else 'OUTRO'
        novos.append(CustoAdicionalCotacao(
            cotacao_fornecedor=cotacao, tipo=tipo, descricao=descricao, quantidade=qtd, valor_unitario=valor))
    cotacao.custos_adicionais.all().delete()
    for c in novos:
        c.save()
    if ignorados:
        messages.warning(request, f"{ignorados} custo(s) adicional(is) com valor/quantidade inválidos foram ignorados.")
    return len(novos)


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
            
            # Processar os itens só se a tabela de instrumentos foi enviada (senão o 'Pode atender?'
            # de todos os itens seria zerado ao salvar apenas os dados gerais)
            if request.POST.get('itens_enviados'):
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
            
            if request.POST.get('custos_enviados'):
                _salvar_custos_adicionais(request, cotacao)

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
        'mode': 'edit',
        'custos': list(cotacao.custos_adicionais.all()),
        'tipos_custo': CustoAdicionalCotacao.TIPO_CHOICES,
    }
    return render(request, 'metrologia/novo_fluxo/cotacao_fornecedor_form.html', context)


@login_required
def cotacao_fornecedor_detail(request, pk):
    """Detalha uma cotação de fornecedor - ETAPA 2"""
    cotacao = get_object_or_404(CotacaoFornecedor, pk=pk)
    itens = cotacao.itens.select_related('instrumento', 'item_solicitacao')
    
    # Valor total = serviços + custos adicionais
    valor_servicos = sum(item.valor_total for item in itens)
    custos_adicionais = list(cotacao.custos_adicionais.all())
    valor_custos = sum((c.valor_total for c in custos_adicionais), Decimal('0.00'))
    valor_total = valor_servicos + valor_custos

    from qms.models import OcorrenciaInstrumento
    em_execucao = cotacao.etapa_servico == 'EXECUCAO'
    context = {
        'cotacao': cotacao,
        'itens': itens,
        'valor_total': valor_total,
        'valor_servicos': valor_servicos,
        'valor_custos': valor_custos,
        'custos_adicionais': custos_adicionais,
        'valor_a_pagar': cotacao.get_valor_a_pagar(),
        'comparativo_versao': comparar_versoes(cotacao, cotacao.versao_anterior) if cotacao.versao_anterior_id else None,
        'versao_nova': cotacao.versoes_novas.filter(ativa=True).first(),
        'pode_nova_versao': (not cotacao.ativa
                             and cotacao.solicitacao.status not in STATUS_COTACAO_ENCERRADA
                             and not cotacao.solicitacao.cotacoes_fornecedores.filter(
                                 ativa=True, fornecedor=cotacao.fornecedor).exists()),
        'execucao_registrada': any(i.status_execucao != 'PENDENTE' for i in itens),
        'tipos_ocorrencia': OcorrenciaInstrumento.TIPO_OCORRENCIA,
        'itens_pendentes': sum(1 for i in itens if i.status_execucao == 'PENDENTE'),
        'relatorio_previa': gerar_relatorio_conclusao(cotacao) if em_execucao else '',
        'historicos_gerados': list(
            HistoricoCalibracao.objects.filter(item_cotacao__cotacao_fornecedor=cotacao)
            .select_related('instrumento')
        ),
    }
    return render(request, 'metrologia/novo_fluxo/cotacao_fornecedor_detail.html', context)


# ==============================================================================
# EXECUÇÃO DO SERVIÇO COTADO: PLANEJAMENTO -> EXECUÇÃO -> CONCLUSÃO
# ==============================================================================

def _fmt_brl(valor):
    """Formata Decimal como R$ 1.234,56."""
    texto = f"{Decimal(valor):,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_relatorio_conclusao(cotacao):
    """
    Monta o relatório de conclusão a partir dos dados das etapas anteriores
    (visita planejada, instrumentos atendidos, valores praticados e ocorrências).
    """
    from django.utils import timezone as tz
    itens = list(cotacao.itens.select_related('instrumento', 'ocorrencia'))
    atendidos = [i for i in itens if i.status_execucao == 'ATENDIDO']
    nao_atendidos = [i for i in itens if i.status_execucao == 'NAO_ATENDIDO']
    pendentes = [i for i in itens if i.status_execucao == 'PENDENTE']

    def _dt(v):
        return tz.localtime(v).strftime('%d/%m/%Y %H:%M') if v else '-'

    linhas = [
        f"RELATÓRIO DE CONCLUSÃO - {cotacao.numero}",
        f"Fornecedor: {cotacao.fornecedor.empresa}",
        "",
        "1. PLANEJAMENTO",
        f"Visita agendada para: {_dt(cotacao.data_visita)}",
        "",
        "2. EXECUÇÃO",
        f"Início da execução: {_dt(cotacao.data_inicio_execucao)}",
        f"Instrumentos cotados: {len(itens)} | Atendidos: {len(atendidos)} | "
        f"Não atendidos: {len(nao_atendidos)} | Pendentes: {len(pendentes)}",
        "",
    ]
    if atendidos:
        linhas.append("Instrumentos atendidos:")
        for i in atendidos:
            extra = ""
            if i.valor_cobrado != i.valor_total:
                extra = f" (cotado {_fmt_brl(i.valor_total)})"
            linhas.append(f"- {i.instrumento.tag}: {_fmt_brl(i.valor_cobrado)}{extra}")
            if i.tipo_servico == 'CALIBRACAO' and cotacao.etapa_servico == 'CONCLUIDO':
                linhas.append("    Histórico de calibração gerado - PENDENTE: dados do certificado")
            if i.observacao_execucao:
                linhas.append(f"    Obs.: {i.observacao_execucao}")
        linhas.append("")
    if nao_atendidos:
        linhas.append("Instrumentos NÃO atendidos:")
        for i in nao_atendidos:
            linhas.append(f"- {i.instrumento.tag}" + (f": {i.observacao_execucao}" if i.observacao_execucao else ""))
        linhas.append("")
    com_oc = [i for i in itens if i.ocorrencia_id]
    if com_oc:
        linhas.append("Ocorrências abertas:")
        for i in com_oc:
            oc = i.ocorrencia
            linhas.append(f"- {i.instrumento.tag}: #{oc.pk} {oc.get_tipo_display()} - {oc.descricao}")
        linhas.append("")
    custos = list(cotacao.custos_adicionais.all())
    if custos:
        linhas.append("Custos adicionais:")
        for c in custos:
            rotulo = c.get_tipo_display() + (f" - {c.descricao}" if c.descricao else "")
            linhas.append(f"- {rotulo}: {c.quantidade} x {_fmt_brl(c.valor_unitario)} = {_fmt_brl(c.valor_total)}")
        linhas.append("")
    linhas += [
        "3. CONCLUSÃO",
        f"Valor cotado (serviços + custos adicionais): {_fmt_brl(cotacao.get_valor_total())}",
        f"Valor a pagar (conforme praticado): {_fmt_brl(cotacao.get_valor_a_pagar())}",
    ]
    return "\n".join(linhas)


def registrar_historico_item(item, data_calibracao, atendimento=None, origem=''):
    """
    Cria o HistoricoCalibracao de uma calibração externa realizada, marcado como
    "aguardando certificado" (número, arquivo/link e resultado pendentes).
    Idempotente por item da cotação: devolve None se já existe histórico dele
    (gerado na conclusão do serviço ou a partir do planejamento de atendimentos).
    """
    from metrologia.models import HistoricoCalibracao
    if item.tipo_servico != 'CALIBRACAO':
        return None
    if item.historicos_gerados.exists() or HistoricoCalibracao.objects.filter(atendimento__item_cotacao=item).exists():
        return None
    cotacao = item.cotacao_fornecedor
    return HistoricoCalibracao.objects.create(
        instrumento=item.instrumento,
        item_cotacao=item,
        atendimento=atendimento,
        data_calibracao=data_calibracao,
        tipo_calibracao='EXTERNA',
        fornecedor=cotacao.fornecedor.empresa,
        aguardando_certificado=True,
        observacoes=(
            f"Gerado {origem or 'a partir da cotação'} {cotacao.numero}. "
            "PENDENTE: informar número, arquivo/link do certificado e resultado da calibração."
        ),
    )


def gerar_historicos_calibracao(cotacao):
    """Na conclusão do serviço: um histórico por calibração atendida (idempotente por item)."""
    hoje = timezone.localdate()
    data_cal = hoje
    if cotacao.data_visita:
        data_cal = min(timezone.localtime(cotacao.data_visita).date(), hoje)
    criados = []
    itens = cotacao.itens.filter(status_execucao='ATENDIDO', tipo_servico='CALIBRACAO').select_related(
        'instrumento', 'cotacao_fornecedor__fornecedor')
    for item in itens:
        h = registrar_historico_item(item, data_cal, origem='na conclusão do serviço da cotação')
        if h:
            criados.append(h)
    return criados


def _ultimo_historico_por_item(solicitacao):
    """{item_cotacao_id: HistoricoCalibracao mais recente} da solicitação."""
    from django.db.models import Q
    qs = (HistoricoCalibracao.objects
          .filter(Q(item_cotacao__cotacao_fornecedor__solicitacao=solicitacao)
                  | Q(atendimento__solicitacao=solicitacao))
          .select_related('atendimento')
          .order_by('data_calibracao', 'id'))  # o mais recente sobrescreve
    mapa = {}
    for h in qs:
        item_id = h.item_cotacao_id or (h.atendimento.item_cotacao_id if h.atendimento_id else None)
        if item_id:
            mapa[item_id] = h
    return mapa


def _redirect_cotacao(cotacao):
    return redirect('metrologia:cotacao_fornecedor_detail', pk=cotacao.id)


@login_required
@require_POST
def cotacao_servico_agendar(request, pk):
    """PLANEJAMENTO: define data/hora da visita; 'iniciar' avança para a Execução."""
    cotacao = get_object_or_404(CotacaoFornecedor, pk=pk)
    if not cotacao.aprovada:
        messages.error(request, "Apenas cotações aceitas podem ser agendadas.")
        return _redirect_cotacao(cotacao)
    if cotacao.etapa_servico == 'CONCLUIDO':
        messages.error(request, "Serviço já concluído.")
        return _redirect_cotacao(cotacao)

    raw = (request.POST.get('data_visita') or '').strip()
    if raw:
        try:
            dt = datetime.strptime(raw, '%Y-%m-%dT%H:%M')
        except ValueError:
            messages.error(request, "Data/hora da visita inválida.")
            return _redirect_cotacao(cotacao)
        cotacao.data_visita = timezone.make_aware(dt) if timezone.is_naive(dt) else dt

    if not cotacao.data_visita:
        messages.error(request, "Informe a data e hora da visita.")
        return _redirect_cotacao(cotacao)

    if request.POST.get('acao') == 'iniciar' and cotacao.etapa_servico == 'AGENDAMENTO':
        cotacao.etapa_servico = 'EXECUCAO'
        cotacao.data_inicio_execucao = timezone.now()
        messages.success(request, "Execução iniciada. Confirme os instrumentos atendidos.")
    else:
        messages.success(request, "Visita agendada.")
    cotacao.save()
    return _redirect_cotacao(cotacao)


@login_required
@require_POST
def cotacao_servico_executar(request, pk):
    """EXECUÇÃO: confirma instrumentos atendidos, valores praticados e abre ocorrências."""
    from qms.models import OcorrenciaInstrumento
    from shared.inbox import invalidar_cache_inbox

    cotacao = get_object_or_404(CotacaoFornecedor, pk=pk)
    if cotacao.etapa_servico != 'EXECUCAO':
        messages.error(request, "A cotação não está na etapa de execução.")
        return _redirect_cotacao(cotacao)

    ocorrencias_abertas = 0
    with transaction.atomic():
        for item in cotacao.itens.select_related('instrumento'):
            status = request.POST.get(f'status_{item.id}', 'PENDENTE')
            if status not in ('PENDENTE', 'ATENDIDO', 'NAO_ATENDIDO'):
                status = 'PENDENTE'
            item.status_execucao = status
            item.observacao_execucao = (request.POST.get(f'obs_{item.id}') or '').strip()

            valor_raw = (request.POST.get(f'valor_{item.id}') or '').strip().replace(',', '.')
            item.valor_praticado = None
            if valor_raw and status == 'ATENDIDO':
                try:
                    valor = Decimal(valor_raw)
                    if valor >= 0:
                        item.valor_praticado = valor
                except Exception:
                    messages.warning(request, f"Valor inválido para {item.instrumento.tag}; mantido o cotado.")

            if request.POST.get(f'ocorrencia_{item.id}') and not item.ocorrencia_id:
                tipo = request.POST.get(f'ocorrencia_tipo_{item.id}') or 'OUTRO'
                if tipo not in dict(OcorrenciaInstrumento.TIPO_OCORRENCIA):
                    tipo = 'OUTRO'
                descricao = (request.POST.get(f'ocorrencia_desc_{item.id}') or '').strip()
                if not descricao:
                    messages.warning(request, f"Ocorrência de {item.instrumento.tag} não aberta: descreva o problema.")
                else:
                    item.ocorrencia = OcorrenciaInstrumento.objects.create(
                        instrumento=item.instrumento,
                        tipo=tipo,
                        descricao=f"[{cotacao.numero}] {descricao}",
                        data_ocorrencia=timezone.localdate(),
                        usuario_responsavel=request.user,
                        status='ABERTA',
                    )
                    ocorrencias_abertas += 1
            item.save()

    invalidar_cache_inbox(request.user)
    msg = "Execução salva."
    if ocorrencias_abertas:
        msg += f" {ocorrencias_abertas} ocorrência(s) aberta(s)."
    messages.success(request, msg)
    return _redirect_cotacao(cotacao)


@login_required
@require_POST
def cotacao_servico_concluir(request, pk):
    """CONCLUSÃO: finaliza o serviço e grava o relatório gerado das etapas anteriores."""
    cotacao = get_object_or_404(CotacaoFornecedor, pk=pk)
    acao = request.POST.get('acao', 'concluir')

    if acao == 'reabrir':
        if cotacao.itens.filter(historicos_gerados__isnull=False).exists():
            messages.error(request, "O serviço já gerou históricos de calibração; ajuste-os pelo histórico do instrumento.")
            return _redirect_cotacao(cotacao)
        if cotacao.etapa_servico == 'CONCLUIDO':
            cotacao.etapa_servico = 'EXECUCAO'
            cotacao.data_conclusao_servico = None
            cotacao.concluido_por = None
            cotacao.save()
            messages.success(request, "Serviço reaberto para execução.")
        return _redirect_cotacao(cotacao)

    if cotacao.etapa_servico != 'EXECUCAO':
        messages.error(request, "A cotação não está na etapa de execução.")
        return _redirect_cotacao(cotacao)
    if cotacao.itens.filter(status_execucao='PENDENTE').exists():
        messages.error(request, "Confirme todos os instrumentos (atendido ou não) antes de concluir.")
        return _redirect_cotacao(cotacao)

    with transaction.atomic():
        cotacao.observacoes_conclusao = (request.POST.get('observacoes_conclusao') or '').strip()
        cotacao.etapa_servico = 'CONCLUIDO'
        cotacao.data_conclusao_servico = timezone.now()
        cotacao.concluido_por = request.user
        historicos = gerar_historicos_calibracao(cotacao)
        cotacao.relatorio_conclusao = gerar_relatorio_conclusao(cotacao)
        cotacao.save()
    msg = "Serviço concluído e relatório gerado."
    if historicos:
        msg += f" {len(historicos)} histórico(s) de calibração criado(s): preencha os dados dos certificados."
    messages.success(request, msg)
    return _redirect_cotacao(cotacao)





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
            cotacao_fornecedor__ativa=True,
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
    
    # Apenas cotações aprovadas (e ativas) podem gerar atendimentos
    if not cotacao.aprovada or not cotacao.ativa:
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


def _data_ou_none(valor):
    """'' / None -> None; 'YYYY-MM-DD' -> date. Levanta ValueError se inválida."""
    valor = (valor or '').strip() if isinstance(valor, str) else valor
    if not valor:
        return None
    return datetime.strptime(valor, '%Y-%m-%d').date()


@login_required
@require_http_methods(['POST'])
def atendimento_atualizar_dados(request):
    """Salva em lote os dados de um agrupamento (cotação) de atendimentos.

    Payload novo (um conjunto de campos por agrupamento, aplicado a todos os itens ativos):
      {tipo, cotacao_id, atendimentos: [ids],
       grupo: {data_realizada, tecnico, tecnico_telefone,            # NO_LOCAL
               data_envio, data_retorno_previsto, data_retorno,      # NO_LABORATORIO
               data_chegada,                                         # COMPRAR_NOVO
               observacoes}}
    Itens desconsiderados nunca são alterados. Formato antigo ({campos: {id: {...}}}) segue aceito.
    """
    import json

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError as e:
        return JsonResponse({'success': False, 'error': f'Erro ao processar JSON: {e}'}, status=400)

    tipo = data.get('tipo')
    if tipo not in ('NO_LOCAL', 'NO_LABORATORIO', 'COMPRAR_NOVO'):
        return JsonResponse({'success': False, 'error': 'Tipo de atendimento inválido.'}, status=400)

    # Normaliza os dois formatos para {atendimento_id: valores}
    por_atendimento = {}
    if 'grupo' in data:
        grupo = data.get('grupo') or {}
        for aid in data.get('atendimentos', []):
            por_atendimento[aid] = grupo
    else:
        por_atendimento = data.get('campos', {}) or {}

    try:
        atualizados = 0
        historicos_criados = 0
        solicitacao_ids = set()
        with transaction.atomic():
            for atendimento_id_str, valores in por_atendimento.items():
                try:
                    atendimento = AtendimentoSolicitacao.objects.get(id=int(atendimento_id_str))
                except (ValueError, TypeError, AtendimentoSolicitacao.DoesNotExist):
                    continue
                if atendimento.desconsiderado:
                    continue
                solicitacao_ids.add(atendimento.solicitacao_id)

                if tipo == 'NO_LOCAL':
                    if 'data_realizada' in valores:
                        atendimento.data_realizada = _data_ou_none(valores.get('data_realizada'))
                    if 'tecnico' in valores:
                        atendimento.tecnico_responsavel = (valores.get('tecnico') or '').strip()
                    if 'tecnico_telefone' in valores:
                        atendimento.tecnico_telefone = (valores.get('tecnico_telefone') or '').strip()
                elif tipo == 'NO_LABORATORIO':
                    for campo in ('data_envio', 'data_retorno_previsto', 'data_retorno'):
                        if campo in valores:
                            setattr(atendimento, campo, _data_ou_none(valores.get(campo)))
                elif tipo == 'COMPRAR_NOVO':
                    chegada = valores.get('data_chegada', valores.get('data_chegada_realizada'))
                    if chegada is not None:
                        atendimento.data_chegada = _data_ou_none(chegada)
                if 'observacoes' in valores:
                    atendimento.observacoes = (valores.get('observacoes') or '').strip()
                atendimento.save()
                atualizados += 1

                # Calibração realizada (no local: data realizada; no laboratório: retorno)
                # já entra no histórico, aguardando os dados do certificado.
                data_cal = atendimento.data_realizada if tipo == 'NO_LOCAL' else (
                    atendimento.data_retorno if tipo == 'NO_LABORATORIO' else None)
                if data_cal:
                    h = registrar_historico_item(
                        atendimento.item_cotacao, data_cal, atendimento=atendimento,
                        origem='no planejamento de atendimentos da cotação')
                    if h:
                        historicos_criados += 1

            for solicitacao in SolicitacaoCotacao.objects.filter(id__in=solicitacao_ids):
                solicitacao.atualizar_status_automatico()

        mensagem = f'{atualizados} atendimento(s) atualizado(s)'
        if historicos_criados:
            mensagem += (f'; {historicos_criados} registro(s) de calibração criado(s) '
                         '(Calibrado: aguardando certificado)')
            messages.success(request, mensagem + '. Preencha os dados dos certificados.')
        return JsonResponse({
            'success': True,
            'message': mensagem,
            'atualizados': atualizados,
            'historicos_criados': historicos_criados,
        })
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Data inválida (use o formato AAAA-MM-DD).'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


def _abrir_ocorrencia_desconsiderar(atendimento, usuario):
    """Registra a justificativa como ocorrência do instrumento (uma aberta por atendimento)."""
    from qms.models import OcorrenciaInstrumento
    from shared.inbox import invalidar_cache_inbox
    atual = atendimento.ocorrencia_desconsiderar
    descricao = _descricao_ocorrencia_desconsiderar(atendimento, atendimento.justificativa_desconsiderar)
    if atual and atual.status == 'ABERTA':
        atual.descricao = descricao
        atual.save(update_fields=['descricao'])
        return atual
    oc = OcorrenciaInstrumento.objects.create(
        instrumento=atendimento.item_solicitacao.instrumento,
        tipo='CALIBRACAO',
        descricao=descricao,
        data_ocorrencia=timezone.localdate(),
        usuario_responsavel=usuario,
        status='ABERTA',
    )
    atendimento.ocorrencia_desconsiderar = oc
    invalidar_cache_inbox(usuario)
    return oc


def _encerrar_ocorrencia_desconsiderar(atendimento, usuario):
    """Ao voltar a considerar o instrumento, encerra a ocorrência aberta pela justificativa."""
    from qms.models import OcorrenciaMensagem
    from shared.inbox import invalidar_cache_inbox
    oc = atendimento.ocorrencia_desconsiderar
    if oc and oc.status == 'ABERTA':
        oc.status = 'ENCERRADA'
        oc.data_encerramento = timezone.localdate()
        oc.save(update_fields=['status', 'data_encerramento'])
        OcorrenciaMensagem.objects.create(
            ocorrencia=oc, autor=usuario,
            texto='Instrumento voltou a ser considerado no planejamento; ocorrência encerrada automaticamente.')
        invalidar_cache_inbox(usuario)


def _descricao_ocorrencia_desconsiderar(atendimento, justificativa):
    cot = atendimento.item_cotacao.cotacao_fornecedor
    return (f"[{atendimento.solicitacao.numero} / {cot.numero}] "
            f"Instrumento desconsiderado no planejamento: {justificativa}")


@login_required
@require_POST
def atendimento_associar_certificado(request, pk):
    """Associa o certificado ao instrumento (N° e resultado) e conclui a calibração dele.

    Serve para o registro que aguarda o certificado e também para atendimentos já realizados
    (calibração no local realizada / retorno do laboratório) que ainda não têm registro.
    """
    from django.db.models import Q
    from metrologia.models import HistoricoCalibracao

    atendimento = get_object_or_404(
        AtendimentoSolicitacao.objects.select_related(
            'item_cotacao__instrumento', 'item_cotacao__cotacao_fornecedor__fornecedor', 'solicitacao'),
        pk=pk)
    voltar = redirect('metrologia:solicitacao_detail', pk=atendimento.solicitacao_id)
    item = atendimento.item_cotacao
    tag = item.instrumento.tag

    numero = (request.POST.get('numero_certificado') or '').strip()
    resultado = request.POST.get('resultado') or ''
    if item.tipo_servico != 'CALIBRACAO' or atendimento.desconsiderado:
        messages.error(request, f"{tag}: este atendimento não aceita certificado de calibração.")
        return voltar
    if not numero or numero.upper() == 'S/N':
        messages.error(request, f"{tag}: informe o N° do certificado.")
        return voltar
    if resultado not in dict(HistoricoCalibracao.RESULTADO_CHOICES):
        messages.error(request, f"{tag}: informe o resultado da calibração.")
        return voltar

    historico = (HistoricoCalibracao.objects
                 .filter(Q(item_cotacao=item) | Q(atendimento__item_cotacao=item))
                 .order_by('-data_calibracao', '-id').first())
    if historico is None:
        data_cal = atendimento.data_realizada or atendimento.data_retorno
        if not data_cal:
            messages.error(request, f"{tag}: registre a data de realização/retorno antes de associar o certificado.")
            return voltar
        historico = registrar_historico_item(
            item, data_cal, atendimento=atendimento, origem='ao associar o certificado da cotação')
    elif not historico.aguardando_certificado:
        messages.warning(request, f"{tag}: o certificado desta calibração já foi associado ({historico.numero_certificado}).")
        return voltar

    historico.numero_certificado = numero
    historico.resultado = resultado
    historico.aguardando_certificado = False
    historico.data_aprovacao = timezone.localdate()
    base = (historico.observacoes or '').split(' PENDENTE:')[0].strip()
    historico.observacoes = (
        f"{base} Certificado {numero} associado por {request.user.get_full_name() or request.user.username} "
        f"em {timezone.localdate():%d/%m/%Y}.").strip()
    historico.save()

    atendimento.status = 'CONCLUIDA'
    atendimento.save(update_fields=['status', 'atualizado_em'])
    atendimento.solicitacao.atualizar_status_automatico()
    messages.success(request, f"{tag}: certificado {numero} associado; calibração concluída.")
    return voltar


@login_required
@require_POST
def atendimento_desconsiderar(request, pk):
    """Desconsidera (com justificativa obrigatória) ou reativa um instrumento do planejamento."""
    atendimento = get_object_or_404(AtendimentoSolicitacao, pk=pk)
    voltar = redirect('metrologia:solicitacao_detail', pk=atendimento.solicitacao_id)

    if request.POST.get('desconsiderado') == '0':
        _encerrar_ocorrencia_desconsiderar(atendimento, request.user)
        atendimento.desconsiderado = False
        atendimento.desconsiderado_por = None
        atendimento.desconsiderado_em = None
        atendimento.save(update_fields=['desconsiderado', 'desconsiderado_por', 'desconsiderado_em', 'atualizado_em'])
        atendimento.solicitacao.atualizar_status_automatico()
        messages.success(request, f"Instrumento {atendimento.item_solicitacao.instrumento.tag} voltou a ser considerado.")
        return voltar

    justificativa = (request.POST.get('justificativa') or '').strip()
    if not justificativa:
        messages.error(request, "Informe a justificativa para desconsiderar o instrumento.")
        return voltar

    atendimento.desconsiderado = True
    atendimento.justificativa_desconsiderar = justificativa
    atendimento.desconsiderado_por = request.user
    atendimento.desconsiderado_em = timezone.now()
    _abrir_ocorrencia_desconsiderar(atendimento, request.user)
    atendimento.save(update_fields=[
        'desconsiderado', 'justificativa_desconsiderar', 'desconsiderado_por', 'desconsiderado_em',
        'ocorrencia_desconsiderar', 'atualizado_em',
    ])
    atendimento.solicitacao.atualizar_status_automatico()
    messages.success(request, f"Instrumento {atendimento.item_solicitacao.instrumento.tag} desconsiderado.")
    return voltar


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
    pendencias = solicitacao.pendencias_conclusao()
    if pendencias:
        return JsonResponse({
            'success': False,
            'error': 'A cotação só pode ser concluída com todas as etapas realizadas e os certificados recebidos.',
            'pendencias': pendencias,
        }, status=400)
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
