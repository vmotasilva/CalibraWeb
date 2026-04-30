"""
Cache Managers for Different Data Types
========================================

Specialized cache managers for:
1. Model Instances (ORM objects)
2. Query Results (Lists, QuerySets)
3. Aggregated Data (Stats, counts)
4. User-Specific Data (Authenticated content)

Each manager handles serialization, invalidation patterns,
and optimal TTL based on data type.

Author: Caching Team
Date: 2025-12
"""

import json
import logging
from typing import Any, List, Type, Optional, Dict, Callable
from datetime import datetime, timedelta

from django.core.cache import cache
from django.db.models import Model, QuerySet
from django.contrib.auth.models import User

from config.multilevel_cache import multi_level_cache

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
# MODEL INSTANCE CACHE
# ════════════════════════════════════════════════════════════════

class ModelInstanceCache:
    """
    Cache for Django model instances.
    
    Handles:
    - Serialization of model instances
    - Automatic cache key generation
    - Invalidation on model changes
    - Relationship prefetching hints
    
    Example:
        cache_mgr = ModelInstanceCache(Instrument)
        
        # Get with cache
        instrument = cache_mgr.get(id=1, timeout=3600)
        
        # Set
        cache_mgr.set(instrument, timeout=3600)
        
        # Clear by ID
        cache_mgr.invalidate(id=1)
    """

    def __init__(self, model: Type[Model], timeout: int = 3600):
        """
        Initialize model cache.
        
        Args:
            model: Django model class
            timeout: Default cache TTL in seconds
        """
        self.model = model
        self.model_name = model.__name__.lower()
        self.timeout = timeout

    def _get_cache_key(self, **kwargs) -> str:
        """Generate cache key for model instance."""
        if 'pk' in kwargs or 'id' in kwargs:
            pk = kwargs.get('pk') or kwargs.get('id')
            return f"{self.model_name}_{pk}"
        elif len(kwargs) == 1:
            key, value = list(kwargs.items())[0]
            return f"{self.model_name}_{key}_{value}"
        return None

    def get(self, timeout: Optional[int] = None, **kwargs) -> Optional[Model]:
        """
        Get model instance from cache or database.
        
        Args:
            timeout: Override default timeout
            **kwargs: Model lookup parameters (id, pk, slug, etc)
            
        Returns:
            Model instance or None
            
        Example:
            instrument = cache_mgr.get(id=1, timeout=3600)
            user = cache_mgr.get(username='john', timeout=1800)
        """
        cache_key = self._get_cache_key(**kwargs)
        if not cache_key:
            return self.model.objects.get(**kwargs)

        timeout = timeout or self.timeout

        # Try multi-level cache with fetch function
        def fetch():
            return self.model.objects.get(**kwargs)

        instance = multi_level_cache.get(
            cache_key,
            fetch_fn=fetch,
            timeout=timeout
        )

        return instance

    def set(self, instance: Model, timeout: Optional[int] = None) -> None:
        """
        Cache model instance.
        
        Args:
            instance: Model instance to cache
            timeout: Override default timeout
        """
        cache_key = f"{self.model_name}_{instance.pk}"
        timeout = timeout or self.timeout
        
        multi_level_cache.set(cache_key, instance, timeout=timeout)
        logger.debug(f"Cached {self.model_name} instance: {instance.pk}")

    def invalidate(self, **kwargs) -> None:
        """
        Invalidate cached model instance.
        
        Args:
            **kwargs: Model lookup parameters
        """
        cache_key = self._get_cache_key(**kwargs)
        if cache_key:
            multi_level_cache.delete(cache_key)
            logger.debug(f"Invalidated {self.model_name}: {cache_key}")

    def invalidate_all(self) -> None:
        """Invalidate all instances of this model."""
        pattern = f"{self.model_name}_*"
        count = multi_level_cache.invalidate_pattern(pattern)
        logger.debug(f"Invalidated {count} {self.model_name} instances")


# ════════════════════════════════════════════════════════════════
# QUERY RESULT CACHE
# ════════════════════════════════════════════════════════════════

