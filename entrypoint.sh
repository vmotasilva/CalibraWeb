#!/bin/bash
set -ex
export PYTHONUNBUFFERED=1
PORT=${PORT:-8000}

echo "=== ENTRYPOINT SCRIPT STARTED ==="
echo "PORT=${PORT}"
echo "PWD=$(pwd)"
echo "Python version: $(python --version)"
echo "Gunicorn version: $(gunicorn --version)"
echo ""

# Try Django migrations asynchronously (don't block startup)
echo "Starting Django maintenance tasks in background..."
(
  python manage.py migrate --noinput 2>&1 || true
  python manage.py collectstatic --noinput 2>&1 || true
  python manage.py ensure_superuser 2>&1 || true
) &
BG_PID=$!

echo "Maintenance tasks PID: $BG_PID"
echo "Starting Gunicorn immediately (maintenance runs in background)..."
echo ""

exec gunicorn \
  config.wsgi:application \
  --bind 0.0.0.0:${PORT} \
  --workers 3 \
  --worker-class sync \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  --log-level debug \
  --forwarded-allow-ips="*"
