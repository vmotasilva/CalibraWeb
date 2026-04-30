#!/usr/bin/env python
"""
Entrypoint para Celery Beat no Docker
Executa o scheduler de tarefas agendadas Celery
"""
import os
import sys
import subprocess
import time

# Force unbuffered output
os.environ['PYTHONUNBUFFERED'] = '1'

print("[CELERY_BEAT_ENTRYPOINT] ================================", flush=True)
print("[CELERY_BEAT_ENTRYPOINT] Celery Beat Entrypoint Starting", flush=True)
print(f"[CELERY_BEAT_ENTRYPOINT] Python: {sys.version}", flush=True)
print(f"[CELERY_BEAT_ENTRYPOINT] CWD: {os.getcwd()}", flush=True)
print(f"[CELERY_BEAT_ENTRYPOINT] ================================", flush=True)

# Verify required environment variables
redis_url = os.environ.get('REDIS_URL') or os.environ.get('CELERY_BROKER_URL')
if not redis_url:
    print("[CELERY_BEAT_ENTRYPOINT] WARNING: REDIS_URL or CELERY_BROKER_URL not set", flush=True)
    print("[CELERY_BEAT_ENTRYPOINT] Using default: redis://localhost:6379/0", flush=True)
else:
    # Don't log the full URL for security
    print(f"[CELERY_BEAT_ENTRYPOINT] OK - Redis configured (URL partially masked)", flush=True)

# Check if celery is available
try:
    import celery
    print(f"[CELERY_BEAT_ENTRYPOINT] OK - Celery version: {celery.__version__}", flush=True)
except ImportError as e:
    print(f"[CELERY_BEAT_ENTRYPOINT] ERROR: Celery not found: {e}", flush=True)
    sys.exit(1)

# Try to import Django
try:
    import django
    print(f"[CELERY_BEAT_ENTRYPOINT] OK - Django version: {django.__version__}", flush=True)
except ImportError as e:
    print(f"[CELERY_BEAT_ENTRYPOINT] ERROR: Django not found: {e}", flush=True)
    sys.exit(1)

print("[CELERY_BEAT_ENTRYPOINT] Starting Celery Beat Scheduler...", flush=True)
print("[CELERY_BEAT_ENTRYPOINT] ================================", flush=True)
sys.stdout.flush()
sys.stderr.flush()

# Run Celery Beat with database scheduler for task persistence
result = subprocess.run([
    'celery',
    '-A', 'config',
    'beat',
    '--loglevel=info',
    '--scheduler=django_celery_beat.schedulers:DatabaseScheduler',
], env=os.environ.copy())

sys.exit(result.returncode)
