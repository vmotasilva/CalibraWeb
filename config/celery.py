import os
import sys
import logging

from celery import Celery

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("CalibraWeb")

logger = logging.getLogger(__name__)
CELERY_ENV_DEBUG = os.getenv("CELERY_ENV_DEBUG", "false").lower() in ("1", "true", "yes")

# Debug: Print environment info before loading config
def _debug_env():
    """Debug print environment variables (safe version)."""
    if not CELERY_ENV_DEBUG:
        return

    print("\n" + "="*60)
    print("CELERY ENVIRONMENT DEBUG")
    print("="*60)
    
    env_vars = [
        "REDIS_URL", "REDIS_HOST", "REDIS_PORT", "REDIS_PASSWORD",
        "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND", "DATABASE_URL",
        "DJANGO_SETTINGS_MODULE"
    ]
    
    for var in env_vars:
        val = os.getenv(var, "NOT SET")
        # Hide sensitive data
        if var in ["REDIS_PASSWORD", "SECRET_KEY", "DATABASE_URL", "CELERY_BROKER_URL", "REDIS_URL"]:
            if val != "NOT SET":
                if len(val) > 20:
                    val = val[:20] + "..." + val[-10:]
        print(f"  {var}: {val}")
    
    print("="*60 + "\n")

_debug_env()

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
try:
    app.config_from_object("django.conf:settings", namespace="CELERY")
    if CELERY_ENV_DEBUG:
        print("[OK] Django settings loaded for Celery")
except Exception as e:
    print(f"[ERROR] Error loading Django settings: {e}")
    sys.exit(1)

# CRITICAL: Override broker_url and result_backend to use our _build_redis_url() function
# This prevents Celery from using broken CELERY_BROKER_URL from beat service environment
import django.conf
if hasattr(django.conf.settings, 'CELERY_BROKER_URL'):
    app.conf.broker_url = django.conf.settings.CELERY_BROKER_URL
if hasattr(django.conf.settings, 'CELERY_RESULT_BACKEND'):
    app.conf.result_backend = django.conf.settings.CELERY_RESULT_BACKEND


def _has_unresolved_template(value: object) -> bool:
    return "${" in str(value) or "%24%7B" in str(value)


def _safe_redis_url_from_env() -> str:
    """Best-effort Redis URL builder that ignores '${...}' placeholders."""
    redis_url = os.getenv("REDIS_URL")
    if redis_url and not _has_unresolved_template(redis_url):
        return redis_url
    return "redis://localhost:6379/0"

# Validate broker connection
broker_url = getattr(app.conf, 'broker_url', 'NOT SET')
result_backend = getattr(app.conf, 'result_backend', 'NOT SET')

if _has_unresolved_template(broker_url):
    resolved = _safe_redis_url_from_env()
    app.conf.broker_url = resolved
    broker_url = resolved

if _has_unresolved_template(result_backend):
    resolved = _safe_redis_url_from_env()
    app.conf.result_backend = resolved
    result_backend = resolved

if _has_unresolved_template(broker_url) or _has_unresolved_template(result_backend):
    print(f"[ERROR] CRITICAL: Celery Redis URL still has unresolved templates")
    print(f"   broker_url={broker_url}")
    print(f"   result_backend={result_backend}")
    print(f"   Fix Railway env vars: prefer only REDIS_URL (no '${{...}}' placeholders).")
else:
    if CELERY_ENV_DEBUG:
        short_broker = f"{broker_url[:30]}..." if len(str(broker_url)) > 30 else str(broker_url)
        short_backend = f"{result_backend[:30]}..." if len(str(result_backend)) > 30 else str(result_backend)
        print(f"[OK] CELERY broker_url: {short_broker}")
        print(f"[OK] CELERY result_backend: {short_backend}")

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# Configure Celery Beat schedules for Phase 5 (Exports and Reports)
try:
    from qms.celery_beat_config import (
        CELERY_BEAT_SCHEDULE,
        CELERY_QUEUES,
        CELERY_ROUTES,
    )
    
    app.conf.beat_schedule = CELERY_BEAT_SCHEDULE
    app.conf.task_queues = CELERY_QUEUES
    app.conf.task_routes = CELERY_ROUTES
    if CELERY_ENV_DEBUG:
        print(f"[OK] Celery Beat scheduled with {len(CELERY_BEAT_SCHEDULE)} tasks")
except ImportError as e:
    # If qms app is not available, continue without Beat configuration
    logger.warning("Celery Beat config not available: %s", e)
except Exception as e:
    print(f"[ERROR] Error loading Celery Beat config: {e}")


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
