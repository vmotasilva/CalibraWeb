"""
Monitoring and Profiling Configuration
========================================

Comprehensive monitoring setup for Django + Celery with:
1. Django Debug Toolbar (development)
2. Silk APM (production)
3. Custom performance profiling
4. Real-time metrics collection
5. Alerting system

Author: Performance Monitoring Team
Date: 2025-12
"""

import logging
import os
from typing import Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
# PERFORMANCE THRESHOLDS
# ════════════════════════════════════════════════════════════════


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class PerformanceThresholds:
    """Define acceptable performance thresholds for various operations."""

    # ────────────────────────────────────────────────────────────
    # REQUEST LATENCY THRESHOLDS (milliseconds)
    # ────────────────────────────────────────────────────────────

    # HTTP request duration thresholds
    REQUEST_LATENCY_THRESHOLD_GOOD = 100  # < 100ms is good
    REQUEST_LATENCY_THRESHOLD_WARNING = 300  # 100-300ms is warning
    REQUEST_LATENCY_THRESHOLD_CRITICAL = 1000  # > 1000ms is critical

    # ────────────────────────────────────────────────────────────
    # DATABASE QUERY THRESHOLDS (milliseconds)
    # ────────────────────────────────────────────────────────────

    # Individual query execution time
    QUERY_LATENCY_THRESHOLD_GOOD = 10  # < 10ms is good
    QUERY_LATENCY_THRESHOLD_WARNING = 50  # 10-50ms is warning
    QUERY_LATENCY_THRESHOLD_CRITICAL = 500  # > 500ms is critical

    # Number of queries per request
    QUERY_COUNT_THRESHOLD_GOOD = 5  # < 5 queries is good
    QUERY_COUNT_THRESHOLD_WARNING = 20  # 5-20 queries is warning
    QUERY_COUNT_THRESHOLD_CRITICAL = 50  # > 50 queries is critical

    # ────────────────────────────────────────────────────────────
    # CELERY TASK THRESHOLDS (milliseconds)
    # ────────────────────────────────────────────────────────────

    # Task execution duration
    CELERY_TASK_DURATION_GOOD = 1000  # < 1s is good
    CELERY_TASK_DURATION_WARNING = 5000  # 1-5s is warning
    CELERY_TASK_DURATION_CRITICAL = 30000  # > 30s is critical

    # Task failure rate
    CELERY_FAILURE_RATE_THRESHOLD = 0.05  # Alert if > 5% failures

    # ────────────────────────────────────────────────────────────
    # CACHE PERFORMANCE THRESHOLDS
    # ────────────────────────────────────────────────────────────

    # Cache hit rate
    CACHE_HIT_RATE_THRESHOLD_GOOD = 0.70  # > 70% is good
    CACHE_HIT_RATE_THRESHOLD_WARNING = 0.50  # 50-70% is warning
    CACHE_HIT_RATE_THRESHOLD_CRITICAL = 0.30  # < 30% is critical

    # ────────────────────────────────────────────────────────────
    # RESOURCE UTILIZATION THRESHOLDS
    # ────────────────────────────────────────────────────────────

    # CPU usage percentage
    CPU_USAGE_THRESHOLD_WARNING = 70
    CPU_USAGE_THRESHOLD_CRITICAL = 90

    # Memory usage percentage
    MEMORY_USAGE_THRESHOLD_WARNING = 75
    MEMORY_USAGE_THRESHOLD_CRITICAL = 90

    # Database connection pool utilization
    DB_POOL_UTILIZATION_THRESHOLD_WARNING = 0.80  # 80%
    DB_POOL_UTILIZATION_THRESHOLD_CRITICAL = 0.95  # 95%

    # ────────────────────────────────────────────────────────────
    # ERROR RATE THRESHOLDS
    # ────────────────────────────────────────────────────────────

    # HTTP error rate
    HTTP_ERROR_RATE_THRESHOLD = 0.01  # Alert if > 1% errors

    # Database error rate
    DB_ERROR_RATE_THRESHOLD = 0.001  # Alert if > 0.1% errors

    # ────────────────────────────────────────────────────────────
    # COLLECTOR SETTINGS
    # ────────────────────────────────────────────────────────────

    # Sampling rate for detailed profiling (0.0-1.0)
    # 1.0 = profile every request (high overhead)
    # 0.1 = profile 10% of requests (recommended for production)
    PROFILING_SAMPLE_RATE = os.environ.get("PROFILING_SAMPLE_RATE", "0.1")

    # Retention period for metrics (days)
    METRICS_RETENTION_DAYS = int(os.environ.get("METRICS_RETENTION_DAYS", "30"))

    # Batch size for metrics collection
    METRICS_BATCH_SIZE = 1000


