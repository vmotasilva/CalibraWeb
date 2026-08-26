from __future__ import annotations
import logging
from django.db.models.signals import post_save, post_delete, pre_save, pre_delete
from django.dispatch import receiver
from auditoria.models import SolicitacaoEvidenciaIso, RespostaEntrevistaIso

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=SolicitacaoEvidenciaIso)
def solicitacao_iso_pre_save(sender, instance, **kwargs):
    """
    Guarda o estado anterior da solicitação (resposta anterior e conclusão anterior)
    para que na troca de requisito/bloco possamos recalcular o requisito de origem.
    """
    if instance.pk:
        try:
            antigo = SolicitacaoEvidenciaIso.objects.select_related('resposta__auditoria', 'resposta__pergunta').get(pk=instance.pk)
            instance._old_resposta = antigo.resposta
            instance._old_conclusao = antigo.conclusao
        except SolicitacaoEvidenciaIso.DoesNotExist:
            instance._old_resposta = None
            instance._old_conclusao = None
    else:
        instance._old_resposta = None
        instance._old_conclusao = None


@receiver(post_save, sender=SolicitacaoEvidenciaIso)
def solicitacao_iso_post_save(sender, instance, created, **kwargs):
    """
    Sempre que uma solicitação de evidência é criada, atualizada ou transferida:
    Recalcula o status consolidado do requisito de origem (se mudou) e do requisito de destino.
    """
    from auditoria.services.sincronizacao_requisitos import sincronizar_status_requisito, sincronizar_status_por_solicitacao

    try:
        # Se mudou de resposta/pergunta, sincroniza o requisito de origem
        old_resp = getattr(instance, '_old_resposta', None)
        if old_resp and old_resp != instance.resposta:
            auditoria_antiga = old_resp.auditoria
            if auditoria_antiga and old_resp.pergunta:
                for item in old_resp.pergunta.itens_norma.all():
                    sincronizar_status_requisito(auditoria_antiga, item)

        # Sincroniza o requisito de destino atual
        sincronizar_status_por_solicitacao(instance)
    except Exception as e:
        logger.exception("Erro no signal post_save de SolicitacaoEvidenciaIso: %s", e)


@receiver(pre_delete, sender=SolicitacaoEvidenciaIso)
def solicitacao_iso_pre_delete(sender, instance, **kwargs):
    """
    Captura dados de auditoria e itens antes da exclusão física.
    """
    try:
        if instance.resposta and instance.resposta.auditoria and instance.resposta.pergunta:
            instance._delete_auditoria = instance.resposta.auditoria
            instance._delete_itens = list(instance.resposta.pergunta.itens_norma.all())
    except Exception:
        instance._delete_auditoria = None
        instance._delete_itens = []


@receiver(post_delete, sender=SolicitacaoEvidenciaIso)
def solicitacao_iso_post_delete(sender, instance, **kwargs):
    """
    Sempre que uma evidência é excluída:
    Recalcula obrigatoriamente o status consolidado de todos os requisitos afetados.
    """
    from auditoria.services.sincronizacao_requisitos import sincronizar_status_requisito

    try:
        auditoria = getattr(instance, '_delete_auditoria', None)
        itens = getattr(instance, '_delete_itens', [])
        if auditoria and itens:
            for item in itens:
                sincronizar_status_requisito(auditoria, item)
    except Exception as e:
        logger.exception("Erro no signal post_delete de SolicitacaoEvidenciaIso: %s", e)
