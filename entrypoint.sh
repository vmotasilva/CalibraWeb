#!/bin/bash
set -m  # Enable job control
export PYTHONUNBUFFERED=1
PORT=${PORT:-8000}

echo "=== STARTUP SEQUENCE ==="

# Run migrations in background with timeout
echo "Starting background initialization (migrations, collectstatic, superuser)..."
(
  timeout 30 python manage.py migrate --noinput 2>&1 || true
  timeout 30 python manage.py collectstatic --noinput 2>&1 || true
  timeout 30 python manage.py ensure_superuser 2>&1 || true
) &
BG_PID=$!

# Start Gunicorn immediately (don't wait for background tasks)
echo "Starting Gunicorn on port $PORT..."
exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:${PORT} \
  --workers 3 \
  --worker-class sync \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  --log-level debug \
  --forwarded-allow-ips="*"
