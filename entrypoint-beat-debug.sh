#!/bin/bash
# Celery Beat entrypoint com debug completo

set -e

echo "=========================================="
echo "CELERY BEAT - Validation & Debug"
echo "=========================================="

# CRITICAL: Unset broken template variables that might be in the environment
# This prevents Celery from using CELERY_BROKER_URL/CELERY_RESULT_BACKEND with unresolved templates
if [[ "$CELERY_BROKER_URL" == *"\${"* ]] || [[ "$CELERY_BROKER_URL" == *"%24%7B"* ]]; then
    echo "⚠️  Removing broken CELERY_BROKER_URL from environment"
    unset CELERY_BROKER_URL
fi

if [[ "$CELERY_RESULT_BACKEND" == *"\${"* ]] || [[ "$CELERY_RESULT_BACKEND" == *"%24%7B"* ]]; then
    echo "⚠️  Removing broken CELERY_RESULT_BACKEND from environment"
    unset CELERY_RESULT_BACKEND
fi

# Print environment
echo ""
echo "Environment Variables:"
echo "  DJANGO_SETTINGS_MODULE: $DJANGO_SETTINGS_MODULE"
echo "  DEBUG: $DEBUG"
echo "  REDIS_HOST: ${REDIS_HOST:-NOT SET}"
echo "  REDIS_PORT: ${REDIS_PORT:-NOT SET}"
echo "  REDIS_PASSWORD: ${REDIS_PASSWORD:+SET (hidden)}"
echo "  REDIS_URL: ${REDIS_URL:+SET (hidden)}"
echo "  CELERY_BROKER_URL: ${CELERY_BROKER_URL:+SET (hidden)}"
echo ""

# Test database connection
echo "Testing Database Connection..."
python manage.py dbshell <<EOF
SELECT 1;
\q
EOF
echo "✅ Database OK"

# Test Redis connection
echo ""
echo "Testing Redis Connection..."
python -c "
import os
import redis
from urllib.parse import urlparse

redis_url = os.getenv('REDIS_URL') or os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
print(f'Redis URL: {redis_url[:30]}...')

try:
    r = redis.from_url(redis_url)
    r.ping()
    print('✅ Redis Connection OK')
except Exception as e:
    print(f'❌ Redis Connection Failed: {e}')
    import sys
    sys.exit(1)
"

# Collect static files
echo ""
echo "Collecting Static Files..."
python manage.py collectstatic --noinput || true

# Run migrations
echo ""
echo "Running Migrations..."
python manage.py migrate --noinput || true

# Start Celery Beat
echo ""
echo "=========================================="
echo "Starting Celery Beat"
echo "=========================================="
echo ""

exec celery -A config beat --loglevel=info
