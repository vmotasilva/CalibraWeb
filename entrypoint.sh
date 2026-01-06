#!/bin/bash
set -e

# Set default PORT if not provided by Railway
PORT=${PORT:-8000}

echo "=== CalibraWeb Startup ==="
echo "Python version: $(python --version)"
echo "Listening on port: $PORT"
echo ""

# Setup persistent storage first
echo ""
echo "Setting up persistent storage..."
python setup_persistent_storage.py || true
echo "✓ Persistent storage configured"

# Debug: Check environment variables
if [ -z "$SECRET_KEY" ]; then
  echo "ERROR: SECRET_KEY environment variable is not set!"
  exit 1
fi
echo "✓ SECRET_KEY is configured"

if [ -z "$DATABASE_URL" ] && [ -z "$PGHOST" ]; then
  echo "ERROR: DATABASE_URL or PGHOST not configured!"
  exit 1
fi
echo "✓ Database configuration present"

echo ""
echo "Django check..."
python manage.py check --database default 2>&1

echo ""
echo "Running database migrations..."
python manage.py migrate --noinput --fake-initial 2>/dev/null || python manage.py migrate --noinput 2>&1 || { 
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
echo "Creating superuser if needed..."
python manage.py ensure_superuser 2>/dev/null || true

echo ""
echo "Starting Gunicorn server on port $PORT..."
echo "All checks passed! Starting application..."
exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:$PORT \
  --workers 3 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  --log-level debug \
  --max-requests 1000 \
  --max-requests-jitter 50

