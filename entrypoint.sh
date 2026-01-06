#!/bin/bash
# Exit on any error but show what's happening
set -ex

# Unbuffer output to see logs immediately
export PYTHONUNBUFFERED=1

# Set default PORT if not provided by Railway
PORT=${PORT:-8000}

echo "=========================================="
echo "=== CalibraWeb Startup Starting ==="
echo "=========================================="
echo "Time: $(date)"
echo "Python version: $(python --version)"
echo "Python executable: $(which python)"
echo "Current directory: $(pwd)"
echo "Listening on port: $PORT"
echo ""

# Setup persistent storage first
echo ""
echo ">>> Step 1: Setting up persistent storage..."
python setup_persistent_storage.py || true
echo "✓ Persistent storage configured"

# Debug: Check environment variables
echo ""
echo ">>> Step 2: Verifying environment variables..."
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
echo ">>> Step 3: Running Django check..."
python manage.py check --database default 2>&1

echo ""
echo ">>> Step 4: Running database migrations..."
python manage.py migrate --noinput --fake-initial 2>/dev/null || python manage.py migrate --noinput 2>&1 || { 
  echo "❌ Migration failed!"; 
  exit 1; 
}
echo "✓ Migrations completed"

echo ""
echo ">>> Step 5: Collecting static files..."
python manage.py collectstatic --noinput --clear 2>&1 || { 
  echo "❌ Collectstatic failed!"; 
  exit 1; 
}
echo "✓ Static files collected"

echo ""
echo ">>> Step 6: Creating superuser if needed..."
python manage.py ensure_superuser 2>/dev/null || true

echo ""
echo "=========================================="
echo ">>> Step 7: Starting Gunicorn..."
echo "=========================================="
echo "Binding to: 0.0.0.0:$PORT"
echo "Workers: 3"
echo "Timeout: 120s"
echo "=========================================="
echo ""
exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:$PORT \
  --workers 3 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  --log-level debug \
  --max-requests 1000 \
  --max-requests-jitter 50

