from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from .models import RegistroTreinamento, PacoteTreinamento


@receiver(post_save, sender=RegistroTreinamento)
def atualizar_status_treinamento(sender, instance, created, **kwargs):
    """Atualiza o status do treinamento quando um registro é criado/atualizado"""
    if created:
        # Lógica para atualizar status
        # será implementada na Fase 3
        pass


@receiver(m2m_changed, sender=PacoteTreinamento.procedimentos.through)
def atualizar_procedimentos_pacote(sender, instance, action, **kwargs):
    """Atualiza quando procedimentos são adicionados ao pacote"""
    if action in ['post_add', 'post_remove']:
        # Lógica para sincronizar procedimentos
        # será implementada na Fase 3
        pass
