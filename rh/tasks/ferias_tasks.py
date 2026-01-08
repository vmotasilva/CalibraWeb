# -*- coding: utf-8 -*-
"""
Celery Tasks para Gestão de Férias
Atualização automática de status e sincronização
"""

from celery import shared_task
from django.utils import timezone
from datetime import date
import logging

from rh.models import Ferias, Colaborador

logger = logging.getLogger(__name__)


@shared_task(name='rh.atualizar_status_ferias')
def atualizar_status_ferias():
    """
    Atualiza automaticamente o status das férias de "Em Andamento" para "Concluído"
    quando a data de término já passou.
    
    Esta task é executada periodicamente pelo Celery Beat.
    """
    hoje = date.today()
    atualizadas = 0
    erros = 0
    
    try:
        # Buscar todas as férias em andamento
        ferias_em_andamento = Ferias.objects.filter(status="EM_ANDAMENTO")
        
        for ferias in ferias_em_andamento:
            try:
                # Verificar se a data de término já passou
                if ferias.data_fim < hoje:
                    # Atualizar status para concluído
                    ferias.status = "CONCLUIDO"
                    ferias.save(update_fields=['status'])
                    
                    # Atualizar o campo em_ferias do colaborador
                    colaborador = ferias.colaborador
                    ferias_ativas = Ferias.objects.filter(
                        colaborador=colaborador,
                        aprovada=True,
                        data_inicio__lte=hoje,
                        data_fim__gte=hoje
                    ).exists()
                    
                    if colaborador.em_ferias != ferias_ativas:
                        colaborador.em_ferias = ferias_ativas
                        colaborador.save(update_fields=['em_ferias'])
                    
                    atualizadas += 1
                    logger.info(
                        f"Férias atualizado para CONCLUÍDO: {colaborador.nome_completo} "
                        f"({ferias.data_inicio} a {ferias.data_fim})"
                    )
                    
            except Exception as e:
                erros += 1
                logger.error(
                    f"Erro ao atualizar férias {ferias.id}: {str(e)}",
                    exc_info=True
                )
        
        logger.info(
            f"Atualização de status de férias concluída: "
            f"{atualizadas} atualizados, {erros} erros"
        )
        
        return {
            'status': 'success',
            'atualizados': atualizadas,
            'erros': erros,
            'timestamp': str(timezone.now())
        }
        
    except Exception as e:
        logger.error(f"Erro na task atualizar_status_ferias: {str(e)}", exc_info=True)
        return {
            'status': 'error',
            'mensagem': str(e),
            'timestamp': str(timezone.now())
        }


@shared_task(name='rh.sincronizar_em_ferias')
def sincronizar_em_ferias():
    """
    Sincroniza o campo 'em_ferias' de todos os colaboradores
    com base em seus registros de férias aprovadas.
    
    Útil para corrigir inconsistências.
    """
    hoje = date.today()
    sincronizados = 0
    erros = 0
    
    try:
        # Buscar todos os colaboradores ativos
        colaboradores = Colaborador.objects.filter(is_active=True)
        
        for colaborador in colaboradores:
            try:
                # Verificar se tem férias ativas aprovadas
                ferias_ativas = Ferias.objects.filter(
                    colaborador=colaborador,
                    aprovada=True,
                    data_inicio__lte=hoje,
                    data_fim__gte=hoje
                ).exists()
                
                # Atualizar se diferente
                if colaborador.em_ferias != ferias_ativas:
                    colaborador.em_ferias = ferias_ativas
                    colaborador.save(update_fields=['em_ferias'])
                    sincronizados += 1
                    
            except Exception as e:
                erros += 1
                logger.error(
                    f"Erro ao sincronizar colaborador {colaborador.id}: {str(e)}",
                    exc_info=True
                )
        
        logger.info(
            f"Sincronização de em_ferias concluída: "
            f"{sincronizados} sincronizados, {erros} erros"
        )
        
        return {
            'status': 'success',
            'sincronizados': sincronizados,
            'erros': erros,
            'timestamp': str(timezone.now())
        }
        
    except Exception as e:
        logger.error(f"Erro na task sincronizar_em_ferias: {str(e)}", exc_info=True)
        return {
            'status': 'error',
            'mensagem': str(e),
            'timestamp': str(timezone.now())
        }
