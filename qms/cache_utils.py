# qms/cache_utils.py
# Cache utilities and decorators - Fase 6 Task #3

import hashlib
import json
from functools import wraps
from django.core.cache import cache, caches
from django.views.decorators.cache import cache_page as django_cache_page
from django.views.decorators.cache import cache_control
from config.cache_settings import CACHE_TIMEOUTS, CACHE_KEY_PATTERNS


class CacheManager:
    """Gerenciador centralizado de cache com invalidação automática."""
    
    @staticmethod
    def get_cache_instance(cache_name='default'):
        """Retorna instância do cache específico."""
        return caches[cache_name]
    
    @staticmethod
    def make_cache_key(pattern, **kwargs):
        """
        Cria chave de cache a partir de padrão.
        
        Args:
            pattern: Padrão de chave (ex: 'instrumentos_lista:{filtro_hash}')
            **kwargs: Parâmetros para substituir no padrão
        
        Returns:
            Chave formatada
        """
        return pattern.format(**kwargs)
    
    @staticmethod
    def invalidate_pattern(pattern_name):
        """
        Invalida todas as chaves que combinam com um padrão.
        
        Args:
            pattern_name: Nome do padrão (ex: 'instrumentos_lista')
        """
        cache_instance = CacheManager.get_cache_instance()
        
        # Para Redis, deletar padrões
        if hasattr(cache_instance, 'delete_pattern'):
            pattern = CACHE_KEY_PATTERNS.get(pattern_name, '')
            if pattern:
                cache_instance.delete_pattern(pattern)
        else:
            # Fallback: apenas clear tudo
            cache_instance.clear()
    
    @staticmethod
    def get_or_set(key, callable_func, timeout=None, cache_alias='default'):
        """
        Obtém valor do cache ou executa função se não existir.
        
        Args:
            key: Chave do cache
            callable_func: Função a executar se não existir
            timeout: Timeout em segundos
            cache_alias: Qual cache usar ('default', 'statistics', etc)
        
        Returns:
            Valor do cache ou resultado da função
        """
        cache_instance = caches[cache_alias]
        value = cache_instance.get(key)
        
        if value is None:
            value = callable_func()
            cache_instance.set(key, value, timeout)
        
        return value
    
    @staticmethod
    def set_many(data_dict, timeout=None, cache_alias='default'):
        """
        Seta múltiplas chaves de uma vez.
        
        Args:
            data_dict: Dict com {key: value}
            timeout: Timeout em segundos
            cache_alias: Qual cache usar
        """
        cache_instance = caches[cache_alias]
        cache_instance.set_many(data_dict, timeout)
    
    @staticmethod
    def delete_many(keys, cache_alias='default'):
        """Deleta múltiplas chaves."""
        cache_instance = caches[cache_alias]
        cache_instance.delete_many(keys)
    
    @staticmethod
    def get_stats(cache_alias='default'):
        """Retorna estatísticas de uso do cache."""
        cache_instance = caches[cache_alias]
        
        if hasattr(cache_instance, '_cache'):
            # Redis
            info = cache_instance._cache.info()
            return {
                'backend': 'Redis',
                'used_memory': info.get('used_memory_human', 'N/A'),
                'connected_clients': info.get('connected_clients', 'N/A'),
                'total_commands': info.get('total_commands_processed', 0),
                'evicted_keys': info.get('evicted_keys', 0),
            }
        return {}


# ============================================================================
# DECORATORS
# ============================================================================

def cache_result(timeout=None, cache_alias='default', key_prefix=None):
    """
    Decorator para cachear resultado de função/método.
    
    Usage:
        @cache_result(timeout=300, cache_alias='default')
        def get_all_instruments():
            return Instrumento.objects.all()
    
    Args:
        timeout: Timeout em segundos (padrão: 300)
        cache_alias: Qual cache usar
        key_prefix: Prefixo da chave
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Criar chave única
            cache_key = f"{key_prefix or func.__name__}"
            
            if args:
                args_hash = hashlib.md5(str(args).encode()).hexdigest()[:8]
                cache_key += f":{args_hash}"
            
            if kwargs:
                kwargs_hash = hashlib.md5(json.dumps(kwargs, sort_keys=True).encode()).hexdigest()[:8]
                cache_key += f":{kwargs_hash}"
            
            # Tentar obter do cache
            cache_instance = caches[cache_alias]
            result = cache_instance.get(cache_key)
            
            if result is None:
                result = func(*args, **kwargs)
                cache_instance.set(cache_key, result, timeout)
            
            return result
        
        # Adicionar método para invalidar
        wrapper.invalidate = lambda: caches[cache_alias].delete(cache_key)
        return wrapper
    
    return decorator


def cache_view(timeout=None, cache_alias='default'):
    """
    Decorator para cachear resultado de view.
    
    Usage:
        @cache_view(timeout=300)
        def my_view(request):
            return render(request, 'template.html')
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Criar chave baseada em User + URL
            cache_key = f"view:{request.user.id}:{request.path}"
            
            cache_instance = caches[cache_alias]
            response = cache_instance.get(cache_key)
            
            if response is None:
                response = view_func(request, *args, **kwargs)
                
                # Cachear se sucesso
                if hasattr(response, 'status_code') and response.status_code == 200:
                    cache_instance.set(cache_key, response, timeout)
            
            return response
        
        return wrapper
    
    return decorator


# ============================================================================
# INVALIDATION SIGNALS
# ============================================================================

def setup_cache_invalidation():
    """
    Setup de sinais para invalidação automática de cache.
    
    Deve ser chamado em apps.py do app.
    """
    from django.db.models.signals import post_save, post_delete
    from django.dispatch import receiver
    from qms.models_legacy import Instrumento, HistoricoCalibracao, CategoriaInstrumento, Setor
    from config.cache_settings import CACHE_INVALIDATION_MAP
    
    @receiver(post_save, sender=Instrumento)
    @receiver(post_delete, sender=Instrumento)
    def invalidate_instrumento_cache(sender, **kwargs):
        """Invalida cache quando Instrumento é alterado."""
        patterns = CACHE_INVALIDATION_MAP.get('Instrumento', [])
        for pattern in patterns:
            CacheManager.invalidate_pattern(pattern)
    
    @receiver(post_save, sender=HistoricoCalibracao)
    @receiver(post_delete, sender=HistoricoCalibracao)
    def invalidate_historico_cache(sender, **kwargs):
        """Invalida cache quando HistoricoCalibracao é alterado."""
        patterns = CACHE_INVALIDATION_MAP.get('HistoricoCalibracao', [])
        for pattern in patterns:
            CacheManager.invalidate_pattern(pattern)
    
    @receiver(post_save, sender=CategoriaInstrumento)
    @receiver(post_delete, sender=CategoriaInstrumento)
    def invalidate_categoria_cache(sender, **kwargs):
        """Invalida cache quando CategoriaInstrumento é alterado."""
        patterns = CACHE_INVALIDATION_MAP.get('CategoriaInstrumento', [])
        for pattern in patterns:
            CacheManager.invalidate_pattern(pattern)
    
    @receiver(post_save, sender=Setor)
    @receiver(post_delete, sender=Setor)
    def invalidate_setor_cache(sender, **kwargs):
        """Invalida cache quando Setor é alterado."""
        patterns = CACHE_INVALIDATION_MAP.get('Setor', [])
        for pattern in patterns:
            CacheManager.invalidate_pattern(pattern)


# ============================================================================
# CACHE WARMING FUNCTIONS
# ============================================================================

def warm_cache_for_common_queries():
    """
    Pré-carrega cache com queries mais comuns.
    Deve rodar periodicamente (via Celery beat).
    """
    from qms.models_legacy import Instrumento, CategoriaInstrumento, Setor
    from qms.utils.query_optimizer import InstrumentoQueryOptimizer, EstatisticasQueryOptimizer
    
    cache_instance = caches['default']
    stats_cache = caches['statistics']
    
    # Warm: Listagem de instrumentos ativos
    key = CACHE_KEY_PATTERNS['instrumentos_lista'].format(filtro_hash='ativos')
    value = InstrumentoQueryOptimizer.listar_completo().filter(ativo=True)
    cache_instance.set(key, list(value), CACHE_TIMEOUTS['instrumentos_lista'])
    
    # Warm: Categorias
    key = CACHE_KEY_PATTERNS['categorias_lista']
    value = list(CategoriaInstrumento.objects.all().values('id', 'nome'))
    cache_instance.set(key, value, CACHE_TIMEOUTS['categorias_lista'])
    
    # Warm: Setores
    key = CACHE_KEY_PATTERNS['setores_lista']
    value = list(Setor.objects.all().values('id', 'nome'))
    cache_instance.set(key, value, CACHE_TIMEOUTS['setores_lista'])
    
    # Warm: Estatísticas gerais
    key = CACHE_KEY_PATTERNS['estatisticas_gerais']
    value = {
        'total_instrumentos': Instrumento.objects.filter(ativo=True).count(),
        'total_vencidos': Instrumento.objects.filter(
            ativo=True,
            data_proxima_calibracao__lte='today'
        ).count(),
    }
    stats_cache.set(key, value, CACHE_TIMEOUTS['estatisticas_gerais'])
    
    return {
        'status': 'success',
        'message': 'Cache warmed successfully',
        'keys_set': 4,
    }


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def hash_dict(data_dict):
    """Cria hash de um dict para usar em chave de cache."""
    json_str = json.dumps(data_dict, sort_keys=True)
    return hashlib.md5(json_str.encode()).hexdigest()[:8]


def hash_query_params(request):
    """Cria hash dos query params da request."""
    params = request.GET.dict()
    return hash_dict(params)


def invalidate_all_caches():
    """Invalida todos os caches. Use com cuidado!"""
    for cache_alias in caches:
        caches[cache_alias].clear()
    return {'status': 'All caches cleared'}
