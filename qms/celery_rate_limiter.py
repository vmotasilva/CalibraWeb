"""
Rate limiting for Celery tasks using sliding window and token bucket algorithms.

Features:
- Sliding window counter (memory efficient)
- Token bucket algorithm (smooth rate limiting)
- Per-user and per-system rate limits
- Redis-backed for distributed systems
- Decorator-based easy integration

Example:
    from qms.celery_rate_limiter import rate_limit, get_rate_limit_config

    @shared_task(bind=True)
    @rate_limit(rate='100/hour')
    def my_task(self, user_id):
        ...
"""

import time
import logging
from typing import Dict, Tuple, Optional, Union
from datetime import datetime, timedelta
from functools import wraps

try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

logger = logging.getLogger(__name__)


class RateLimiter:
    """Base rate limiter class."""
    
    def __init__(self, rate: str, key: str = 'default'):
        """
        Initialize rate limiter.
        
        Args:
            rate: Rate limit string (e.g., '100/hour', '10/minute', '1000/day')
            key: Redis key prefix
        """
        self.key = key
        self.rate_limit, self.window = self._parse_rate(rate)
        self.redis_key = f"rate_limit:{key}"
    
    @staticmethod
    def _parse_rate(rate: str) -> Tuple[int, int]:
        """
        Parse rate string to (limit, window_seconds).
        
        Args:
            rate: Rate string like '100/hour'
        
        Returns:
            Tuple of (limit, window_in_seconds)
        """
        limit_str, window_str = rate.split('/')
        limit = int(limit_str)
        
        window_map = {
            'second': 1,
            'minute': 60,
            'hour': 3600,
            'day': 86400,
            'week': 604800,
        }
        
        window = window_map.get(window_str, 3600)
        
        return limit, window
    
    def is_allowed(self, key: str) -> bool:
        """Check if request is allowed. Override in subclass."""
        raise NotImplementedError


class SlidingWindowRateLimiter(RateLimiter):
    """
    Sliding window rate limiter using Redis.
    
    Memory efficient, accurate for distributed systems.
    """
    
    def __init__(self, rate: str, key: str = 'default', redis_client=None):
        super().__init__(rate, key)
        self.redis = redis_client
        
        if not HAS_REDIS and redis_client is None:
            logger.warning("Redis not available for rate limiting")
    
    def is_allowed(self, identifier: str) -> bool:
        """
        Check if request is allowed under sliding window.
        
        Args:
            identifier: Unique identifier (user_id, task_name, etc.)
        
        Returns:
            True if allowed, False if rate limit exceeded
        """
        if not self.redis:
            return True  # Fallback if Redis unavailable
        
        full_key = f"{self.redis_key}:{identifier}"
        current_time = time.time()
        window_start = current_time - self.window
        
        try:
            # Remove old entries outside window
            self.redis.zremrangebyscore(full_key, 0, window_start)
            
            # Count requests in window
            count = self.redis.zcard(full_key)
            
            if count < self.rate_limit:
                # Add current request
                self.redis.zadd(full_key, {str(current_time): current_time})
                # Set expiration
                self.redis.expire(full_key, self.window + 1)
                return True
            else:
                return False
        
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            return True  # Allow on error
    
    def get_stats(self, identifier: str) -> Dict[str, Union[int, float]]:
        """Get rate limit statistics."""
        if not self.redis:
            return {}
        
        full_key = f"{self.redis_key}:{identifier}"
        current_time = time.time()
        window_start = current_time - self.window
        
        try:
            # Remove old entries
            self.redis.zremrangebyscore(full_key, 0, window_start)
            
            # Count requests in window
            count = self.redis.zcard(full_key)
            
            return {
                'requests_used': count,
                'requests_limit': self.rate_limit,
                'requests_remaining': max(0, self.rate_limit - count),
                'window_seconds': self.window,
                'reset_at': datetime.fromtimestamp(current_time + self.window).isoformat(),
            }
        
        except Exception as e:
            logger.error(f"Rate limit stats error: {e}")
            return {}
    
    def reset(self, identifier: str):
        """Reset rate limit for identifier."""
        if not self.redis:
            return
        
        full_key = f"{self.redis_key}:{identifier}"
        try:
            self.redis.delete(full_key)
        except Exception as e:
            logger.error(f"Rate limit reset error: {e}")


class TokenBucketRateLimiter(RateLimiter):
    """
    Token bucket rate limiter using Redis.
    
    Allows burst traffic while maintaining average rate.
    """
    
    def __init__(self, rate: str, key: str = 'default', redis_client=None, burst_size: int = None):
        super().__init__(rate, key)
        self.redis = redis_client
        self.burst_size = burst_size or self.rate_limit
        
        if not HAS_REDIS and redis_client is None:
            logger.warning("Redis not available for rate limiting")
    
    def is_allowed(self, identifier: str) -> bool:
        """
        Check if request is allowed under token bucket.
        
        Args:
            identifier: Unique identifier
        
        Returns:
            True if token available, False otherwise
        """
        if not self.redis:
            return True
        
        full_key = f"{self.redis_key}:{identifier}"
        refill_rate = self.rate_limit / self.window  # Tokens per second
        
        try:
            # Get current bucket state
            current_time = time.time()
            last_refill = self.redis.hget(full_key, 'last_refill')
            tokens = float(self.redis.hget(full_key, 'tokens') or self.burst_size)
            
            if last_refill:
                last_refill = float(last_refill)
                time_passed = current_time - last_refill
                tokens = min(self.burst_size, tokens + (refill_rate * time_passed))
            else:
                last_refill = current_time
            
            # Try to consume token
            if tokens >= 1:
                tokens -= 1
                self.redis.hset(
                    full_key,
                    mapping={
                        'tokens': str(tokens),
                        'last_refill': str(current_time),
                    }
                )
                self.redis.expire(full_key, self.window + 1)
                return True
            else:
                return False
        
        except Exception as e:
            logger.error(f"Token bucket error: {e}")
            return True
    
    def get_stats(self, identifier: str) -> Dict[str, Union[int, float]]:
        """Get token bucket statistics."""
        if not self.redis:
            return {}
        
        full_key = f"{self.redis_key}:{identifier}"
        
        try:
            tokens = float(self.redis.hget(full_key, 'tokens') or self.burst_size)
            
            return {
                'tokens_available': int(tokens),
                'tokens_max': self.burst_size,
                'refill_rate': self.rate_limit / self.window,
                'rate_limit': f"{self.rate_limit}/{self.window}s",
            }
        
        except Exception as e:
            logger.error(f"Token bucket stats error: {e}")
            return {}


