#!/usr/bin/env python
"""
Entrypoint for Docker - runs Gunicorn directly
"""
import os
import sys
import subprocess

print("[STARTUP] Python entrypoint initialized", flush=True)

PORT = os.environ.get('PORT', '8000')
print(f"[STARTUP] PORT={PORT}", flush=True)

print("[STARTUP] Starting Gunicorn...", flush=True)
sys.stdout.flush()
sys.stderr.flush()

os.execvp('gunicorn', [
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