class MonitoringConfig:
    """Central monitoring configuration."""

    # ────────────────────────────────────────────────────────────
    # DEBUG TOOLBAR (DEVELOPMENT)
    # ────────────────────────────────────────────────────────────

    # Enable Django Debug Toolbar in development
    DEBUG_TOOLBAR_ENABLED = os.environ.get("DEBUG_TOOLBAR_ENABLED", "True").lower() == "true"

    # Debug Toolbar settings
    DEBUG_TOOLBAR_CONFIG = {
        "SHOW_TOOLBAR_CALLBACK": lambda r: DEBUG_TOOLBAR_ENABLED,
        "SHOW_TEMPLATE_CONTEXT": True,
        "ENABLE_STACKTRACES": True,
        "SQL_WARNING_THRESHOLD": 500,  # ms
        "SHOW_CACHE": True,
        "SHOW_PROFILING": True,
        "PROFILING_DEPTH": 10,
        "PRETTIFY_SQL": True,
        "SKIP_TEMPLATE_PREFIXES": (
            "django/forms/widgets/",
            "admin/widgets/",
        ),
    }

    # ────────────────────────────────────────────────────────────
    # SILK APM (PRODUCTION)
    # ────────────────────────────────────────────────────────────

    # Enable Silk APM for production profiling
    SILK_ENABLED = os.environ.get("SILK_ENABLED", "False").lower() == "true"

    # Silk configuration
    SILK_CONFIG = {
        # Only profile a percentage of requests (reduce overhead)
        "SILKY_PYTHON_PROFILER_RESULT_PER_PAGE": 100,
        # Hide Silk UI from URL
        "SILKY_HIDE_DOWNLOADABLE_PROFILING": True,
        # Record queries
        "SILKY_INTERCEPT_PERCENT": int(os.environ.get("SILK_INTERCEPT_PERCENT", "10")),
        # Authenticated users only
        "SILKY_AUTHENTICATION": True,
        "SILKY_AUTHORISATION": True,
        # Meta config
        "SILKY_LOG_QUERIES": True,
        "SILKY_LOG_KWARGS": True,
        # Ignore static files
        "SILKY_IGNORE_PATHS": (
            "/static/",
            "/media/",
        ),
    }

    # ────────────────────────────────────────────────────────────
    # PROMETHEUS METRICS (OPTIONAL)
    # ────────────────────────────────────────────────────────────

    # Enable Prometheus metrics collection
    PROMETHEUS_ENABLED = os.environ.get("PROMETHEUS_ENABLED", "False").lower() == "true"

    # Prometheus configuration
    PROMETHEUS_CONFIG = {
        "PROMETHEUS_ENDPOINT": "/metrics/",
        "PROMETHEUS_METRICS_PORT": int(os.environ.get("PROMETHEUS_METRICS_PORT", "8001")),
    }

    # ────────────────────────────────────────────────────────────
    # CUSTOM METRICS COLLECTION
    # ────────────────────────────────────────────────────────────

    # Enable custom metrics collection
    CUSTOM_METRICS_ENABLED = os.environ.get("CUSTOM_METRICS_ENABLED", "True").lower() == "true"

    # Metrics to collect
    COLLECT_REQUEST_METRICS = True
    COLLECT_DATABASE_METRICS = True
    COLLECT_CACHE_METRICS = True
    COLLECT_CELERY_METRICS = True
    COLLECT_RESOURCE_METRICS = True  # CPU, memory, disk

    # ────────────────────────────────────────────────────────────
    # LOGGING CONFIGURATION
    # ────────────────────────────────────────────────────────────

    # Log slow queries
    LOG_SLOW_QUERIES = os.environ.get("LOG_SLOW_QUERIES", "True").lower() == "true"
    SLOW_QUERY_THRESHOLD = int(os.environ.get("SLOW_QUERY_THRESHOLD", "500"))  # ms

    # Log slow requests
    LOG_SLOW_REQUESTS = os.environ.get("LOG_SLOW_REQUESTS", "True").lower() == "true"
    SLOW_REQUEST_THRESHOLD = int(os.environ.get("SLOW_REQUEST_THRESHOLD", "1000"))  # ms

    # Log slow Celery tasks
    LOG_SLOW_TASKS = os.environ.get("LOG_SLOW_TASKS", "True").lower() == "true"
    SLOW_TASK_THRESHOLD = int(os.environ.get("SLOW_TASK_THRESHOLD", "5000"))  # ms

    # ────────────────────────────────────────────────────────────
    # ALERTING CONFIGURATION
    # ────────────────────────────────────────────────────────────

    # Enable alerting system
    ALERTING_ENABLED = os.environ.get("ALERTING_ENABLED", "False").lower() == "true"

    # Alert channels
    ALERT_EMAIL_ENABLED = os.environ.get("ALERT_EMAIL_ENABLED", "False").lower() == "true"
    ALERT_SLACK_ENABLED = os.environ.get("ALERT_SLACK_ENABLED", "False").lower() == "true"

    # Email alerts
    ALERT_EMAIL_TO = os.environ.get("ALERT_EMAIL_TO", "admin@example.com").split(",")
    ALERT_EMAIL_FROM = os.environ.get("ALERT_EMAIL_FROM", "monitoring@example.com")

    # Slack alerts
    ALERT_SLACK_WEBHOOK = os.environ.get("ALERT_SLACK_WEBHOOK")
    ALERT_SLACK_CHANNEL = os.environ.get("ALERT_SLACK_CHANNEL", "#alerts")

    # ────────────────────────────────────────────────────────────
    # STORAGE CONFIGURATION
    # ────────────────────────────────────────────────────────────

    # Where to store metrics
    METRICS_STORAGE = os.environ.get("METRICS_STORAGE", "database")  # database, redis, influxdb

    # InfluxDB settings (if using InfluxDB)
    INFLUXDB_ENABLED = os.environ.get("INFLUXDB_ENABLED", "False").lower() == "true"
    INFLUXDB_HOST = os.environ.get("INFLUXDB_HOST", "localhost")
    INFLUXDB_PORT = int(os.environ.get("INFLUXDB_PORT", "8086"))
    INFLUXDB_DATABASE = os.environ.get("INFLUXDB_DATABASE", "calibra")
    INFLUXDB_USERNAME = os.environ.get("INFLUXDB_USERNAME", "")
    INFLUXDB_PASSWORD = os.environ.get("INFLUXDB_PASSWORD", "")


