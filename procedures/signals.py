# -*- coding: utf-8 -*-
"""
Signals para o módulo Procedures
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from rh.models import Colaborador
from procedures.models import RegistroTreinamento


@receiver(post_save, sender=Colaborador)
def marcar_treinamentos_inativos_quando_colaborador_inativo(sender, instance, created, **kwargs):
    """
    Quando um colaborador é marcado como inativo (is_active=False),
    marca todos os seus treinamentos como inativos também.
    """
    if not instance.is_active:
        # Marcar todos os treinamentos deste colaborador como inativos
        RegistroTreinamento.objects.filter(
            colaborador=instance,
            ativo=True
        ).update(ativo=False)
