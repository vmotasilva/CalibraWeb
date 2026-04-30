"""
Cache Warming System
====================

Predictive cache warming based on access patterns and analytics.

Features:
- Analyze user access patterns
- Predict frequently accessed items
- Warm cache during off-peak hours
- Personalized warming per user
- Scheduled pre-caching via Celery

Author: Caching Team
Date: 2025-12
"""

import logging
from datetime import timedelta
from collections import defaultdict, Counter
from typing import Dict, List, Set, Tuple, Optional
from django.utils import timezone
from django.db.models import QuerySet, Model

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
# ACCESS PATTERN ANALYZER
# ════════════════════════════════════════════════════════════════

class AccessPattern:
    """Represents an access pattern for a piece of data."""
    
    def __init__(self, key: str):
        self.key = key
        self.access_count = 0
        self.unique_users = set()
        self.timestamps = []
        self.score = 0.0
    
    def record_access(self, user_id: Optional[int] = None):
        """Record an access to this key."""
        self.access_count += 1
        if user_id:
            self.unique_users.add(user_id)
        self.timestamps.append(timezone.now())
        self._calculate_score()
    
    def _calculate_score(self) -> float:
        """
        Calculate popularity score based on:
        - Total accesses
        - Unique users
        - Recency (recent > old)
        """
        # Base score: access count
        score = self.access_count * 1.0
        
        # Boost: unique users (popular with many)
        score += len(self.unique_users) * 10.0
        
        # Recency boost: recent accesses worth more
        if self.timestamps:
            now = timezone.now()
            for ts in self.timestamps[-5:]:  # Last 5 accesses
                age_hours = (now - ts).total_seconds() / 3600
                recency_factor = 1.0 / (1.0 + age_hours)
                score += recency_factor * 5.0
        
        self.score = score
        return score
    
    def is_hot(self, threshold: float = 50.0) -> bool:
        """Check if this is a hot (popular) key."""
        return self.score >= threshold
    
    def is_warm(self, threshold: float = 20.0) -> bool:
        """Check if this is a warm key."""
        return threshold <= self.score < 50.0
    
    def __repr__(self) -> str:
        return f"AccessPattern({self.key}, score={self.score:.1f}, accesses={self.access_count})"


class AccessPatternAnalyzer:
    """Analyzes access patterns to identify warming candidates."""
    
    def __init__(self, window_hours: int = 24):
        """
        Initialize analyzer.
        
        Args:
            window_hours: Time window for analysis (default 24h)
        """
        self.window_hours = window_hours
        self.patterns: Dict[str, AccessPattern] = {}
        self.model_patterns: Dict[str, List[str]] = defaultdict(list)
        self.time_patterns: Dict[str, float] = defaultdict(float)  # Hour -> avg score
    
    def record_access(self, key: str, model_name: str = None, user_id: int = None):
        """Record an access pattern."""
        if key not in self.patterns:
            self.patterns[key] = AccessPattern(key)
        
        self.patterns[key].record_access(user_id)
        
        if model_name:
            self.model_patterns[model_name].append(key)
        
        # Record time-of-day pattern
        hour = timezone.now().hour
        self.time_patterns[f"hour_{hour}"] += 1.0
    
    def get_hot_keys(self, limit: int = 20, threshold: float = 50.0) -> List[str]:
        """Get the hottest (most popular) keys."""
        hot = [
            (key, pattern.score)
            for key, pattern in self.patterns.items()
            if pattern.is_hot(threshold)
        ]
        hot.sort(key=lambda x: x[1], reverse=True)
        return [k for k, _ in hot[:limit]]
    
    def get_warm_keys(self, limit: int = 50, threshold: float = 20.0) -> List[str]:
        """Get warm keys."""
        warm = [
            (key, pattern.score)
            for key, pattern in self.patterns.items()
            if pattern.is_warm(threshold)
        ]
        warm.sort(key=lambda x: x[1], reverse=True)
        return [k for k, _ in warm[:limit]]
    
    def get_model_popularity(self, model_name: str) -> Dict[str, int]:
        """Get popularity scores for a model's data."""
        keys = self.model_patterns.get(model_name, [])
        scores = Counter()
        
        for key in keys:
            if key in self.patterns:
                scores[key] = self.patterns[key].score
        
        return dict(scores.most_common(20))
    
    def get_peak_hours(self, top_n: int = 3) -> List[int]:
        """Get peak access hours (0-23)."""
        hours = []
        for key, score in self.time_patterns.items():
            if key.startswith("hour_"):
                hour = int(key.split("_")[1])
                hours.append((hour, score))
        
        hours.sort(key=lambda x: x[1], reverse=True)
        return [h for h, _ in hours[:top_n]]
    
    def get_off_peak_hours(self, top_n: int = 3) -> List[int]:
        """Get off-peak hours (best for warming)."""
        all_hours = list(range(24))
        peak = set(self.get_peak_hours())
        off_peak = [h for h in all_hours if h not in peak]
        return off_peak[-top_n:] if off_peak else [2, 3, 4]  # Default: 2-4 AM
    
    def get_stats(self) -> Dict:
        """Get analyzer statistics."""
        patterns = list(self.patterns.values())
        scores = [p.score for p in patterns]
        
        return {
            'total_patterns': len(self.patterns),
            'hot_keys': len([p for p in patterns if p.is_hot()]),
            'warm_keys': len([p for p in patterns if p.is_warm()]),
            'avg_score': sum(scores) / len(scores) if scores else 0,
            'max_score': max(scores) if scores else 0,
            'peak_hours': self.get_peak_hours(),
            'off_peak_hours': self.get_off_peak_hours(),
        }
    
    def reset(self):
        """Reset all patterns."""
        self.patterns.clear()
        self.model_patterns.clear()
        self.time_patterns.clear()