class PerformanceMonitor:
    """
    Main performance monitoring class.

    Tracks request, database, cache, and Celery task performance.
    """

    def __init__(self):
        """Initialize performance monitor."""
        self.logger = logging.getLogger("calibra.monitoring")
        self.config = MonitoringConfig()
        self.thresholds = PerformanceThresholds()

    def check_request_performance(self, duration_ms: float) -> tuple[AlertLevel, Optional[str]]:
        """
        Check request performance against thresholds.

        Args:
            duration_ms: Request duration in milliseconds

        Returns:
            (alert_level, message)
        """
        if duration_ms < self.thresholds.REQUEST_LATENCY_THRESHOLD_GOOD:
            return AlertLevel.INFO, f"Good request latency: {duration_ms:.1f}ms"

        if duration_ms < self.thresholds.REQUEST_LATENCY_THRESHOLD_WARNING:
            return AlertLevel.INFO, f"Normal request latency: {duration_ms:.1f}ms"

        if duration_ms < self.thresholds.REQUEST_LATENCY_THRESHOLD_CRITICAL:
            return AlertLevel.WARNING, f"Slow request: {duration_ms:.1f}ms (threshold: {self.thresholds.REQUEST_LATENCY_THRESHOLD_WARNING}ms)"

        return AlertLevel.CRITICAL, f"Very slow request: {duration_ms:.1f}ms (threshold: {self.thresholds.REQUEST_LATENCY_THRESHOLD_CRITICAL}ms)"

    def check_query_performance(self, duration_ms: float) -> tuple[AlertLevel, Optional[str]]:
        """
        Check query performance.

        Args:
            duration_ms: Query duration in milliseconds

        Returns:
            (alert_level, message)
        """
        if duration_ms < self.thresholds.QUERY_LATENCY_THRESHOLD_GOOD:
            return AlertLevel.INFO, None

        if duration_ms < self.thresholds.QUERY_LATENCY_THRESHOLD_WARNING:
            return AlertLevel.INFO, None

        if duration_ms < self.thresholds.QUERY_LATENCY_THRESHOLD_CRITICAL:
            return AlertLevel.WARNING, f"Slow query: {duration_ms:.1f}ms"

        return AlertLevel.CRITICAL, f"Very slow query: {duration_ms:.1f}ms"

    def check_celery_task_performance(self, duration_ms: float) -> tuple[AlertLevel, Optional[str]]:
        """
        Check Celery task performance.

        Args:
            duration_ms: Task duration in milliseconds

        Returns:
            (alert_level, message)
        """
        if duration_ms < self.thresholds.CELERY_TASK_DURATION_GOOD:
            return AlertLevel.INFO, None

        if duration_ms < self.thresholds.CELERY_TASK_DURATION_WARNING:
            return AlertLevel.INFO, None

        if duration_ms < self.thresholds.CELERY_TASK_DURATION_CRITICAL:
            return AlertLevel.WARNING, f"Slow task: {duration_ms:.1f}ms"

        return AlertLevel.CRITICAL, f"Very slow task: {duration_ms:.1f}ms"

    def get_diagnostic_report(self) -> Dict[str, Any]:
        """
        Generate diagnostic report with current metrics.

        Returns:
            Dictionary with performance metrics and recommendations
        """
        return {
            "timestamp": None,  # Will be set by caller
            "request_metrics": None,
            "database_metrics": None,
            "cache_metrics": None,
            "celery_metrics": None,
            "resource_metrics": None,
            "alerts": [],
            "recommendations": [],
        }


