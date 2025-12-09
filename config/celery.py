import os

from celery import Celery

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("CalibraWeb")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object("django.conf:settings", namespace="CELERY")

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
except ImportError:
    # If qms app is not available, continue without Beat configuration
    pass


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
