"""
Cache Dashboard & Real-time Monitoring
=======================================

Real-time cache metrics and monitoring dashboard.

Features:
- Real-time cache statistics collection
- WebSocket support for live updates
- Performance metrics visualization
- Alert system for cache issues
- Historical data tracking

Author: Caching Team
Date: 2025-12
"""

import logging
import json
from datetime import datetime, timedelta
from collections import deque
from django.utils import timezone
from django.core.cache import cache as django_cache

from config.multilevel_cache import multi_level_cache
from config.cache_invalidation import smart_ttl, dependency_tracker
from qms.cache_warming import access_analyzer

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
# METRICS COLLECTOR
# ════════════════════════════════════════════════════════════════

class CacheMetrics:
    """Single snapshot of cache metrics."""
    
    def __init__(self):
        self.timestamp = timezone.now()
        self.l1_stats = {}
        self.l2_stats = {}
        self.l3_stats = {}
        self.system_stats = {}
        self.alerts = []
    
    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'l1': self.l1_stats,
            'l2': self.l2_stats,
            'l3': self.l3_stats,
            'system': self.system_stats,
            'alerts': self.alerts,
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class MetricsCollector:
    """Collects and stores cache metrics over time."""
    
    def __init__(self, max_history: int = 1440):  # 24 hours of 1-min samples
        self.max_history = max_history
        self.metrics_history = deque(maxlen=max_history)
        self.last_collection = None
    
    def collect(self) -> CacheMetrics:
        """Collect current cache metrics."""
        metrics = CacheMetrics()
        
        try:
            # Get cache stats
            cache_stats = multi_level_cache.get_stats()
            
            metrics.l1_stats = cache_stats.get('L1', {})
            metrics.l2_stats = cache_stats.get('L2', {})
            metrics.l3_stats = cache_stats.get('L3', {})
            
            # Calculate combined stats
            metrics.system_stats = self._calculate_system_stats(cache_stats)
            
            # Check for alerts
            metrics.alerts = self._check_alerts(metrics)
            
            # Store in history
            self.metrics_history.append(metrics)
            self.last_collection = timezone.now()
            
            logger.debug(f"Collected metrics: {metrics.system_stats}")
            
            return metrics
        
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}", exc_info=True)
            return metrics
    
    def _calculate_system_stats(self, cache_stats: dict) -> dict:
        """Calculate system-level statistics."""
        l1_hit = cache_stats.get('L1', {}).get('hit_rate', 0)
        l2_hit = cache_stats.get('L2', {}).get('hit_rate', 0)
        l3_hit = cache_stats.get('L3', {}).get('hit_rate', 0)
        
        # Weighted average
        combined_hit = (l1_hit * 0.3) + (l2_hit * 0.4) + (l3_hit * 0.3)
        
        return {
            'combined_hit_rate': round(combined_hit, 3),
            'l1_hit_rate': round(l1_hit, 3),
            'l2_hit_rate': round(l2_hit, 3),
            'l3_hit_rate': round(l3_hit, 3),
            'total_hits': cache_stats.get('L3', {}).get('hits', 0),
            'total_misses': cache_stats.get('L3', {}).get('misses', 0),
            'cache_size': cache_stats.get('L3', {}).get('size', 0),
            'memory_usage': cache_stats.get('L3', {}).get('memory', 0),
        }
    
    def _check_alerts(self, metrics: CacheMetrics) -> list:
        """Check for alertable conditions."""
        alerts = []
        
        combined_hit = metrics.system_stats.get('combined_hit_rate', 0)
        if combined_hit < 0.70:
            alerts.append({
                'severity': 'warning',
                'message': f'Low cache hit rate: {combined_hit:.1%} (target: 80%+)',
                'type': 'low_hit_rate',
            })
        
        l1_hit = metrics.l1_stats.get('hit_rate', 0)
        if l1_hit < 0.20:
            alerts.append({
                'severity': 'info',
                'message': f'L1 cache underutilized: {l1_hit:.1%}',
                'type': 'l1_low',
            })
        
        memory = metrics.system_stats.get('memory_usage', 0)
        if memory > 8000:  # 8GB threshold
            alerts.append({
                'severity': 'critical',
                'message': f'High memory usage: {memory/1024:.1f}GB',
                'type': 'high_memory',
            })
        
        return alerts
    
    def get_history(self, minutes: int = 60) -> list:
        """Get metric history for last N minutes."""
        if not self.metrics_history:
            return []
        
        cutoff_time = timezone.now() - timedelta(minutes=minutes)
        return [
            m.to_dict()
            for m in self.metrics_history
            if m.timestamp >= cutoff_time
        ]
    
    def get_latest(self) -> dict:
        """Get latest metrics."""
        if not self.metrics_history:
            return {}
        return self.metrics_history[-1].to_dict()
    
    def get_averages(self, minutes: int = 60) -> dict:
        """Get average metrics over time period."""
        history = self.get_history(minutes)
        
        if not history:
            return {}
        
        # Calculate averages
        hit_rates = [m['system']['combined_hit_rate'] for m in history]
        l1_rates = [m['l1'].get('hit_rate', 0) for m in history]
        l2_rates = [m['l2'].get('hit_rate', 0) for m in history]
        l3_rates = [m['l3'].get('hit_rate', 0) for m in history]
        
        return {
            'combined_hit_rate': round(sum(hit_rates) / len(hit_rates), 3),
            'l1_hit_rate': round(sum(l1_rates) / len(l1_rates), 3),
            'l2_hit_rate': round(sum(l2_rates) / len(l2_rates), 3),
            'l3_hit_rate': round(sum(l3_rates) / len(l3_rates), 3),
            'sample_count': len(history),
            'period_minutes': minutes,
        }
    
    def get_trends(self, minutes: int = 60) -> dict:
        """Get trend analysis (improving/declining)."""
        history = self.get_history(minutes)
        
        if len(history) < 2:
            return {'status': 'insufficient_data'}
        
        # Split into first and second half
        mid = len(history) // 2
        first_half = history[:mid]
        second_half = history[mid:]
        
        first_avg = sum(m['system']['combined_hit_rate'] for m in first_half) / len(first_half)
        second_avg = sum(m['system']['combined_hit_rate'] for m in second_half) / len(second_half)
        
        change = second_avg - first_avg
        trend = 'improving' if change > 0.01 else 'declining' if change < -0.01 else 'stable'
        
        return {
            'trend': trend,
            'change': round(change, 3),
            'first_half_avg': round(first_avg, 3),
            'second_half_avg': round(second_avg, 3),
        }


