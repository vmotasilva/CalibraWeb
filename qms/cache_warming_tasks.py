"""
Cache Warming Celery Tasks
===========================

Background tasks for warming the cache with frequently accessed data.

Tasks:
- warm_hot_items: Warm the hottest (most accessed) items
- warm_peak_hour_items: Warm items popular during peak hours
- warm_off_peak_items: Warm cache during low-traffic hours
- warm_active_user_data: Warm data for active users
- analyze_access_patterns: Analyze and log access patterns

Author: Caching Team
Date: 2025-12
"""

import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from django.contrib.auth.models import User

from qms.cache_warming import (
    access_analyzer,
    cache_warmer,
    record_cache_access,
)
from config.multilevel_cache import multi_level_cache
from config.cache_invalidation import smart_ttl

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
# MAIN WARMING TASKS
# ════════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=3)
def warm_hot_items(self, limit: int = 20):
    """
    Warm cache with hot (popular) items.
    
    Runs: Every hour
    
    Args:
        limit: Number of hot items to warm
    
    Returns:
        Number of items warmed
    """
    try:
        logger.info(f"Starting warm_hot_items task (limit={limit})")
        
        count = cache_warmer.warm_hot_items(multi_level_cache, top_n=limit)
        
        logger.info(f"Warmed {count} hot items")
        
        # Log metrics
        stats = access_analyzer.get_stats()
        logger.debug(f"Access analyzer stats: {stats}")
        
        return {
            'status': 'success',
            'items_warmed': count,
            'timestamp': timezone.now().isoformat(),
        }
    
    except Exception as exc:
        logger.error(f"Error in warm_hot_items: {exc}", exc_info=True)
        
        # Retry after 5 minutes
        raise self.retry(exc=exc, countdown=300, max_retries=3)


