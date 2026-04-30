#!/usr/bin/env bash
# Celery Worker startup script

set -e

export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-config.settings}

if [ -z "$CELERY_BROKER_URL" ] && [ -z "$REDIS_URL" ]; then
	echo "==> No CELERY_BROKER_URL/REDIS_URL configured. Worker will idle."
	exec sleep infinity
fi

echo "==> Starting Celery Worker..."
exec celery -A config.celery.app worker -l info --concurrency=4
