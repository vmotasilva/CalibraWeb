# -*- coding: utf-8 -*-
"""
Signals para o novo fluxo de cotações - ETAPA 4

Automatizações disparadas quando um atendimento é confirmado:
- AQUISICAO: Marcar instrumento para substituição
- CALIBRACAO: Criar RegistroCalibracao em estado inicial
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from metrologia.models import AtendimentoSolicitacao, ProcessoAutomatizacao, ItemCotacao


@receiver(post_save, sender=AtendimentoSolicitacao)
def disparar_automatizacoes_atendimento(sender, instance, created, **kwargs):
    """
    Dispara automatizações quando atendimento é confirmado
    """
    # Só processa se status mudou para CONFIRMADA
    if instance.status != 'CONFIRMADA':
        return
    
    # Verifica se processo já foi criado
    if ProcessoAutomatizacao.objects.filter(atendimento=instance).exists():
        return
    
    item_cotacao = instance.item_cotacao
    tipo_servico = item_cotacao.tipo_servico
    
    # Dispara baseado no tipo de serviço
    if tipo_servico == 'AQUISICAO':
        _processar_aquisicao(instance, item_cotacao)
    elif tipo_servico == 'CALIBRACAO':
        _processar_calibracao(instance, item_cotacao)


def _processar_aquisicao(atendimento, item_cotacao):
    """
    ETAPA 4A: Automatizações para AQUISIÇÃO
    
    Passo 1: Desativar instrumento antigo
    Passo 2: Marcar para substituição
    Passo 3: Registrar data prevista de recebimento
    """
    instrumento = item_cotacao.instrumento
    
    try:
        # Passo 1: Desativar instrumento antigo
        instrumento.ativo = False
        instrumento.save()
        
        # TODO: Passo 2-3: Criar ProcessoSubstituicao ou similar
        # Por enquanto, apenas registramos que aquisição foi iniciada
        
        # Registrar processo
        processo = ProcessoAutomatizacao.objects.create(
            atendimento=atendimento,
            tipo_processo='AQUISICAO',
            status='ATIVA',
            observacoes=f'Instrumento {instrumento.tag} desativado para substituição. Previsão: {atendimento.data_prevista_atendimento}'
        )
        
    except Exception as e:
        # Registrar erro
        ProcessoAutomatizacao.objects.create(
            atendimento=atendimento,
            tipo_processo='AQUISICAO',
            status='ERRO',
            observacoes=f'Erro ao processar aquisição: {str(e)}'
        )


def _processar_calibracao(atendimento, item_cotacao):
    """
    ETAPA 4B: Automatizações para CALIBRAÇÃO
    
    Passo 1: Criar RegistroCalibracao com status AGUARDANDO_ENVIO
    Passo 2: Pré-preencher campos básicos
    Passo 3: Deixar em aberto apenas resultados
    """
    try:
        from metrologia.models import HistoricoCalibracao
        from fornecedores.models import Fornecedor
        
        instrumento = item_cotacao.instrumento
        cotacao = item_cotacao.cotacao_fornecedor
        fornecedor = cotacao.fornecedor
        
        # Criar RegistroCalibracao (HistoricoCalibracao)
        # NOTA: Pode ser que o modelo seja RegistroCalibracao ou HistoricoCalibracao
        # Ajuste conforme seu modelo real
        
        historico = HistoricoCalibracao.objects.create(
            instrumento=instrumento,
            fornecedor=fornecedor,
            data_calibracao=atendimento.data_prevista_atendimento,
            proxima_calibracao=None,  # Será calculado após calibração
            temperatura=None,
            umidade=None,
            observacoes=f'Calibração requisitada pela Solicitação #{atendimento.solicitacao.numero}. '
                       f'Item: {atendimento.item_solicitacao.necessidade}'
        )
        
        # Registrar processo bem-sucedido
        processo = ProcessoAutomatizacao.objects.create(
            atendimento=atendimento,
            tipo_processo='CALIBRACAO',
            status='ATIVA',
            nome_modelo_objeto='HistoricoCalibracao',
            id_objeto_criado=historico.id,
            observacoes=f'RegistroCalibracao #{historico.id} criado. Aguardando preenchimento de resultados.'
        )
        
    except Exception as e:
        # Registrar erro
        ProcessoAutomatizacao.objects.create(
            atendimento=atendimento,
            tipo_processo='CALIBRACAO',
            status='ERRO',
            observacoes=f'Erro ao processar calibração: {str(e)}'
        )


# Note: Para usar estes signals, você precisa importá-los em apps.py:
# 
# from django.apps import AppConfig
#
# class MetrologiaConfig(AppConfig):
#     default_auto_field = 'django.db.models.BigAutoField'
#     name = 'metrologia'
#     
#     def ready(self):
#         import metrologia.signals  # Importar signals quando app estiver pronto