# ════════════════════════════════════════════════════════════════
# GLOBAL COLLECTOR
# ════════════════════════════════════════════════════════════════

metrics_collector = MetricsCollector()


# ════════════════════════════════════════════════════════════════
# DASHBOARD DATA PROVIDER
# ════════════════════════════════════════════════════════════════

class DashboardDataProvider:
    """Provides all data needed for the dashboard."""
    
    def __init__(self):
        self.collector = metrics_collector
    
    def get_dashboard_data(self) -> dict:
        """Get all dashboard data."""
        return {
            'timestamp': timezone.now().isoformat(),
            'current_metrics': self.collector.get_latest(),
            'hourly_averages': self.collector.get_averages(minutes=60),
            'daily_averages': self.collector.get_averages(minutes=1440),
            'trends': self.collector.get_trends(minutes=60),
            'access_patterns': self._get_access_patterns(),
            'hot_keys': self._get_hot_keys(),
            'cache_health': self._get_cache_health(),
            'invalidation_stats': self._get_invalidation_stats(),
        }
    
    def _get_access_patterns(self) -> dict:
        """Get access pattern information."""
        stats = access_analyzer.get_stats()
        
        return {
            'total_keys': stats.get('total_keys', 0),
            'hot_keys_count': stats.get('hot_keys', 0),
            'warm_keys_count': stats.get('warm_keys', 0),
            'peak_hours': stats.get('peak_hours', []),
            'off_peak_hours': stats.get('off_peak_hours', []),
            'avg_score': round(stats.get('avg_score', 0), 2),
            'max_score': round(stats.get('max_score', 0), 2),
        }
    
    def _get_hot_keys(self, limit: int = 10) -> list:
        """Get top hot keys."""
        hot_keys = access_analyzer.get_hot_keys(limit=limit)
        
        return [
            {
                'key': key,
                'score': round(access_analyzer.patterns[key].score, 1),
                'accesses': access_analyzer.patterns[key].access_count,
                'users': len(access_analyzer.patterns[key].unique_users),
            }
            for key in hot_keys
            if key in access_analyzer.patterns
        ]
    
    def _get_cache_health(self) -> dict:
        """Assess overall cache health."""
        metrics = self.collector.get_latest()
        hit_rate = metrics.get('system', {}).get('combined_hit_rate', 0)
        
        if hit_rate >= 0.85:
            health = 'excellent'
            status = '🟢 Excellent'
        elif hit_rate >= 0.75:
            health = 'good'
            status = '🟡 Good'
        elif hit_rate >= 0.60:
            health = 'acceptable'
            status = '🟠 Acceptable'
        else:
            health = 'poor'
            status = '🔴 Poor'
        
        return {
            'health': health,
            'status': status,
            'hit_rate': hit_rate,
            'recommendation': self._get_health_recommendation(health),
        }
    
    def _get_health_recommendation(self, health: str) -> str:
        """Get recommendation based on health."""
        recommendations = {
            'excellent': 'Cache is performing well. Continue current strategy.',
            'good': 'Cache is good. Monitor for any degradation.',
            'acceptable': 'Cache needs optimization. Consider increasing L2/L3 sizes.',
            'poor': 'Cache needs urgent attention. Check invalidation and warming strategies.',
        }
        return recommendations.get(health, 'Unknown')
    
    def _get_invalidation_stats(self) -> dict:
        """Get invalidation statistics."""
        try:
            ttl_stats = smart_ttl.get_stats()
            
            return {
                'total_keys': ttl_stats.get('total_keys', 0),
                'total_accesses': ttl_stats.get('total_accesses', 0),
                'total_invalidations': ttl_stats.get('total_invalidations', 0),
                'model_dependencies': len(dependency_tracker.dependencies),
                'registered_callbacks': len(dependency_tracker.callbacks),
            }
        except Exception:
            return {}
    
    def get_performance_summary(self) -> dict:
        """Get performance summary for quick overview."""
        metrics = self.collector.get_latest()
        hourly = self.collector.get_averages(60)
        
        return {
            'cache_hit_rate': round(metrics.get('system', {}).get('combined_hit_rate', 0) * 100, 1),
            'l1_efficiency': round(metrics.get('l1', {}).get('hit_rate', 0) * 100, 1),
            'l2_efficiency': round(metrics.get('l2', {}).get('hit_rate', 0) * 100, 1),
            'l3_efficiency': round(metrics.get('l3', {}).get('hit_rate', 0) * 100, 1),
            'memory_used_gb': round(metrics.get('system', {}).get('memory_usage', 0) / 1024, 1),
            'items_cached': metrics.get('system', {}).get('cache_size', 0),
            'hourly_trend': self.collector.get_trends(60).get('trend', 'unknown'),
        }


