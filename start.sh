#!/usr/bin/env bash
# Render entrypoint script - runs migrations and collectstatic before starting server

set -ex  # Exit on error, print commands

echo "==> Checking database connection..."
python manage.py check --database default

echo "==> Running database migrations..."
python manage.py migrate --noinput

echo "==> Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "==> Creating superuser (if not exists)..."
python manage.py ensure_superuser

echo "==> Starting Gunicorn server on port $PORT..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:$PORT \
    --workers 3 \
    --timeout 120 \
    --log-level debug \
    --access-logfile - \
    --error-logfile -
