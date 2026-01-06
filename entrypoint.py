#!/usr/bin/env python
"""
Entrypoint for Docker - runs Gunicorn directly
"""
import os
import sys

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

print("[ENTRYPOINT] Starting Gunicorn...", flush=True)
sys.stdout.flush()
sys.stderr.flush()

# Import subprocess to run gunicorn
import subprocess
result = subprocess.run([
    'gunicorn',
    'config.wsgi:application',
    f'--bind=0.0.0.0:{PORT}',
    '--workers=1',
    '--worker-class=sync',
    '--timeout=600',
    '--access-logfile=-',
    '--error-logfile=-',
    '--log-level=info',
])

sys.exit(result.returncode)