# ============================================================================
# DECORATOR-BASED RATE LIMITING
# ============================================================================

def rate_limit(
    rate: str,
    key_func=None,
    algorithm: str = 'sliding_window',
    redis_client=None,
):
    """
    Decorator for rate limiting tasks or functions.
    
    Args:
        rate: Rate limit string (e.g., '100/hour')
        key_func: Function to generate rate limit key from args/kwargs
        algorithm: 'sliding_window' or 'token_bucket'
        redis_client: Redis client instance
    
    Example:
        @rate_limit('100/hour', key_func=lambda self, user_id: f'user:{user_id}')
        @shared_task(bind=True)
        def process_user_task(self, user_id, data):
            ...
    """
    if algorithm == 'token_bucket':
        limiter = TokenBucketRateLimiter(rate, redis_client=redis_client)
    else:
        limiter = SlidingWindowRateLimiter(rate, redis_client=redis_client)
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate rate limit key
            if key_func:
                if callable(key_func):
                    key = key_func(*args, **kwargs)
                else:
                    key = key_func
            else:
                key = func.__name__
            
            # Check rate limit
            if not limiter.is_allowed(key):
                stats = limiter.get_stats(key)
                logger.warning(
                    f"Rate limit exceeded for {key}: {stats}"
                )
                raise RateLimitExceeded(
                    f"Rate limit exceeded: {rate}",
                    key=key,
                    stats=stats
                )
            
            return func(*args, **kwargs)
        
        # Attach limiter for inspection
        wrapper.rate_limiter = limiter
        
        return wrapper
    
    return decorator


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""
    
    def __init__(self, message: str, key: str = None, stats: Dict = None):
        super().__init__(message)
        self.key = key
        self.stats = stats or {}


# ============================================================================
# TASK-SPECIFIC RATE LIMITS
# ============================================================================

RATE_LIMIT_CONFIGS = {
    # Import tasks
    'importar_procedimentos': '10/hour',
    'importar_colaboradores': '5/hour',
    'importar_instrumentos': '5/hour',
    
    # Export tasks
    'exportar_calibracoes': '20/hour',
    'exportar_instrumentos': '20/hour',
    
    # Calculation tasks
    'calcular_estatisticas': '50/hour',
    'gerar_relatorio': '30/hour',
    
    # Email tasks
    'enviar_email': '100/hour',
    'enviar_notificacao': '200/hour',
    
    # Cache warming
    'warm_instrumentos_cache': '1/hour',
    'warm_statistics_cache': '1/hour',
    'warm_categories_cache': '1/hour',
}


def get_rate_limit_for_task(task_name: str) -> Optional[str]:
    """Get rate limit configuration for a task."""
    return RATE_LIMIT_CONFIGS.get(task_name)


def apply_rate_limit_to_task(task, rate: Optional[str] = None):
    """
    Apply rate limiting to a Celery task.
    
    Args:
        task: Celery task instance
        rate: Rate limit string (default: from RATE_LIMIT_CONFIGS)
    """
    if rate is None:
        rate = get_rate_limit_for_task(task.name)
    
    if not rate:
        return  # No rate limit configured
    
    limiter = SlidingWindowRateLimiter(
        rate,
        key=task.name
    )
    
    # Wrap task's apply_async
    original_apply_async = task.apply_async
    
    def apply_async_with_rate_limit(*args, **kwargs):
        key = f"task:{task.name}"
        if not limiter.is_allowed(key):
            raise RateLimitExceeded(
                f"Task {task.name} rate limit exceeded: {rate}",
                key=key
            )
        return original_apply_async(*args, **kwargs)
    
    task.apply_async = apply_async_with_rate_limit


# ============================================================================
# MONITORING & STATISTICS
# ============================================================================

class RateLimitMonitor:
    """Monitor and report on rate limit usage."""
    
    def __init__(self, redis_client=None):
        self.redis = redis_client
    
    def get_all_stats(self) -> Dict[str, Dict]:
        """Get rate limit stats for all tracked keys."""
        if not self.redis:
            return {}
        
        stats = {}
        
        try:
            # Get all rate_limit keys from Redis
            pattern = "rate_limit:*"
            keys = self.redis.keys(pattern)
            
            for key in keys:
                count = self.redis.zcard(key)
                ttl = self.redis.ttl(key)
                stats[key] = {
                    'count': count,
                    'ttl_seconds': ttl,
                }
        
        except Exception as e:
            logger.error(f"Monitor error: {e}")
        
        return stats
    
    def get_hottest_keys(self, limit: int = 10) -> list:
        """Get most active rate limited keys."""
        stats = self.get_all_stats()
        sorted_stats = sorted(stats.items(), key=lambda x: x[1]['count'], reverse=True)
        return sorted_stats[:limit]