# ════════════════════════════════════════════════════════════════
# CACHE WARMER
# ════════════════════════════════════════════════════════════════

class CacheWarmer:
    """Warms cache with frequently accessed data."""
    
    def __init__(self, analyzer: AccessPatternAnalyzer):
        self.analyzer = analyzer
        self._warming_registry = {}  # key -> warming_func
    
    def register_warmer(self, model_name: str, warming_func: callable):
        """
        Register a warming function for a model.
        
        Args:
            model_name: Name of the model (e.g., 'Instrument')
            warming_func: Function that returns data to cache
                         Signature: warming_func(instance_ids) -> List[data]
        """
        self._warming_registry[model_name] = warming_func
    
    def warm_hot_items(self, cache_mgr, top_n: int = 20) -> int:
        """
        Warm cache with hot (popular) items.
        
        Args:
            cache_mgr: MultiLevelCache manager
            top_n: Number of hot items to warm
        
        Returns:
            Number of items warmed
        """
        hot_keys = self.analyzer.get_hot_keys(limit=top_n)
        count = 0
        
        for key in hot_keys:
            try:
                # Get data and cache it
                data = self._fetch_data_for_key(key)
                if data:
                    cache_mgr.set(key, data, ttl=3600)  # 1 hour
                    count += 1
                    logger.debug(f"Warmed hot key: {key}")
            
            except Exception as e:
                logger.error(f"Error warming key {key}: {e}")
        
        logger.info(f"Warmed {count} hot items")
        return count
    
    def warm_model_data(self, model_name: str, cache_mgr, limit: int = 100) -> int:
        """
        Warm cache for all instances of a model.
        
        Args:
            model_name: Model to warm (e.g., 'Instrument')
            cache_mgr: MultiLevelCache manager
            limit: Maximum instances to warm
        
        Returns:
            Number of instances warmed
        """
        warming_func = self._warming_registry.get(model_name)
        if not warming_func:
            logger.warning(f"No warming function registered for {model_name}")
            return 0
        
        try:
            # Get popular instances
            popularity = self.analyzer.get_model_popularity(model_name)
            
            if not popularity:
                logger.debug(f"No access patterns for {model_name}, skipping")
                return 0
            
            count = 0
            for key in list(popularity.keys())[:limit]:
                try:
                    data = self._fetch_data_for_key(key)
                    if data:
                        cache_mgr.set(key, data, ttl=3600)
                        count += 1
                
                except Exception as e:
                    logger.error(f"Error warming {key}: {e}")
            
            logger.info(f"Warmed {count} instances of {model_name}")
            return count
        
        except Exception as e:
            logger.error(f"Error warming {model_name}: {e}", exc_info=True)
            return 0
    
    def warm_by_time_pattern(self, cache_mgr, current_hour: int = None) -> int:
        """
        Warm cache items that are popular at current hour.
        
        Args:
            cache_mgr: MultiLevelCache manager
            current_hour: Hour to predict for (default: now)
        
        Returns:
            Number of items warmed
        """
        if current_hour is None:
            current_hour = timezone.now().hour
        
        # Get items popular at this hour
        # This would need historical hourly data
        hot_keys = self.analyzer.get_hot_keys(limit=50)
        
        count = 0
        for key in hot_keys:
            try:
                data = self._fetch_data_for_key(key)
                if data:
                    cache_mgr.set(key, data, ttl=3600)
                    count += 1
            except Exception:
                pass
        
        logger.info(f"Warmed {count} items for peak hour {current_hour}")
        return count
    
    def warm_user_data(self, user_id: int, cache_mgr) -> int:
        """
        Warm cache with data relevant to a specific user.
        
        Args:
            user_id: User ID
            cache_mgr: MultiLevelCache manager
        
        Returns:
            Number of items warmed
        """
        # Get patterns for this user
        user_patterns = [
            (key, pattern)
            for key, pattern in self.analyzer.patterns.items()
            if user_id in pattern.unique_users
        ]
        
        # Sort by score and warm top items
        user_patterns.sort(key=lambda x: x[1].score, reverse=True)
        
        count = 0
        for key, _ in user_patterns[:20]:
            try:
                data = self._fetch_data_for_key(key)
                if data:
                    user_key = f"user_{user_id}_{key}"
                    cache_mgr.set(user_key, data, ttl=1800)  # 30 min
                    count += 1
            except Exception:
                pass
        
        logger.info(f"Warmed {count} items for user {user_id}")
        return count
    
    def _fetch_data_for_key(self, key: str):
        """Fetch data for a cache key from the database."""
        # This is a placeholder - override in subclass or pass custom fetcher
        # Example: instrument_5 -> fetch Instrument.objects.get(pk=5)
        parts = key.split('_')
        if len(parts) < 2:
            return None
        
        model_type = parts[0]
        try:
            obj_id = int(parts[1])
        except (ValueError, IndexError):
            return None
        
        # Import models
        try:
            from qms.models import Instrument, Category, Procedimento
            
            model_map = {
                'instrument': Instrument,
                'categoria': Category,
                'procedimento': Procedimento,
            }
            
            Model = model_map.get(model_type)
            if Model:
                return Model.objects.get(pk=obj_id).__dict__
        
        except Exception as e:
            logger.debug(f"Could not fetch data for {key}: {e}")
        
        return None