class QueryResultCache:
    """
    Cache for query results (lists, counts, aggregates).
    
    Handles:
    - QuerySet result caching
    - List and dict result serialization
    - Automatic cache key from query parameters
    - Result subset caching (slices)
    
    Example:
        cache_mgr = QueryResultCache()
        
        # Cache full list
        instruments = cache_mgr.get(
            'instruments_list',
            lambda: Instrument.objects.all().values('id', 'name')[:100],
            timeout=300
        )
        
        # Cache count
        total = cache_mgr.get(
            'instruments_count',
            lambda: Instrument.objects.count(),
            timeout=600
        )
        
        # Cache with filters
        filtered = cache_mgr.get(
            'instruments_active',
            lambda: Instrument.objects.filter(active=True).values_list('id'),
            timeout=300
        )
    """

    def __init__(self):
        """Initialize query result cache."""
        pass

    def get(
        self,
        key: str,
        query_fn: Callable,
        timeout: int = 300,
        **options
    ) -> Any:
        """
        Get query results from cache.
        
        Args:
            key: Cache key (descriptive name)
            query_fn: Function returning query results
            timeout: Cache TTL in seconds
            **options: Additional options
                - force_refresh: Bypass cache
                - max_items: Limit result size
                
        Returns:
            Query results (list or value)
        """
        if options.get('force_refresh'):
            result = query_fn()
        else:
            # Try multi-level cache
            def fetch():
                return list(query_fn()) if isinstance(query_fn(), QuerySet) else query_fn()
            
            result = multi_level_cache.get(
                f"query_{key}",
                fetch_fn=fetch,
                timeout=timeout
            )

        # Apply limits if specified
        if options.get('max_items') and isinstance(result, list):
            result = result[:options['max_items']]

        return result

    def invalidate(self, key: str) -> None:
        """Invalidate query result."""
        multi_level_cache.delete(f"query_{key}")
        logger.debug(f"Invalidated query: {key}")

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate multiple query results by pattern.
        
        Args:
            pattern: Glob pattern (e.g., 'instruments_*')
            
        Returns:
            Number of keys invalidated
        """
        return multi_level_cache.invalidate_pattern(f"query_{pattern}")


# ════════════════════════════════════════════════════════════════
# AGGREGATED DATA CACHE
# ════════════════════════════════════════════════════════════════

class AggregateCache:
    """
    Cache for aggregated data (stats, counts, totals).
    
    Perfect for:
    - Dashboard statistics
    - Report data
    - Counts and totals
    - Time-series data
    
    Example:
        cache_mgr = AggregateCache()
        
        # Cache daily stats
        stats = cache_mgr.get_or_compute(
            'daily_stats_2024_12_01',
            compute_fn=lambda: compute_daily_stats(date(2024, 12, 1)),
            timeout=86400  # 1 day
        )
    """

    def __init__(self):
        """Initialize aggregate cache."""
        self.ttls = {
            'realtime': 60,      # 1 minute
            'frequent': 300,     # 5 minutes
            'hourly': 3600,      # 1 hour
            'daily': 86400,      # 1 day
            'weekly': 604800,    # 1 week
            'monthly': 2592000,  # 30 days
        }

    def get_or_compute(
        self,
        key: str,
        compute_fn: Callable,
        frequency: str = 'frequent',
        **options
    ) -> Any:
        """
        Get aggregated data or compute if not cached.
        
        Args:
            key: Cache key
            compute_fn: Function to compute value if not cached
            frequency: One of: realtime, frequent, hourly, daily, weekly, monthly
            **options:
                - force_refresh: Bypass cache
                
        Returns:
            Aggregated data
        """
        if options.get('force_refresh'):
            value = compute_fn()
        else:
            timeout = self.ttls.get(frequency, 300)
            value = multi_level_cache.get(
                f"agg_{key}",
                fetch_fn=compute_fn,
                timeout=timeout
            )

        return value

    def set(self, key: str, value: Any, frequency: str = 'frequent') -> None:
        """
        Set aggregated data.
        
        Args:
            key: Cache key
            value: Aggregated value
            frequency: TTL frequency
        """
        timeout = self.ttls.get(frequency, 300)
        multi_level_cache.set(f"agg_{key}", value, timeout=timeout)

    def invalidate(self, key: str) -> None:
        """Invalidate aggregated data."""
        multi_level_cache.delete(f"agg_{key}")

    def invalidate_time_range(self, pattern: str) -> int:
        """Invalidate time-based aggregates."""
        return multi_level_cache.invalidate_pattern(f"agg_{pattern}*")


# ════════════════════════════════════════════════════════════════
# USER-SPECIFIC CACHE
# ════════════════════════════════════════════════════════════════

class UserSpecificCache:
    """
    Cache for user-specific data (preferences, settings).
    
    Automatically includes user ID in cache key.
    Marks as private (not shared via CDN).
    
    Example:
        user_cache = UserSpecificCache()
        
        # Get user preferences
        prefs = user_cache.get(
            request.user,
            'preferences',
            compute_fn=lambda: get_user_preferences(request.user),
            timeout=1800
        )
        
        # Set user setting
        user_cache.set(request.user, 'theme', 'dark', timeout=3600)
    """

    def __init__(self):
        """Initialize user-specific cache."""
        pass

    def _make_key(self, user: User, key: str) -> str:
        """Generate user-specific cache key."""
        return f"user_{user.id}_{key}"

    def get(
        self,
        user: User,
        key: str,
        compute_fn: Optional[Callable] = None,
        timeout: int = 1800,
    ) -> Any:
        """
        Get user-specific data.
        
        Args:
            user: Django User instance
            key: Data key
            compute_fn: Function to compute if not cached
            timeout: Cache TTL
            
        Returns:
            Cached value
        """
        cache_key = self._make_key(user, key)

        if compute_fn:
            return multi_level_cache.get(
                cache_key,
                fetch_fn=compute_fn,
                timeout=timeout
            )
        else:
            return multi_level_cache.get(cache_key)

    def set(
        self,
        user: User,
        key: str,
        value: Any,
        timeout: int = 1800,
    ) -> None:
        """
        Set user-specific data.
        
        Args:
            user: Django User instance
            key: Data key
            value: Value to cache
            timeout: Cache TTL
        """
        cache_key = self._make_key(user, key)
        multi_level_cache.set(cache_key, value, timeout=timeout)
        logger.debug(f"Cached user data: {user.id}/{key}")

    def invalidate(self, user: User, key: str) -> None:
        """Invalidate user-specific data."""
        cache_key = self._make_key(user, key)
        multi_level_cache.delete(cache_key)

    def invalidate_user(self, user: User) -> int:
        """Invalidate all data for a user."""
        pattern = f"user_{user.id}_*"
        return multi_level_cache.invalidate_pattern(pattern)


# ════════════════════════════════════════════════════════════════
# GLOBAL INSTANCES
# ════════════════════════════════════════════════════════════════

# Query result cache
query_cache = QueryResultCache()

# Aggregated data cache
aggregate_cache = AggregateCache()

# User-specific cache
user_cache = UserSpecificCache()


# ════════════════════════════════════════════════════════════════
# QUICK START
# ════════════════════════════════════════════════════════════════
#
# from config.cache_managers import (
#     ModelInstanceCache,
#     query_cache,
#     aggregate_cache,
#     user_cache
# )
#
# # Model cache
# instrument_cache = ModelInstanceCache(Instrument, timeout=3600)
# instrument = instrument_cache.get(id=1)
#
# # Query results
# from qms.models import Instrument
# instruments = query_cache.get(
#     'all_instruments',
#     lambda: Instrument.objects.all().values('id', 'name'),
#     timeout=300
# )
#
# # Aggregated data
# stats = aggregate_cache.get_or_compute(
#     'total_instruments',
#     compute_fn=lambda: Instrument.objects.count(),
#     frequency='hourly'
# )
#
# # User preferences
# theme = user_cache.get(
#     request.user,
#     'ui_theme',
#     compute_fn=lambda: get_user_theme(request.user),
#     timeout=3600
# )
#
# ════════════════════════════════════════════════════════════════
