"""
RH Module Tasks (Celery)
Tarefas assíncronas para recursos humanos
"""

# Import tasks para serem descobertas pelo Celery
from .ferias_tasks import atualizar_status_ferias, sincronizar_em_ferias

__all__ = [
    'atualizar_status_ferias',
    'sincronizar_em_ferias',
]