@shared_task(bind=True, max_retries=3)
def warm_peak_hour_items(self):
    """
    Warm cache with items popular during peak hours.
    
    Runs: Every 15 minutes
    
    Returns:
        Number of items warmed
    """
    try:
        current_hour = timezone.now().hour
        peak_hours = access_analyzer.get_peak_hours()
        
        logger.debug(f"Current hour: {current_hour}, Peak hours: {peak_hours}")
        
        # Only warm if approaching peak hours
        upcoming_peak = any(h == (current_hour + 1) % 24 for h in peak_hours)
        
        if upcoming_peak:
            logger.info(f"Peak hour approaching, warming cache")
            count = cache_warmer.warm_by_time_pattern(multi_level_cache, current_hour)
            
            return {
                'status': 'success',
                'items_warmed': count,
                'peak_hours': peak_hours,
            }
        else:
            return {
                'status': 'skipped',
                'reason': 'no_peak_hour_approaching',
                'peak_hours': peak_hours,
            }
    
    except Exception as exc:
        logger.error(f"Error in warm_peak_hour_items: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=300, max_retries=2)


@shared_task(bind=True, max_retries=3)
def warm_off_peak_items(self):
    """
    Warm entire models during off-peak hours.
    
    This heavy operation runs when traffic is low (e.g., 2-4 AM).
    
    Returns:
        Number of items warmed
    """
    try:
        logger.info("Starting off-peak warming")
        
        off_peak_hours = access_analyzer.get_off_peak_hours()
        current_hour = timezone.now().hour
        
        if current_hour not in off_peak_hours:
            logger.debug(f"Not off-peak (current: {current_hour}, off-peak: {off_peak_hours})")
            return {
                'status': 'skipped',
                'reason': 'not_off_peak',
            }
        
        # Warm all popular models
        total = 0
        
        models = ['Instrument', 'Categoria', 'Procedimento']
        for model_name in models:
            try:
                count = cache_warmer.warm_model_data(
                    model_name,
                    multi_level_cache,
                    limit=50  # Warm top 50 per model
                )
                total += count
                logger.info(f"Warmed {count} items from {model_name}")
            
            except Exception as e:
                logger.warning(f"Could not warm {model_name}: {e}")
        
        logger.info(f"Off-peak warming complete: {total} items")
        
        return {
            'status': 'success',
            'total_items_warmed': total,
            'timestamp': timezone.now().isoformat(),
        }
    
    except Exception as exc:
        logger.error(f"Error in warm_off_peak_items: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=600, max_retries=1)


@shared_task(bind=True, max_retries=2)
def warm_active_user_data(self):
    """
    Warm cache with data for currently active users.
    
    Runs: Every 6 hours
    
    Returns:
        Number of items warmed
    """
    try:
        logger.info("Starting active user warming")
        
        # Get users active in last 30 minutes
        thirty_min_ago = timezone.now() - timedelta(minutes=30)
        active_users = User.objects.filter(
            last_login__gte=thirty_min_ago
        ).values_list('id', flat=True)[:100]  # Limit to 100
        
        total = 0
        for user_id in active_users:
            try:
                count = cache_warmer.warm_user_data(user_id, multi_level_cache)
                total += count
            except Exception as e:
                logger.debug(f"Error warming user {user_id}: {e}")
        
        logger.info(f"Warmed data for {len(active_users)} active users ({total} items)")
        
        return {
            'status': 'success',
            'users_warmed': len(active_users),
            'total_items_warmed': total,
        }
    
    except Exception as exc:
        logger.error(f"Error in warm_active_user_data: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=300, max_retries=2)


# ════════════════════════════════════════════════════════════════
# ANALYSIS & MONITORING TASKS
# ════════════════════════════════════════════════════════════════

@shared_task
def analyze_access_patterns():
    """
    Analyze current access patterns and log statistics.
    
    Runs: Every hour
    
    Returns:
        Access pattern statistics
    """
    try:
        stats = access_analyzer.get_stats()
        
        logger.info(f"Access Pattern Analysis:")
        logger.info(f"  Total patterns: {stats['total_patterns']}")
        logger.info(f"  Hot keys: {stats['hot_keys']}")
        logger.info(f"  Warm keys: {stats['warm_keys']}")
        logger.info(f"  Avg score: {stats['avg_score']:.2f}")
        logger.info(f"  Max score: {stats['max_score']:.2f}")
        logger.info(f"  Peak hours: {stats['peak_hours']}")
        logger.info(f"  Off-peak hours: {stats['off_peak_hours']}")
        
        return {
            'status': 'success',
            'analysis': stats,
        }
    
    except Exception as e:
        logger.error(f"Error analyzing patterns: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
        }


@shared_task
def monitor_warming_effectiveness():
    """
    Monitor cache warming effectiveness.
    
    Compares cache hit rates before/after warming.
    
    Runs: Every 30 minutes
    
    Returns:
        Effectiveness metrics
    """
    try:
        cache_stats = multi_level_cache.get_stats()
        
        l1_hit = cache_stats.get('L1', {}).get('hit_rate', 0)
        l2_hit = cache_stats.get('L2', {}).get('hit_rate', 0)
        l3_hit = cache_stats.get('L3', {}).get('hit_rate', 0)
        
        combined = (l1_hit * 0.3) + (l2_hit * 0.4) + (l3_hit * 0.3)
        
        logger.info(f"Cache Effectiveness:")
        logger.info(f"  L1 hit rate: {l1_hit:.1%}")
        logger.info(f"  L2 hit rate: {l2_hit:.1%}")
        logger.info(f"  L3 hit rate: {l3_hit:.1%}")
        logger.info(f"  Combined: {combined:.1%}")
        
        # Adjust warming if needed
        if combined < 0.80:
            logger.warning("Hit rate below target (80%), increasing warming")
            # Trigger additional warming
            warm_hot_items.delay(limit=50)
        
        return {
            'status': 'success',
            'combined_hit_rate': combined,
            'l1': l1_hit,
            'l2': l2_hit,
            'l3': l3_hit,
        }
    
    except Exception as e:
        logger.error(f"Error monitoring warming: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
        }


@shared_task
def optimize_cache_ttls():
    """
    Optimize cache TTLs based on access and invalidation patterns.
    
    Runs: Daily at 1 AM
    
    Returns:
        TTL optimization results
    """
    try:
        logger.info("Starting TTL optimization")
        
        ttl_stats = smart_ttl.get_stats()
        
        # Get recommendations
        recommendations = []
        
        hot_keys = ttl_stats.get('hot_keys', [])
        if hot_keys:
            recommendations.append(f"Hot keys ({len(hot_keys)}): Increase TTL to 3600s (1h)")
        
        warm_keys = ttl_stats.get('warm_keys', [])
        if warm_keys:
            recommendations.append(f"Warm keys ({len(warm_keys)}): Set TTL to 600s (10m)")
        
        cold_keys = ttl_stats.get('cold_keys', [])
        if cold_keys:
            recommendations.append(f"Cold keys ({len(cold_keys)}): Set TTL to 60s (1m)")
        
        for rec in recommendations:
            logger.info(f"  {rec}")
        
        return {
            'status': 'success',
            'recommendations': recommendations,
            'total_keys': ttl_stats.get('total_keys', 0),
        }
    
    except Exception as e:
        logger.error(f"Error optimizing TTLs: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
        }


@shared_task
def reset_access_patterns():
    """
    Reset access pattern statistics.
    
    Run periodically (daily) to capture fresh patterns.
    
    Runs: Daily at 1 AM
    
    Returns:
        Reset confirmation
    """
    try:
        logger.info("Resetting access patterns")
        access_analyzer.reset()
        
        return {
            'status': 'success',
            'message': 'Access patterns reset',
        }
    
    except Exception as e:
        logger.error(f"Error resetting patterns: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
        }


# ════════════════════════════════════════════════════════════════
# WARM ON DEMAND
# ════════════════════════════════════════════════════════════════

@shared_task
def warm_model_on_demand(model_name: str, limit: int = 100):
    """
    Warm a specific model's cache on demand.
    
    Args:
        model_name: Model to warm (e.g., 'Instrument')
        limit: Number of instances to warm
    
    Returns:
        Warming result
    """
    try:
        logger.info(f"On-demand warming for {model_name}")
        count = cache_warmer.warm_model_data(model_name, multi_level_cache, limit)
        
        return {
            'status': 'success',
            'model': model_name,
            'items_warmed': count,
        }
    
    except Exception as e:
        logger.error(f"Error warming {model_name}: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
        }


@shared_task
def warm_user_data_on_demand(user_id: int):
    """
    Warm cache for a specific user on demand.
    
    Args:
        user_id: User ID to warm for
    
    Returns:
        Warming result
    """
    try:
        logger.info(f"On-demand warming for user {user_id}")
        count = cache_warmer.warm_user_data(user_id, multi_level_cache)
        
        return {
            'status': 'success',
            'user_id': user_id,
            'items_warmed': count,
        }
    
    except Exception as e:
        logger.error(f"Error warming user {user_id}: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
        }


# ════════════════════════════════════════════════════════════════
# CELERY BEAT SCHEDULE REGISTRATION
# ════════════════════════════════════════════════════════════════

def get_warming_beat_schedule():
    """
    Get Celery Beat schedule for warming tasks.
    
    Usage in celery.py:
        from celery.schedules import crontab
        from qms.cache_warming_tasks import get_warming_beat_schedule
        
        app.conf.beat_schedule.update(get_warming_beat_schedule())
    """
    from celery.schedules import crontab
    
    return {
        # Main warming tasks
        'cache-warm-hot-items': {
            'task': 'qms.cache_warming_tasks.warm_hot_items',
            'schedule': crontab(minute=0),  # Every hour
            'options': {'queue': 'cache_warming'},
        },
        
        'cache-warm-peak-hour': {
            'task': 'qms.cache_warming_tasks.warm_peak_hour_items',
            'schedule': crontab(minute='*/15'),  # Every 15 minutes
            'options': {'queue': 'cache_warming'},
        },
        
        'cache-warm-off-peak': {
            'task': 'qms.cache_warming_tasks.warm_off_peak_items',
            'schedule': crontab(hour=2, minute=0),  # 2 AM daily
            'options': {'queue': 'cache_warming'},
        },
        
        'cache-warm-active-users': {
            'task': 'qms.cache_warming_tasks.warm_active_user_data',
            'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
            'options': {'queue': 'cache_warming'},
        },
        
        # Analysis & monitoring
        'cache-analyze-patterns': {
            'task': 'qms.cache_warming_tasks.analyze_access_patterns',
            'schedule': crontab(minute=0),  # Every hour
            'options': {'queue': 'cache_monitoring'},
        },
        
        'cache-monitor-effectiveness': {
            'task': 'qms.cache_warming_tasks.monitor_warming_effectiveness',
            'schedule': crontab(minute='*/30'),  # Every 30 minutes
            'options': {'queue': 'cache_monitoring'},
        },
        
        'cache-optimize-ttls': {
            'task': 'qms.cache_warming_tasks.optimize_cache_ttls',
            'schedule': crontab(hour=1, minute=0),  # Daily at 1 AM
            'options': {'queue': 'cache_optimization'},
        },
        
        'cache-reset-patterns': {
            'task': 'qms.cache_warming_tasks.reset_access_patterns',
            'schedule': crontab(hour=1, minute=30),  # Daily at 1:30 AM
            'options': {'queue': 'cache_optimization'},
        },
    }
