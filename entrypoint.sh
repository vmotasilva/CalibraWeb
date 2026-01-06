#!/bin/bash
set -e

echo "=== CalibraWeb Startup ==="
echo "Python version: $(python --version)"
echo "Django check..."
python manage.py check

echo ""
echo "Running database migrations..."
python manage.py migrate --noinput || { echo "Migration failed!"; exit 1; }

echo ""
echo "Collecting static files..."
python manage.py collectstatic --noinput --clear || { echo "Collectstatic failed!"; exit 1; }

echo ""
echo "Starting Gunicorn server on port ${PORT:-8000}..."
exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:${PORT:-8000} \
  --workers 3 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  --log-level debug

