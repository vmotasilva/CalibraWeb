#!/bin/bash
set -x
export PYTHONUNBUFFERED=1
PORT=${PORT:-8000}

echo "=== CONTAINER STARTED ==="
echo "Time: $(date)"
echo "PORT: $PORT"
echo "PWD: $(pwd)"
echo "USER: $(whoami)"
echo ""

echo ">>> Running: python manage.py check"
python manage.py check --database default 2>&1 || true
echo ""

echo ">>> Running: python manage.py migrate"
python manage.py migrate --noinput --fake-initial 2>/dev/null || python manage.py migrate --noinput 2>&1 || true
echo ""

echo ">>> Running: python manage.py collectstatic"
python manage.py collectstatic --noinput --clear 2>&1 || true
echo ""
  
echo ">>> Running: python manage.py ensure_superuser"
python manage.py ensure_superuser 2>&1 || true
echo ""

echo "=== STARTING GUNICORN ==="
exec gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --timeout 120 --access-logfile - --error-logfile - --log-level debug
