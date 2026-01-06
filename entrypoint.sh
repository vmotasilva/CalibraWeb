#!/bin/bash
set -ex
export PYTHONUNBUFFERED=1
PORT=${PORT:-8000}

echo "=== STARTUP DIAGNOSTICS ==="
echo "PORT: $PORT"
echo "DATABASE_URL: ${DATABASE_URL:0:50}..."
echo ""

# Test database connection
echo "Testing database connection..."
python -c "
import os
import psycopg2
try:
    import dj_database_url
    db_config = dj_database_url.config(default=os.environ.get('DATABASE_URL'))
    conn = psycopg2.connect(
        dbname=db_config['NAME'],
        user=db_config['USER'],
        password=db_config['PASSWORD'],
        host=db_config['HOST'],
        port=db_config['PORT']
    )
    print('✓ Database connection OK')
    conn.close()
except Exception as e:
    print(f'✗ Database connection FAILED: {e}')
    exit(1)
" || echo "⚠ Database test skipped"

echo ""
echo "Testing Django setup..."
python manage.py check --deploy || true
echo ""

echo "=== STARTING BACKGROUND TASKS ==="
# Run migrations in background with timeout
(
  timeout 30 python manage.py migrate --noinput 2>&1 || echo "⚠ Migrations timeout or failed"
  timeout 30 python manage.py collectstatic --noinput 2>&1 || echo "⚠ Collectstatic timeout or failed"
  timeout 30 python manage.py ensure_superuser 2>&1 || echo "⚠ Superuser timeout or failed"
) &

echo "=== STARTING GUNICORN ==="
exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:${PORT} \
  --workers 3 \
  --worker-class sync \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  --log-level debug \
  --forwarded-allow-ips="*" \
  --capture-output
