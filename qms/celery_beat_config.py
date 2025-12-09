# -*- coding: utf-8 -*-
"""
Configuração de Celery Beat para scheduled tasks - Fase 5

Para usar, adicione ao seu settings.py ou config/celery.py:

from celery.schedules import crontab

app.conf.beat_schedule = {
    'relatorio-diario-vencidos': {
        'task': 'qms.tasks.gerar_relatorio_diario_vencidos',
        'schedule': crontab(hour=8, minute=0),  # 8h da manhã
        'options': {'queue': 'reports'}
    },
    'relatorio-semanal-estatisticas': {
        'task': 'qms.tasks.gerar_relatorio_semanal_estatisticas',
        'schedule': crontab(day_of_week=0, hour=9, minute=0),  # Seg 9h
        'options': {'queue': 'reports'}
    },
    'alerta-critico-vencidos': {
        'task': 'qms.tasks.gerar_relatorio_alerta_critico',
        'schedule': crontab(hour='*/4'),  # A cada 4 horas
        'options': {'queue': 'alerts'}
    },
}
"""

from celery.schedules import crontab

# Agendamento de tarefas - Reporte e Alertas
CELERY_BEAT_SCHEDULE = {
    # Relatório diário de vencidos - 8h da manhã
    'relatorio-diario-vencidos': {
        'task': 'qms.tasks.gerar_relatorio_diario_vencidos',
        'schedule': crontab(hour=8, minute=0),
        'options': {'queue': 'reports', 'expires': 3600}
    },
    
    # Relatório semanal de estatísticas - Seg 9h
    'relatorio-semanal-estatisticas': {
        'task': 'qms.tasks.gerar_relatorio_semanal_estatisticas',
        'schedule': crontab(day_of_week=0, hour=9, minute=0),  # Domingo 9h
        'options': {'queue': 'reports', 'expires': 3600}
    },
    
    # Alerta crítico a cada 4 horas
    'alerta-critico-vencidos': {
        'task': 'qms.tasks.gerar_relatorio_alerta_critico',
        'schedule': crontab(minute=0, hour='*/4'),  # A cada 4 horas
        'options': {'queue': 'alerts', 'expires': 1800}
    },
}

# Queue configuration
CELERY_QUEUES = {
    'default': {'exchange': 'default', 'routing_key': 'default'},
    'reports': {'exchange': 'reports', 'routing_key': 'report'},
    'alerts': {'exchange': 'alerts', 'routing_key': 'alert'},
}

# Task routing
CELERY_ROUTES = {
    'qms.tasks.gerar_relatorio_diario_vencidos': {'queue': 'reports'},
    'qms.tasks.gerar_relatorio_semanal_estatisticas': {'queue': 'reports'},
    'qms.tasks.gerar_relatorio_alerta_critico': {'queue': 'alerts'},
}
