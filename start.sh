#!/usr/bin/env bash
# Railway entrypoint script - runs migrations and collectstatic before starting server

set -e  # Exit on error

export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-config.settings}

echo "==> Checking database connection..."
DB_CHECK_RETRIES=${DB_CHECK_RETRIES:-30}
DB_CHECK_DELAY=${DB_CHECK_DELAY:-2}

db_ok=false
for i in $(seq 1 $DB_CHECK_RETRIES); do
    if python manage.py check --database default; then
        db_ok=true
        break
    fi
    echo "Database not ready yet ($i/$DB_CHECK_RETRIES). Waiting ${DB_CHECK_DELAY}s..."
    sleep $DB_CHECK_DELAY
done

if [ "$db_ok" != "true" ]; then
    echo "Database connection failed after $DB_CHECK_RETRIES attempts."
    exit 1
fi

echo "==> Running database migrations..."
python manage.py migrate --noinput --fake-initial 2>/dev/null || python manage.py migrate --noinput

echo "==> Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "==> Creating superuser (if not exists)..."
python manage.py ensure_superuser 2>/dev/null || true

echo "==> Starting Gunicorn server on port $PORT..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:$PORT \
    --workers ${GUNICORN_WORKERS:-3} \
    --timeout ${GUNICORN_TIMEOUT:-300} \
    --log-level ${GUNICORN_LOG_LEVEL:-info} \
    --access-logfile - \
    --error-logfile -
