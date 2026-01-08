# -*- coding: utf-8 -*-
"""
Tasks Celery para o módulo RH (Recursos Humanos)
"""

from celery import shared_task
from datetime import date
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task(name='rh.atualizar_status_ferias')
def atualizar_status_ferias():
    """
    Task que executa periodicamente para atualizar o status de férias.
    - PLANEJADO → EM_ANDAMENTO quando data_inicio chegar e aprovada=True
    - EM_ANDAMENTO → CONCLUIDO quando data_fim passar
    """
    from rh.models import Ferias
    
    try:
        hoje = date.today()
        
        # Atualizar férias aprovadas que começaram hoje ou antes (e ainda não terminaram)
        ferias_em_andamento = Ferias.objects.filter(
            aprovada=True,
            status="PLANEJADO",
            data_inicio__lte=hoje,
            data_fim__gte=hoje
        )
        
        count_em_andamento = ferias_em_andamento.update(status="EM_ANDAMENTO")
        
        if count_em_andamento > 0:
            logger.info(f"✅ Atualizadas {count_em_andamento} férias para EM_ANDAMENTO")
        
        # Atualizar férias que já terminaram
        ferias_concluidas = Ferias.objects.filter(
            aprovada=True,
            status__in=["PLANEJADO", "EM_ANDAMENTO"],
            data_fim__lt=hoje
        )
        
        count_concluidas = ferias_concluidas.update(status="CONCLUIDO")
        
        if count_concluidas > 0:
            logger.info(f"✅ Atualizadas {count_concluidas} férias para CONCLUIDO")
        
        # Atualizar campo em_ferias dos colaboradores
        from rh.models import Colaborador
        
        colaboradores_em_ferias = Colaborador.objects.filter(
            ferias__aprovada=True,
            ferias__data_inicio__lte=hoje,
            ferias__data_fim__gte=hoje
        ).distinct()
        
        for colaborador in colaboradores_em_ferias:
            colaborador.em_ferias = True
            colaborador.save(update_fields=["em_ferias"])
        
        # Desmarcar colaboradores que não estão mais em férias
        colaboradores_nao_em_ferias = Colaborador.objects.filter(
            em_ferias=True
        ).exclude(
            ferias__aprovada=True,
            ferias__data_inicio__lte=hoje,
            ferias__data_fim__gte=hoje
        )
        
        count_desatualizar = colaboradores_nao_em_ferias.update(em_ferias=False)
        
        if count_desatualizar > 0:
            logger.info(f"✅ Desmarcadas {count_desatualizar} colaboradores como não em férias")
        
        total = count_em_andamento + count_concluidas + count_desatualizar
        logger.info(f"✅ Task de atualização de férias completada: {total} registros atualizados")
        
        return {
            "success": True,
            "em_andamento": count_em_andamento,
            "concluidas": count_concluidas,
            "desatualizar": count_desatualizar,
            "total": total
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao atualizar status de férias: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }
