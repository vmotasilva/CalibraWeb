# REDIS CACHING STRATEGY & IMPLEMENTATION
## CalibraWeb Performance Optimization Layer

**Objective**: Reduce database load by 30-50% through intelligent caching  
**Expected Improvement**: Admin page load: 500ms → 200ms (60% faster)  
**Implementation**: Django-redis with cache invalidation patterns

---

## 🎯 CACHING STRATEGY

### Cache Layers

1. **Query Result Cache** (5-30 min TTL)
   - Django ORM query caching
   - Admin changelist queries
   - Common aggregations
   - Impact: 70-80% reduction for repeated queries

2. **Template Fragment Cache** (15 min - 1 day TTL)
   - Dashboard widgets
   - Static sections
   - Admin list displays
   - Impact: Reduce template rendering time

3. **API Response Cache** (1-60 min TTL)
   - API endpoints
   - Search results
   - Filtered querysets
   - Impact: Instant response for common requests

4. **Session Cache** (30 min TTL)
   - User sessions
   - Authentication tokens
   - User preferences
   - Impact: Faster auth checks

### Cache Keys Strategy

```
Hierarchy:
  app:<app_name>:<model>:<operation>:<filter>
  
Examples:
  app:metrologia:instrumento:list:all
  app:metrologia:historico_calibracao:count:2025-12-01
  app:rh:colaborador:detail:123
  app:qms:admin:changelist:page_1
```

### TTL (Time-To-Live) Configuration

```python
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'PARSER_KWARGS': {'encoding': 'utf-8'},
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
        },
        'KEY_PREFIX': 'calibraweb',
        'TIMEOUT': 300,  # Default 5 minutes
    }
}

# TTL by cache type:
TTL_CONFIG = {
    'query_result': 300,        # 5 min - Database queries
    'template_fragment': 900,   # 15 min - Template rendering
    'api_response': 600,        # 10 min - API responses
    'session': 1800,            # 30 min - User sessions
    'static_data': 86400,       # 1 day - Reference data
}
```

---

## 📦 INSTALLATION & SETUP

### 1. Install Dependencies

```bash
pip install django-redis redis
```

### 2. Configure Redis in settings.py

```python
# Cache Configuration
if not DEBUG:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1'),
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'PARSER_KWARGS': {'encoding': 'utf-8'},
                'SOCKET_CONNECT_TIMEOUT': 5,
                'SOCKET_TIMEOUT': 5,
                'RETRY_ON_TIMEOUT': True,
                'SOCKET_KEEPALIVE': True,
            },
            'KEY_PREFIX': 'calibraweb',
            'TIMEOUT': 300,
        }
    }
    
    # Session backend
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'default'
else:
    # Development: Use local memory cache
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
        }
    }
```

### 3. Create Cache Utility Module

**File**: `shared/cache_utils.py`

```python
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from functools import wraps
from typing import Optional, Callable

class CacheHelper:
    """Helper class for consistent cache operations"""
    
    # Cache TTL constants
    TTL_VERY_SHORT = 60        # 1 minute
    TTL_SHORT = 300            # 5 minutes
    TTL_MEDIUM = 900           # 15 minutes
    TTL_LONG = 3600            # 1 hour
    TTL_VERY_LONG = 86400      # 1 day
    
    @staticmethod
    def make_key(app: str, model: str, operation: str, *args) -> str:
        """Generate consistent cache key"""
        parts = [f'app:{app}:{model}:{operation}'] + list(args)
        return ':'.join(parts)
    
    @staticmethod
    def get(key: str, default=None):
        """Get value from cache"""
        return cache.get(key, default)
    
    @staticmethod
    def set(key: str, value, timeout: int = 300):
        """Set value in cache"""
        cache.set(key, value, timeout)
    
    @staticmethod
    def delete(key: str):
        """Delete from cache"""
        cache.delete(key)
    
    @staticmethod
    def clear_pattern(pattern: str):
        """Clear all keys matching pattern"""
        # Note: Redis only, requires redis-py
        import redis
        conn = redis.from_url(cache.location)
        keys = conn.keys(pattern)
        if keys:
            conn.delete(*keys)

def cache_queryset(ttl: int = 300):
    """Decorator to cache queryset results"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and args
            cache_key = f"qs:{func.__name__}:{str(args)}:{str(kwargs)}"
            
            result = cache.get(cache_key)
            if result is None:
                result = func(*args, **kwargs)
                cache.set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator

def invalidate_cache_on_save():
    """Decorator to invalidate cache when model is saved"""
    def decorator(sender, instance, **kwargs):
        # Example: Clear model list cache
        cache_key = CacheHelper.make_key(
            sender._meta.app_label,
            sender._meta.model_name,
            'list'
        )
        CacheHelper.delete(cache_key)
    return decorator
```

### 4. Cache Invalidation Signals

**Add to app signals.py**:

```python
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from shared.cache_utils import CacheHelper

@receiver(post_save, sender=Instrumento)
def invalidate_instrumento_cache(sender, instance, **kwargs):
    """Invalidate Instrumento cache on save"""
    CacheHelper.clear_pattern('app:metrologia:instrumento:*')
    CacheHelper.clear_pattern('app:metrologia:historicocalibracao:*')

@receiver(post_delete, sender=Instrumento)
def invalidate_instrumento_delete_cache(sender, instance, **kwargs):
    """Invalidate Instrumento cache on delete"""
    CacheHelper.clear_pattern('app:metrologia:instrumento:*')
    CacheHelper.clear_pattern('app:metrologia:historicocalibracao:*')
```

---

## 🔧 IMPLEMENTATION CHECKLIST

### Phase 1: Core Setup (1-2 hours)
- [ ] Install redis and django-redis
- [ ] Configure Redis in settings.py
- [ ] Create cache_utils.py module
- [ ] Test Redis connection
- [ ] Implement session caching

### Phase 2: Query Caching (2-3 hours)
- [ ] Cache admin changelist queries
- [ ] Cache common QuerySet results
- [ ] Cache aggregation functions
- [ ] Add cache invalidation signals
- [ ] Test cache hit rates

### Phase 3: Template & Response Caching (1-2 hours)
- [ ] Cache template fragments
- [ ] Cache admin filter results
- [ ] Cache dashboard widgets
- [ ] Add cache statistics to admin

### Phase 4: Monitoring & Optimization (1-2 hours)
- [ ] Set up cache statistics collection
- [ ] Monitor hit/miss rates
- [ ] Identify slow queries
- [ ] Optimize cache keys
- [ ] Performance benchmarking

---

## 📊 EXPECTED PERFORMANCE GAINS

### Before Caching
- Admin changelist: 10-15 database queries
- Load time: 500-1000ms
- Database CPU: 40-60%
- Memory usage: 200-400MB

### After Caching
- Admin changelist: 1-2 database queries (85% reduction)
- Load time: 150-300ms (60-70% faster)
- Database CPU: 10-20%
- Memory usage: 400-600MB (Redis)
- Cache hit rate: 70-85% for admin operations

### ROI
- Cost: 2-4 hours implementation
- Benefit: 60% load time reduction
- Server capacity: Can handle 5-10x more users
- User experience: Instant admin interface

---

## 🚀 DEPLOYMENT CHECKLIST

- [ ] Redis server deployed and running
- [ ] Redis connection validated
- [ ] Cache configuration in production environment
- [ ] Cache statistics monitoring active
- [ ] Backup strategy includes Redis data
- [ ] Failover plan if Redis goes down
- [ ] Cache clear procedures documented
- [ ] Team trained on cache invalidation

---

## 📈 MONITORING & MAINTENANCE

### Cache Statistics

```python
def get_cache_stats():
    """Get cache performance statistics"""
    from django.core.cache import cache
    
    try:
        # Redis only
        info = cache.client.get_client().info()
        return {
            'used_memory': info['used_memory_human'],
            'connected_clients': info['connected_clients'],
            'evicted_keys': info['evicted_keys'],
        }
    except:
        return None
```

### Monitoring Alerts

- Alert if cache hit rate < 50%
- Alert if Redis memory > 80%
- Alert if Redis connection fails
- Alert on cache evictions

### Regular Maintenance

- Monitor cache memory usage
- Review slow queries not cached
- Adjust TTLs based on patterns
- Clean up unused cache keys
- Update cache strategy with new features

---

## 🔒 SECURITY CONSIDERATIONS

- Redis password protection required in production
- Redis not exposed to public internet
- Use SSL/TLS for Redis connections
- Sanitize cache keys to prevent injection
- Monitor cache for sensitive data (PII)
- Regular Redis security updates

---

## 📚 REFERENCES

- [Django Cache Framework](https://docs.djangoproject.com/en/5.0/topics/cache/)
- [django-redis Documentation](https://niwinz.github.io/django-redis/)
- [Redis Best Practices](https://redis.io/docs/management/admin-guide/client-side-caching/)
- [Cache Invalidation Patterns](https://redis.io/patterns/caching/)
