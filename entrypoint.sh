#!/bin/bash
set -e

echo "Running database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting Gunicorn server..."
gunicorn config.wsgi:application \
  --bind 0.0.0.0:${PORT:-8000} \
  --workers 3 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