# ════════════════════════════════════════════════════════════════
# GLOBAL INSTANCES
# ════════════════════════════════════════════════════════════════

# Global analyzer and warmer instances
access_analyzer = AccessPatternAnalyzer(window_hours=24)
cache_warmer = CacheWarmer(access_analyzer)


# ════════════════════════════════════════════════════════════════
# MONITORING HOOKS
# ════════════════════════════════════════════════════════════════

def record_cache_access(key: str, model_name: str = None, user_id: int = None):
    """
    Record a cache access pattern.
    
    Call this from cache hit/miss monitoring.
    
    Args:
        key: Cache key accessed
        model_name: Model type (e.g., 'Instrument')
        user_id: Accessing user ID
    """
    access_analyzer.record_access(key, model_name, user_id)


def record_api_access(request, view_name: str, model_id: int = None):
    """
    Record API access pattern.
    
    Call from API endpoints to track access.
    
    Args:
        request: Django request object
        view_name: API endpoint name
        model_id: Object ID accessed (optional)
    """
    user_id = request.user.id if request.user.is_authenticated else None
    key = f"{view_name}_{model_id}" if model_id else view_name
    access_analyzer.record_access(key, model_name=view_name, user_id=user_id)


# ════════════════════════════════════════════════════════════════
# CELERY WARMING TASKS
# ════════════════════════════════════════════════════════════════

