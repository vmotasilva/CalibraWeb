#!/bin/bash
set -e

echo "=== CalibraWeb Startup ==="
echo "Python version: $(python --version)"

# Debug: Check if SECRET_KEY is set
if [ -z "$SECRET_KEY" ]; then
  echo "ERROR: SECRET_KEY environment variable is not set!"
  exit 1
fi
echo "✓ SECRET_KEY is configured"

# Debug: Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
  echo "WARNING: DATABASE_URL not set, checking PG* variables..."
fi
echo "✓ Database configuration checked"

echo "Django check..."
python manage.py check 2>&1

echo ""
echo "Running database migrations..."
python manage.py migrate --noinput 2>&1 || { 
  echo "❌ Migration failed!"; 
  exit 1; 
}
echo "✓ Migrations completed"

echo ""
echo "Collecting static files..."
python manage.py collectstatic --noinput --clear 2>&1 || { 
  echo "❌ Collectstatic failed!"; 
  exit 1; 
}
echo "✓ Static files collected"

echo ""
echo "Starting Gunicorn server on port ${PORT:-8000}..."
echo "Port value: ${PORT:-8000}"
echo "All environment check passed, starting application..."
exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:${PORT:-8000} \
  --workers 3 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  --log-level debug \
  --max-requests 1000 \
  --max-requests-jitter 50

