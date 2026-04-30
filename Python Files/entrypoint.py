#!/usr/bin/env python
"""
Entrypoint for Docker - runs Django setup then Gunicorn
"""
import os
import sys
import subprocess

# Force unbuffered output
os.environ['PYTHONUNBUFFERED'] = '1'

print("[ENTRYPOINT] ================================", flush=True)
print("[ENTRYPOINT] Python entrypoint starting", flush=True)
print(f"[ENTRYPOINT] Python: {sys.version}", flush=True)
print(f"[ENTRYPOINT] CWD: {os.getcwd()}", flush=True)
print(f"[ENTRYPOINT] PATH: {os.environ.get('PATH', 'NOT SET')[:100]}", flush=True)

PORT = os.environ.get('PORT', '8000')
print(f"[ENTRYPOINT] PORT: {PORT}", flush=True)
print("[ENTRYPOINT] ================================", flush=True)

# Check if gunicorn is available
try:
    import gunicorn
    print(f"[ENTRYPOINT] Gunicorn version: {gunicorn.__version__}", flush=True)
except ImportError as e:
    print(f"[ENTRYPOINT] ERROR: Gunicorn not found: {e}", flush=True)
    sys.exit(1)

# Try to import Django
try:
    import django
    print(f"[ENTRYPOINT] Django version: {django.__version__}", flush=True)
except ImportError as e:
    print(f"[ENTRYPOINT] ERROR: Django not found: {e}", flush=True)
    sys.exit(1)

# Run Django setup tasks
print("[ENTRYPOINT] Running Django setup tasks...", flush=True)
sys.stdout.flush()

# Run migrations
print("[ENTRYPOINT] ==> Running database migrations...", flush=True)
result = subprocess.run(['python', 'manage.py', 'migrate', '--noinput'], capture_output=False)
if result.returncode != 0:
    print("[ENTRYPOINT] WARNING: Migrations failed (continuing)", flush=True)

# Collect static files
print("[ENTRYPOINT] ==> Collecting static files...", flush=True)
result = subprocess.run(['python', 'manage.py', 'collectstatic', '--noinput'], capture_output=False)
if result.returncode != 0:
    print("[ENTRYPOINT] WARNING: Collectstatic failed (continuing)", flush=True)

# Create superuser if DEBUG
if os.environ.get('DEBUG') == 'True' or os.environ.get('CREATE_SUPERUSER') == 'True':
    print("[ENTRYPOINT] ==> Creating superuser (if not exists)...", flush=True)
    from django.core.management import call_command
    from django.contrib.auth import get_user_model
    User = get_user_model()
    if not User.objects.filter(username='admin').exists():
        try:
            User.objects.create_superuser(
                username='admin',
                email='admin@calibraweb.local',
                password='admin123'
            )
            print("[ENTRYPOINT] Superuser 'admin' created", flush=True)
        except Exception as e:
            print(f"[ENTRYPOINT] Could not create superuser: {e}", flush=True)
    else:
        print("[ENTRYPOINT] Superuser 'admin' already exists", flush=True)

print("[ENTRYPOINT] Starting Gunicorn...", flush=True)
sys.stdout.flush()
sys.stderr.flush()

# Start Gunicorn
result = subprocess.run([
    'gunicorn',
    'config.wsgi:application',
    f'--bind=0.0.0.0:{PORT}',
    '--workers=3',
    '--worker-class=sync',
    '--timeout=300',
    '--access-logfile=-',
    '--error-logfile=-',
    '--log-level=info',
])

sys.exit(result.returncode)