# ════════════════════════════════════════════════════════════════
# DJANGO DEBUG TOOLBAR SETUP
# ════════════════════════════════════════════════════════════════


def get_debug_toolbar_config() -> Dict[str, Any]:
    """Get Django Debug Toolbar configuration for settings.py."""
    if not MonitoringConfig.DEBUG_TOOLBAR_ENABLED:
        return {}

    return {
        "DEBUG_TOOLBAR": {
            "SHOW_TOOLBAR_CALLBACK": MonitoringConfig.DEBUG_TOOLBAR_CONFIG["SHOW_TOOLBAR_CALLBACK"],
            "SHOW_TEMPLATE_CONTEXT": MonitoringConfig.DEBUG_TOOLBAR_CONFIG["SHOW_TEMPLATE_CONTEXT"],
            "ENABLE_STACKTRACES": MonitoringConfig.DEBUG_TOOLBAR_CONFIG["ENABLE_STACKTRACES"],
            "SQL_WARNING_THRESHOLD": MonitoringConfig.DEBUG_TOOLBAR_CONFIG["SQL_WARNING_THRESHOLD"],
            "SHOW_CACHE": MonitoringConfig.DEBUG_TOOLBAR_CONFIG["SHOW_CACHE"],
            "SHOW_PROFILING": MonitoringConfig.DEBUG_TOOLBAR_CONFIG["SHOW_PROFILING"],
        }
    }


# ════════════════════════════════════════════════════════════════
# SILK APM SETUP
# ════════════════════════════════════════════════════════════════


