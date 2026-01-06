#!/bin/bash
# Exit on any error but show what's happening
set -ex

# Unbuffer output to see logs immediately
export PYTHONUNBUFFERED=1

# Set default PORT if not provided by Railway
PORT=${PORT:-8000}

echo "=========================================="
echo "=== CalibraWeb Starting ==="
echo "=========================================="

# Skip the storage setup - it might be blocking
# python setup_persistent_storage.py || true

# Step 1: Django check (minimal output)
echo ">>> Step 1: Django system check..."
python manage.py check --database default
echo "✓ OK"

# Step 2: Migrations 
echo ">>> Step 2: Running migrations..."
python manage.py migrate --noinput --fake-initial 2>/dev/null || python manage.py migrate --noinput
echo "✓ OK"

# Step 3: Static files
echo ">>> Step 3: Collecting static files..."
python manage.py collectstatic --noinput --clear
echo "✓ OK"

# Step 4: Superuser
echo ">>> Step 4: Ensuring superuser..."
python manage.py ensure_superuser 2>/dev/null || true

# Step 5: Start server
echo ""
echo "=========================================="
echo ">>> Starting Gunicorn on $PORT"
echo "=========================================="
echo ""

exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:$PORT \
  --workers 3 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  --log-level debug

