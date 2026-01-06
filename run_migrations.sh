#!/bin/bash
# Script to run migrations and setup tasks
# This can be run separately from the main application startup
# Usage: ./run_migrations.sh

export PYTHONUNBUFFERED=1

echo "=== Running Django Setup Tasks ==="
echo ""

echo "1. Running migrations..."
python manage.py migrate --noinput
echo "✓ Migrations completed"
echo ""

echo "2. Running collectstatic..."
python manage.py collectstatic --noinput --clear
echo "✓ Static files collected"
echo ""

echo "3. Creating superuser if needed..."
python manage.py ensure_superuser
echo "✓ Superuser check completed"
echo ""

echo "=== All setup tasks completed ==="