def get_silk_config() -> Dict[str, Any]:
    """Get Silk APM configuration for settings.py."""
    if not MonitoringConfig.SILK_ENABLED:
        return {}

    return {
        "SILKY_PYTHON_PROFILER_RESULT_PER_PAGE": MonitoringConfig.SILK_CONFIG["SILKY_PYTHON_PROFILER_RESULT_PER_PAGE"],
        "SILKY_HIDE_DOWNLOADABLE_PROFILING": MonitoringConfig.SILK_CONFIG["SILKY_HIDE_DOWNLOADABLE_PROFILING"],
        "SILKY_INTERCEPT_PERCENT": MonitoringConfig.SILK_CONFIG["SILKY_INTERCEPT_PERCENT"],
        "SILKY_AUTHENTICATION": MonitoringConfig.SILK_CONFIG["SILKY_AUTHENTICATION"],
        "SILKY_AUTHORISATION": MonitoringConfig.SILK_CONFIG["SILKY_AUTHORISATION"],
        "SILKY_LOG_QUERIES": MonitoringConfig.SILK_CONFIG["SILKY_LOG_QUERIES"],
        "SILKY_LOG_KWARGS": MonitoringConfig.SILK_CONFIG["SILKY_LOG_KWARGS"],
        "SILKY_IGNORE_PATHS": MonitoringConfig.SILK_CONFIG["SILKY_IGNORE_PATHS"],
    }


# ════════════════════════════════════════════════════════════════
# LOGGING CONFIGURATION FOR SETTINGS.PY
# ════════════════════════════════════════════════════════════════


def get_monitoring_logging_config() -> Dict[str, Any]:
    """Get logging configuration for monitoring in settings.py."""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "verbose": {
                "format": "{levelname} {asctime} {name} {funcName}:{lineno} - {message}",
                "style": "{",
            },
            "simple": {
                "format": "{levelname} {asctime} {name} - {message}",
                "style": "{",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "simple",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": "logs/monitoring.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "formatter": "verbose",
            },
            "slow_queries": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": "logs/slow_queries.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "formatter": "verbose",
                "level": "WARNING",
            },
            "slow_requests": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": "logs/slow_requests.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "formatter": "verbose",
                "level": "WARNING",
            },
            "slow_tasks": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": "logs/slow_tasks.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "formatter": "verbose",
                "level": "WARNING",
            },
        },
        "loggers": {
            "django": {
                "handlers": ["console", "file"],
                "level": "INFO",
                "propagate": False,
            },
            "calibra.monitoring": {
                "handlers": ["console", "file"],
                "level": "DEBUG",
                "propagate": False,
            },
            "calibra.slow_queries": {
                "handlers": ["slow_queries"],
                "level": "WARNING",
                "propagate": False,
            },
            "calibra.slow_requests": {
                "handlers": ["slow_requests"],
                "level": "WARNING",
                "propagate": False,
            },
            "calibra.slow_tasks": {
                "handlers": ["slow_tasks"],
                "level": "WARNING",
                "propagate": False,
            },
        },
    }


# ════════════════════════════════════════════════════════════════
# QUICK START GUIDE
# ════════════════════════════════════════════════════════════════
#
# 1. Add to settings.py (development):
#    from config.monitoring_settings import get_debug_toolbar_config
#    DEBUG_TOOLBAR_CONFIG = get_debug_toolbar_config()
#
# 2. Add to INSTALLED_APPS:
#    'debug_toolbar' if DEBUG else None,
#    'silk' if SILK_ENABLED else None,
#
# 3. Add to MIDDLEWARE:
#    'debug_toolbar.middleware.DebugToolbarMiddleware' if DEBUG else None,
#    'silk.middleware.SilkyMiddleware' if SILK_ENABLED else None,
#
# 4. Add to urls.py:
#    if DEBUG:
#        urlpatterns += [path('__debug__/', include('debug_toolbar.urls'))]
#    if SILK_ENABLED:
#        urlpatterns += [path('silk/', include('silk.urls'))]
#
# 5. Monitor performance:
#    from config.monitoring_settings import PerformanceMonitor
#    monitor = PerformanceMonitor()
#    level, msg = monitor.check_request_performance(duration_ms)
#
# ════════════════════════════════════════════════════════════════
