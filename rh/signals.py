"""
Sinais para rastrear mudanças nos modelos de RH
"""
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import (
    Colaborador, HistoricoSetor, HistoricoPosto,
    HistoricoSalario, HistoricoColaborador
)
import json


@receiver(pre_save, sender=Colaborador)
def rastrear_mudancas_colaborador(sender, instance, **kwargs):
    """
    Detecta mudanças nos campos principais do Colaborador
    e cria registros no histórico
    """
    if instance.pk:
        # Colaborador existente - verificar se houve mudanças
        try:
            anterior = Colaborador.objects.get(pk=instance.pk)
            
            # Verificar mudança de setor
            if anterior.setor != instance.setor:
                HistoricoSetor.objects.create(
                    colaborador=instance,
                    setor_anterior=anterior.setor,
                    setor_novo=instance.setor,
                    data_efetiva=timezone.now().date(),
                    registrado_por=None  # Será preenchido pela view se necessário
                )
                # Registrar no histórico geral
                HistoricoColaborador.objects.create(
                    colaborador=instance,
                    tipo_mudanca="SETOR",
                    descricao=f"Setor alterado de {anterior.setor} para {instance.setor}",
                    dados_anteriores={"setor": str(anterior.setor) if anterior.setor else None},
                    dados_novos={"setor": str(instance.setor) if instance.setor else None},
                    data_efetiva=timezone.now().date(),
                    registrado_por=None
                )
            
            # Verificar mudança de cargo
            if anterior.cargo != instance.cargo:
                HistoricoPosto.objects.create(
                    colaborador=instance,
                    cargo_anterior=anterior.cargo,
                    cargo_novo=instance.cargo,
                    data_efetiva=timezone.now().date(),
                    registrado_por=None
                )
                # Registrar no histórico geral
                HistoricoColaborador.objects.create(
                    colaborador=instance,
                    tipo_mudanca="CARGO",
                    descricao=f"Cargo alterado de {anterior.cargo} para {instance.cargo}",
                    dados_anteriores={"cargo": anterior.cargo},
                    dados_novos={"cargo": instance.cargo},
                    data_efetiva=timezone.now().date(),
                    registrado_por=None
                )
            
            # Verificar mudança de salário
            if anterior.salario != instance.salario:
                diferenca = instance.salario - anterior.salario if instance.salario and anterior.salario else None
                HistoricoSalario.objects.create(
                    colaborador=instance,
                    salario_anterior=anterior.salario,
                    salario_novo=instance.salario,
                    diferenca=diferenca,
                    data_efetiva=timezone.now().date(),
                    registrado_por=None
                )
                # Registrar no histórico geral
                HistoricoColaborador.objects.create(
                    colaborador=instance,
                    tipo_mudanca="SALARIO",
                    descricao=f"Salário alterado de R$ {anterior.salario} para R$ {instance.salario}",
                    dados_anteriores={"salario": float(anterior.salario) if anterior.salario else None},
                    dados_novos={"salario": float(instance.salario) if instance.salario else None},
                    data_efetiva=timezone.now().date(),
                    registrado_por=None
                )
            
            # Verificar mudança de turno
            if anterior.turno != instance.turno:
                HistoricoColaborador.objects.create(
                    colaborador=instance,
                    tipo_mudanca="TURNO",
                    descricao=f"Turno alterado de {anterior.turno} para {instance.turno}",
                    dados_anteriores={"turno": anterior.turno},
                    dados_novos={"turno": instance.turno},
                    data_efetiva=timezone.now().date(),
                    registrado_por=None
                )
            
            # Verificar mudança de status
            if anterior.is_active != instance.is_active:
                status_anterior = "Ativo" if anterior.is_active else "Inativo"
                status_novo = "Ativo" if instance.is_active else "Inativo"
                HistoricoColaborador.objects.create(
                    colaborador=instance,
                    tipo_mudanca="STATUS",
                    descricao=f"Status alterado de {status_anterior} para {status_novo}",
                    dados_anteriores={"is_active": anterior.is_active},
                    dados_novos={"is_active": instance.is_active},
                    data_efetiva=timezone.now().date(),
                    registrado_por=None
                )
        except Colaborador.DoesNotExist:
            pass

@receiver(post_save, sender=Colaborador)
def invalidar_cache_dashboard_rh(sender, instance, **kwargs):
    """
    Invalida o cache do dashboard RH quando um colaborador é alterado.
    Isso garante que mudanças sejam refletidas imediatamente.
    """
    from django.core.cache import cache
    from django.contrib.auth.models import User
    
    # Limpar cache de TODOS os usuários (mais seguro)
    # Padrão: rh_dashboard_<user_id>_*
    cache.delete_pattern("rh_dashboard_*")
    
    # Log para debug
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"✓ Cache RH dashboard invalidado (Colaborador {instance.id} alterado)")