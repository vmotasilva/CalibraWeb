from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


def sincronizar_status_requisito(auditoria, item_norma):
    """
    Recalcula obrigatoriamente o status consolidado de um ItemNorma em uma AuditoriaIso,
    sincronizando em cascata as RespostaEntrevistaIso e a AvaliacaoFinalRequisitoIso.

    Regra:
    1. Para cada RespostaEntrevistaIso do requisito, recalcula a classificação baseada nas suas solicitações filhas.
    2. Se não houver mais nenhuma solicitação com conclusão 'NC', o requisito deixa de ser Não Conforme.
    3. Se havia AvaliacaoFinalRequisitoIso como 'NC' sem evidências reais de NC, reverte/remove a avaliação obsoleta.
    """
    from auditoria.models import (
        RespostaEntrevistaIso,
        SolicitacaoEvidenciaIso,
        AvaliacaoFinalRequisitoIso,
    )

    if not auditoria or not item_norma:
        return

    # 1. Busca todas as respostas vinculadas a este item nesta auditoria
    respostas = RespostaEntrevistaIso.objects.filter(
        auditoria=auditoria,
        pergunta__itens_norma=item_norma
    ).prefetch_related('solicitacoes')

    tem_nc_solicitacao = False
    tem_om_solicitacao = False
    tem_obs_solicitacao = False
    tem_c_solicitacao = False
    pior_grau_nc = 'MENOR'

    for resp in respostas:
        sols = list(resp.solicitacoes.all())
        if sols:
            # Recalcula a resposta individual baseando-se nas solicitações
            resp_nc = any(s.conclusao == 'NC' for s in sols)
            resp_om = any(s.conclusao == 'OM' for s in sols)
            resp_obs = any(s.conclusao == 'OBS' for s in sols)
            resp_p = any(s.conclusao == 'P' for s in sols)

            if resp_nc:
                novo_class = 'NC'
                tem_nc_solicitacao = True
                if any(s.conclusao == 'NC' and s.grau_nc == 'MAIOR' for s in sols):
                    pior_grau_nc = 'MAIOR'
                    resp_grau = 'MAIOR'
                else:
                    resp_grau = 'MENOR'
            elif resp_om:
                novo_class = 'OM'
                tem_om_solicitacao = True
                resp_grau = None
            elif resp_obs:
                novo_class = 'OBS'
                tem_obs_solicitacao = True
                resp_grau = None
            elif resp_p:
                novo_class = 'P'
                resp_grau = None
            else:
                novo_class = 'C'
                tem_c_solicitacao = True
                resp_grau = None

            if resp.classificacao != novo_class or resp.grau_nc != resp_grau:
                resp.classificacao = novo_class
                resp.grau_nc = resp_grau
                resp.save(update_fields=['classificacao', 'grau_nc'])
        else:
            # Resposta sem solicitações filhas
            if resp.classificacao == 'NC':
                # Se estava marcada como NC mas não possui solicitações de NC, reverte para C
                resp.classificacao = 'C'
                resp.grau_nc = None
                resp.save(update_fields=['classificacao', 'grau_nc'])
            elif resp.classificacao == 'OM':
                tem_om_solicitacao = True
            elif resp.classificacao == 'OBS':
                tem_obs_solicitacao = True
            elif resp.classificacao == 'C':
                tem_c_solicitacao = True

    # 2. Verifica se há alguma solicitação NC em qualquer pergunta deste item
    has_any_nc = SolicitacaoEvidenciaIso.objects.filter(
        resposta__auditoria=auditoria,
        resposta__pergunta__itens_norma=item_norma,
        conclusao='NC'
    ).exists()

    has_any_om = SolicitacaoEvidenciaIso.objects.filter(
        resposta__auditoria=auditoria,
        resposta__pergunta__itens_norma=item_norma,
        conclusao='OM'
    ).exists() or tem_om_solicitacao

    has_any_obs = SolicitacaoEvidenciaIso.objects.filter(
        resposta__auditoria=auditoria,
        resposta__pergunta__itens_norma=item_norma,
        conclusao='OBS'
    ).exists() or tem_obs_solicitacao

    # 3. Sincroniza AvaliacaoFinalRequisitoIso
    av_existente = AvaliacaoFinalRequisitoIso.objects.filter(
        auditoria=auditoria,
        item_norma=item_norma
    ).first()

    if not has_any_nc:
        # Se não há mais nenhuma NC no requisito:
        if av_existente and av_existente.classificacao == 'NC':
            # Remove a avaliação obsoleta ou ajusta para o novo status
            if has_any_om:
                av_existente.classificacao = 'OM'
                av_existente.grau_nc = None
                av_existente.save(update_fields=['classificacao', 'grau_nc'])
            elif has_any_obs:
                av_existente.classificacao = 'OBS'
                av_existente.grau_nc = None
                av_existente.save(update_fields=['classificacao', 'grau_nc'])
            else:
                # Requisito volta a ser Conforme: deletamos a avaliação de desvio
                av_existente.delete()
    else:
        # Se há NC, garante consistência
        if av_existente and av_existente.classificacao == 'NC' and not av_existente.grau_nc:
            av_existente.grau_nc = pior_grau_nc
            av_existente.save(update_fields=['grau_nc'])


def sincronizar_status_por_solicitacao(solicitacao):
    """
    Sincroniza todos os itens de norma relacionados a uma solicitação.
    """
    if not solicitacao or not solicitacao.resposta:
        return
    auditoria = solicitacao.resposta.auditoria
    pergunta = solicitacao.resposta.pergunta
    if not auditoria or not pergunta:
        return

    itens = list(pergunta.itens_norma.all())
    for item in itens:
        sincronizar_status_requisito(auditoria, item)
