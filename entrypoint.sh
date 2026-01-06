#!/bin/bash
set -ex

export PYTHONUNBUFFERED=1
PORT=${PORT:-8000}

# Bare minimum test
echo "TEST: Container is running"
echo "PORT=$PORT"

# Try Django check
python manage.py check --database default

# Try migrations
python manage.py migrate --noinput --fake-initial 2>/dev/null || python manage.py migrate --noinput

# Try static files
python manage.py collectstatic --noinput --clear 2>/dev/null || true

# Try superuser
python manage.py ensure_superuser 2>/dev/null || true

# Start server
exec gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --timeout 120 --access-logfile - --error-logfile - --log-level debug

