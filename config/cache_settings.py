# config/cache_settings.py
# Cache Configuration - Development/Production agnostic

import os
from django.conf import settings

# ============================================================================
# CACHE BACKEND - Auto-detect based on Redis availability
# ============================================================================

# Use Redis if REDIS_URL is provided, otherwise use in-memory cache
USE_REDIS = bool(os.getenv('REDIS_URL')) or os.getenv('DEBUG') == 'False'

if USE_REDIS:
    # Production: Redis Cache
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1'),
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'SOCKET_CONNECT_TIMEOUT': 5,
                'SOCKET_TIMEOUT': 5,
                'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
                'CONNECTION_POOL_CLASS_KWARGS': {
                    'max_connections': 50,
                    'retry_on_timeout': True,
                }
            },
            'KEY_PREFIX': 'calibra_',
            'TIMEOUT': 300,  # 5 minutos padrão
        },
        
        # Cache separado para sessões (mais persistente)
        'sessions': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/2'),
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'SOCKET_CONNECT_TIMEOUT': 5,
                'SOCKET_TIMEOUT': 5,
            },
            'TIMEOUT': 86400,  # 24 horas
        },
        
        # Cache separado para dados de longa duração (estatísticas)
        'statistics': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/3'),
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'SOCKET_CONNECT_TIMEOUT': 5,
                'SOCKET_TIMEOUT': 5,
        },
        'TIMEOUT': 3600,  # 1 hora
        },
        
        # Cache separado para queries (validação mais frequente)
        'queries': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/4'),
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'SOCKET_CONNECT_TIMEOUT': 5,
                'SOCKET_TIMEOUT': 5,
            },
            'TIMEOUT': 600,  # 10 minutos
        },
    }
else:
    # Development: In-memory cache (works without Redis)
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'calibra-dev-cache',
            'TIMEOUT': 300,  # 5 minutos
        },
        'sessions': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'calibra-sessions',
            'TIMEOUT': 86400,  # 24 horas
        },
        'statistics': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'calibra-stats',
            'TIMEOUT': 3600,  # 1 hora
        },
        'queries': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'calibra-queries',
            'TIMEOUT': 600,  # 10 minutos
        },
    }# ============================================================================
# CACHE TIMEOUTS (em segundos)
# ============================================================================

CACHE_TIMEOUTS = {
    # Listagens e búscas
    'instrumentos_lista': 30 * 60,           # 30 minutos
    'instrumentos_vencidos': 15 * 60,        # 15 minutos
    'categorias_lista': 60 * 60,             # 1 hora
    'setores_lista': 60 * 60,                # 1 hora
    
    # Estatísticas
    'estatisticas_gerais': 60 * 60,          # 1 hora
    'estatisticas_categoria': 30 * 60,       # 30 minutos
    'estatisticas_setor': 30 * 60,           # 30 minutos
    
    # Detalhes
    'instrumento_detalhe': 10 * 60,          # 10 minutos
    'historico_detalhe': 10 * 60,            # 10 minutos
    
    # Relatórios
    'relatorio_vencidos': 15 * 60,           # 15 minutos
    'relatorio_proximos_30': 15 * 60,        # 15 minutos
    
    # Busca (mais curto pois pode variar)
    'busca_resultado': 5 * 60,               # 5 minutos
    
    # Paginação
    'queryset_count': 5 * 60,                # 5 minutos
}

# ============================================================================
# CACHE KEY PATTERNS
# ============================================================================

CACHE_KEY_PATTERNS = {
    'instrumentos_lista': 'instrumentos:lista:{filtro_hash}',
    'instrumentos_vencidos': 'instrumentos:vencidos',
    'categorias_lista': 'categorias:lista',
    'setores_lista': 'setores:lista',
    'estatisticas_gerais': 'stats:geral',
    'estatisticas_categoria': 'stats:categoria:{categoria_id}',
    'estatisticas_setor': 'stats:setor:{setor_id}',
    'instrumento_detalhe': 'instrumento:{instrumento_id}',
    'historico_detalhe': 'historico:{historico_id}',
    'relatorio_vencidos': 'relatorio:vencidos',
    'relatorio_proximos_30': 'relatorio:proximos_30',
    'busca_resultado': 'busca:{query_hash}',
}

# ============================================================================
# CACHE INVALIDATION SIGNALS
# ============================================================================

# Quando estes modelos são alterados, os seguintes caches são invalidados:
CACHE_INVALIDATION_MAP = {
    'Instrumento': [
        'instrumentos_lista',
        'instrumentos_vencidos',
        'estatisticas_gerais',
        'estatisticas_categoria',
        'estatisticas_setor',
    ],
    'HistoricoCalibracao': [
        'instrumentos_vencidos',
        'estatisticas_gerais',
        'relatorio_vencidos',
        'relatorio_proximos_30',
    ],
    'CategoriaInstrumento': [
        'categorias_lista',
        'estatisticas_categoria',
    ],
    'Setor': [
        'setores_lista',
        'estatisticas_setor',
    ],
}

# ============================================================================
# SESSION & SECURITY
# ============================================================================

# Use cache for sessions if Redis available, otherwise use database
if USE_REDIS:
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'sessions'
else:
    # Fallback to database sessions for development
    SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# ============================================================================
# CACHE WARMING (Background Tasks)
# ============================================================================

# Tasks que rodam em background para pré-carregar cache
CACHE_WARMING_TASKS = [
    'qms.tasks.warm_instrumentos_cache',
    'qms.tasks.warm_statistics_cache',
    'qms.tasks.warm_categories_cache',
]

# Frequência de atualização (em minutos)
CACHE_WARMING_FREQUENCY = {
    'warm_instrumentos_cache': 25,      # A cada 25 min (expira em 30)
    'warm_statistics_cache': 55,        # A cada 55 min (expira em 60)
    'warm_categories_cache': 55,        # A cada 55 min (expira em 60)
}
