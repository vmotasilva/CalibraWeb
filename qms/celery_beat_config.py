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
    
    # ====================================================================
    # RH TASKS - Atualização automática de férias
    # ====================================================================
    
    # Atualizar status de férias - A cada 5 minutos
    'atualizar-status-ferias': {
        'task': 'rh.atualizar_status_ferias',
        'schedule': crontab(minute='*/5'),  # A cada 5 minutos
        'options': {'queue': 'default', 'expires': 300}
    },
    
    # Sincronizar status em_ferias - A cada 15 minutos
    'sincronizar-em-ferias': {
        'task': 'rh.sincronizar_em_ferias',
        'schedule': crontab(minute='*/15'),  # A cada 15 minutos
        'options': {'queue': 'default', 'expires': 900}
    },
    
    # ====================================================================
    # CACHE WARMING TASKS - Fase 6 Task #3
    # ====================================================================
    
    # Cache warming de instrumentos - A cada 25 minutos
    'warm-instrumentos-cache': {
        'task': 'qms.tasks.warm_instrumentos_cache',
        'schedule': crontab(minute='*/25'),
        'options': {'queue': 'cache', 'expires': 1500}
    },
    
    # Cache warming de estatísticas - A cada 55 minutos
    'warm-statistics-cache': {
        'task': 'qms.tasks.warm_statistics_cache',
        'schedule': crontab(minute='*/55'),
        'options': {'queue': 'cache', 'expires': 3300}
    },
    
    # Cache warming de categorias - A cada 55 minutos
    'warm-categories-cache': {
        'task': 'qms.tasks.warm_categories_cache',
        'schedule': crontab(minute='*/55'),
        'options': {'queue': 'cache', 'expires': 3300}
    },
}

# Queue configuration
CELERY_QUEUES = {
    'default': {'exchange': 'default', 'routing_key': 'default'},
    'reports': {'exchange': 'reports', 'routing_key': 'report'},
    'alerts': {'exchange': 'alerts', 'routing_key': 'alert'},
    'cache': {'exchange': 'cache', 'routing_key': 'cache'},
}

# Task routing
CELERY_ROUTES = {
    'qms.tasks.gerar_relatorio_diario_vencidos': {'queue': 'reports'},
    'qms.tasks.gerar_relatorio_semanal_estatisticas': {'queue': 'reports'},
    'qms.tasks.gerar_relatorio_alerta_critico': {'queue': 'alerts'},
    'qms.tasks.warm_instrumentos_cache': {'queue': 'cache'},
    'qms.tasks.warm_statistics_cache': {'queue': 'cache'},
    'qms.tasks.warm_categories_cache': {'queue': 'cache'},
    'rh.atualizar_status_ferias': {'queue': 'default'},
    'rh.sincronizar_em_ferias': {'queue': 'default'},
}
