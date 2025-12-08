from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from .models import (
    HistoricoCalibracao, SolicitacaoInstrumento, 
    OcorrenciaInstrumento, OrdemCalibracao
)


@receiver(post_save, sender=HistoricoCalibracao)
def atualizar_situacao_instrumento(sender, instance, created, **kwargs):
    """Atualiza a situação do instrumento quando uma calibração é registrada"""
    if created:
        instrumento = instance.instrumento
        # Lógica para atualizar situação do instrumento
        # será implementada na Fase 3
        pass


@receiver(post_save, sender=OrdemCalibracao)
def notificar_nova_ordem(sender, instance, created, **kwargs):
    """Notifica quando uma nova ordem de calibração é criada"""
    if created:
        # Lógica de notificação
        # será implementada na Fase 5 (tasks)
        pass