def get_warming_tasks():
    """
    Get warming task definitions for Celery Beat.
    
    Returns:
        Dict of schedule definitions for celery beat
    
    Example:
        In celery.py:
        
        from qms.cache_warming import get_warming_tasks
        
        app.conf.beat_schedule.update(get_warming_tasks())
    """
    from celery.schedules import crontab
    
    return {
        'cache-warm-hot-items': {
            'task': 'qms.tasks.warm_hot_items',
            'schedule': crontab(minute=0),  # Every hour
        },
        'cache-warm-peak-hour': {
            'task': 'qms.tasks.warm_peak_hour_items',
            'schedule': crontab(minute='*/15'),  # Every 15 minutes
        },
        'cache-warm-off-peak': {
            'task': 'qms.tasks.warm_off_peak_items',
            'schedule': crontab(hour=2, minute=0),  # 2 AM daily
        },
        'cache-warm-user-data': {
            'task': 'qms.tasks.warm_active_user_data',
            'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
        },
    }


# ════════════════════════════════════════════════════════════════
# WARMING STRATEGIES
# ════════════════════════════════════════════════════════════════

class WarmingStrategy:
    """Base class for warming strategies."""
    
    def warm(self, cache_mgr, analyzer: AccessPatternAnalyzer) -> int:
        """Execute warming. Returns number of items warmed."""
        raise NotImplementedError


class HotItemsWarmingStrategy(WarmingStrategy):
    """Warm the hottest items."""
    
    def __init__(self, limit: int = 20):
        self.limit = limit
    
    def warm(self, cache_mgr, analyzer: AccessPatternAnalyzer) -> int:
        warmer = CacheWarmer(analyzer)
        return warmer.warm_hot_items(cache_mgr, top_n=self.limit)


class TimeBasedWarmingStrategy(WarmingStrategy):
    """Warm items based on time of day patterns."""
    
    def warm(self, cache_mgr, analyzer: AccessPatternAnalyzer) -> int:
        current_hour = timezone.now().hour
        warmer = CacheWarmer(analyzer)
        return warmer.warm_by_time_pattern(cache_mgr, current_hour)


class ModelBasedWarmingStrategy(WarmingStrategy):
    """Warm entire models."""
    
    def __init__(self, model_name: str, limit: int = 100):
        self.model_name = model_name
        self.limit = limit
    
    def warm(self, cache_mgr, analyzer: AccessPatternAnalyzer) -> int:
        warmer = CacheWarmer(analyzer)
        return warmer.warm_model_data(self.model_name, cache_mgr, self.limit)


class CompositeWarmingStrategy(WarmingStrategy):
    """Combine multiple warming strategies."""
    
    def __init__(self, strategies: List[WarmingStrategy]):
        self.strategies = strategies
    
    def warm(self, cache_mgr, analyzer: AccessPatternAnalyzer) -> int:
        total = 0
        for strategy in self.strategies:
            try:
                count = strategy.warm(cache_mgr, analyzer)
                total += count
            except Exception as e:
                logger.error(f"Strategy {strategy.__class__.__name__} failed: {e}")
        return total


# ════════════════════════════════════════════════════════════════
# QUICK START
# ════════════════════════════════════════════════════════════════

#
# 1. RECORD ACCESSES
# ==================
# 
# In your view or API endpoint:
#
#     from qms.cache_warming import record_cache_access
#     
#     @api_view(['GET'])
#     def get_instrument(request, pk):
#         # Record access for warming
#         record_cache_access(f"instrument_{pk}", "Instrument", request.user.id)
#         
#         # Get data (cached)
#         return Response(data)
#
#
# 2. SCHEDULE WARMING
# ===================
#
# In your celery.py:
#
#     from qms.cache_warming import get_warming_tasks
#     
#     app.conf.beat_schedule.update(get_warming_tasks())
#
#
# 3. CELERY TASKS
# ===============
#
# In your tasks.py:
#
#     from celery import shared_task
#     from qms.cache_warming import cache_warmer, access_analyzer
#     from config.multilevel_cache import multi_level_cache
#     
#     @shared_task
#     def warm_hot_items():
#         return cache_warmer.warm_hot_items(multi_level_cache, top_n=20)
#