# ════════════════════════════════════════════════════════════════
# CELERY TASK FOR PERIODIC COLLECTION
# ════════════════════════════════════════════════════════════════

def get_metrics_collection_task():
    """Get the metrics collection Celery task."""
    from celery import shared_task
    
    @shared_task
    def collect_cache_metrics():
        """Collect metrics periodically for dashboard."""
        try:
            metrics = metrics_collector.collect()
            logger.debug(f"Collected metrics: {metrics.system_stats}")
            
            # Store in cache for quick access
            django_cache.set(
                'cache_dashboard_latest',
                metrics.to_dict(),
                timeout=300  # 5 minutes
            )
            
            return {
                'status': 'success',
                'timestamp': metrics.timestamp.isoformat(),
                'hit_rate': metrics.system_stats.get('combined_hit_rate', 0),
            }
        
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e),
            }
    
    return collect_cache_metrics


# ════════════════════════════════════════════════════════════════
# WEBSOCKET SUPPORT
# ════════════════════════════════════════════════════════════════

class DashboardWebSocketHandler:
    """Handles WebSocket connections for live dashboard updates."""
    
    connected_clients = set()
    
    @classmethod
    def register(cls, client):
        """Register a WebSocket client."""
        cls.connected_clients.add(client)
        logger.debug(f"Client connected. Total: {len(cls.connected_clients)}")
    
    @classmethod
    def unregister(cls, client):
        """Unregister a WebSocket client."""
        cls.connected_clients.discard(client)
        logger.debug(f"Client disconnected. Total: {len(cls.connected_clients)}")
    
    @classmethod
    def broadcast_metrics(cls):
        """Broadcast metrics to all connected clients."""
        if not cls.connected_clients:
            return
        
        provider = DashboardDataProvider()
        data = provider.get_dashboard_data()
        
        for client in cls.connected_clients:
            try:
                client.send_json(data)
            except Exception as e:
                logger.error(f"Error sending to client: {e}")
                cls.unregister(client)


