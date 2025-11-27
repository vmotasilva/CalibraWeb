#!/usr/bin/env bash
# Celery Worker startup script

set -e

if [ -z "$CELERY_BROKER_URL" ] && [ -z "$REDIS_URL" ]; then
	echo "==> No CELERY_BROKER_URL/REDIS_URL configured. Worker will idle."
	exec sleep infinity
fi

echo "==> Starting Celery Worker..."
exec celery -A config.celery.app worker -l info --concurrency=4
