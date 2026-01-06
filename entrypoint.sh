#!/bin/bash
set -x
export PYTHONUNBUFFERED=1
PORT=${PORT:-8000}

echo "========================================"
echo "[ENTRYPOINT] Container iniciado"
echo "[ENTRYPOINT] PORT=${PORT}"
echo "[ENTRYPOINT] PWD=$(pwd)"
echo "[ENTRYPOINT] Python: $(python --version 2>&1)"
echo "[ENTRYPOINT] Gunicorn: $(gunicorn --version 2>&1)"
echo "========================================"

echo "[ENTRYPOINT] Iniciando Gunicorn..."
exec gunicorn \
  config.wsgi:application \
  --bind 0.0.0.0:${PORT} \
  --workers 1 \
  --worker-class sync \
  --max-requests 1000 \
  --timeout 600 \
  --access-logfile - \
  --error-logfile - \
  --log-level debug