# ════════════════════════════════════════════════════════════════
# ALERTS SYSTEM
# ════════════════════════════════════════════════════════════════

class CacheAlertManager:
    """Manages cache-related alerts."""
    
    SEVERITY_LEVELS = {
        'critical': 0,
        'warning': 1,
        'info': 2,
    }
    
    def __init__(self):
        self.alerts = deque(maxlen=100)
        self.muted_alerts = set()
    
    def check_and_create_alerts(self):
        """Check metrics and create alerts if needed."""
        metrics = metrics_collector.get_latest()
        
        # Check combined hit rate
        combined = metrics.get('system', {}).get('combined_hit_rate', 0)
        if combined < 0.70:
            self._create_alert(
                'low_hit_rate',
                'warning',
                f'Cache hit rate below target: {combined:.1%}'
            )
        
        # Check L1 efficiency
        l1_hit = metrics.get('l1', {}).get('hit_rate', 0)
        if l1_hit < 0.10:
            self._create_alert(
                'l1_inefficient',
                'info',
                f'L1 cache underutilized: {l1_hit:.1%}'
            )
        
        # Check memory
        memory = metrics.get('system', {}).get('memory_usage', 0)
        if memory > 8000:
            self._create_alert(
                'high_memory',
                'critical',
                f'Cache memory usage high: {memory/1024:.1f}GB'
            )
    
    def _create_alert(self, alert_type: str, severity: str, message: str):
        """Create an alert if not muted."""
        if alert_type not in self.muted_alerts:
            alert = {
                'type': alert_type,
                'severity': severity,
                'message': message,
                'timestamp': timezone.now().isoformat(),
            }
            self.alerts.append(alert)
            logger.warning(f"Alert [{severity}]: {message}")
    
    def get_alerts(self, severity: str = None) -> list:
        """Get alerts, optionally filtered by severity."""
        if severity:
            return [a for a in self.alerts if a['severity'] == severity]
        return list(self.alerts)
    
    def mute_alert(self, alert_type: str):
        """Mute an alert type."""
        self.muted_alerts.add(alert_type)
    
    def unmute_alert(self, alert_type: str):
        """Unmute an alert type."""
        self.muted_alerts.discard(alert_type)


# ════════════════════════════════════════════════════════════════
# GLOBAL ALERT MANAGER
# ════════════════════════════════════════════════════════════════

alert_manager = CacheAlertManager()


# ════════════════════════════════════════════════════════════════
# QUICK START
# ════════════════════════════════════════════════════════════════

#
# 1. DASHBOARD VIEW
# =================
#
# In your views.py:
#
#     from django.shortcuts import render
#     from qms.cache_dashboard import DashboardDataProvider
#     
#     def cache_dashboard(request):
#         provider = DashboardDataProvider()
#         context = {
#             'dashboard_data': provider.get_dashboard_data(),
#             'performance_summary': provider.get_performance_summary(),
#         }
#         return render(request, 'cache_dashboard.html', context)
#
#
# 2. API ENDPOINTS
# ================
#
# In your API:
#
#     from rest_framework.decorators import api_view
#     from rest_framework.response import Response
#     from qms.cache_dashboard import DashboardDataProvider, metrics_collector
#     
#     @api_view(['GET'])
#     def api_cache_metrics(request):
#         provider = DashboardDataProvider()
#         return Response(provider.get_dashboard_data())
#     
#     @api_view(['GET'])
#     def api_cache_history(request):
#         minutes = request.query_params.get('minutes', 60, type=int)
#         history = metrics_collector.get_history(minutes)
#         return Response(history)
#
#
# 3. CELERY BEAT SCHEDULE
# =======================
#
# In celery.py:
#
#     from celery.schedules import crontab
#     from qms.cache_dashboard import get_metrics_collection_task
#     
#     collect_metrics_task = get_metrics_collection_task()
#     
#     app.conf.beat_schedule.update({
#         'collect-cache-metrics': {
#             'task': 'qms.tasks.collect_cache_metrics',
#             'schedule': crontab(minute='*'),  # Every minute
#         },
#     })
#
