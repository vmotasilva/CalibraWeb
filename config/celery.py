import os
import sys

from celery import Celery

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("CalibraWeb")

# Debug: Print environment info before loading config
def _debug_env():
    """Debug print environment variables (safe version)."""
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
    print("✅ Django settings loaded for Celery")
except Exception as e:
    print(f"❌ Error loading Django settings: {e}")
    sys.exit(1)

# Validate broker connection
broker_url = getattr(app.conf, 'broker_url', 'NOT SET')
if "${" in str(broker_url) or "%24%7B" in str(broker_url):
    print(f"❌ ERROR: CELERY_BROKER_URL still contains unresolved templates!")
    print(f"   Broker URL: {broker_url}")
    print(f"   This should NOT happen - check environment variables in Railway beat service")
    sys.exit(1)
print(f"✅ CELERY_BROKER_URL configured: {broker_url[:30]}..." if len(str(broker_url)) > 30 else f"✅ CELERY_BROKER_URL: {broker_url}")

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
    print(f"✅ Celery Beat scheduled with {len(CELERY_BEAT_SCHEDULE)} tasks")
except ImportError as e:
    # If qms app is not available, continue without Beat configuration
    print(f"⚠️  Celery Beat config not available: {e}")
except Exception as e:
    print(f"❌ Error loading Celery Beat config: {e}")


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
