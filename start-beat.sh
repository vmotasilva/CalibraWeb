#!/usr/bin/env bash
# Celery Beat startup script

set -e

export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-config.settings}

if [ -z "$CELERY_BROKER_URL" ] && [ -z "$REDIS_URL" ]; then
	echo "==> No CELERY_BROKER_URL/REDIS_URL configured. Beat will idle."
	exec sleep infinity
fi

echo "==> Starting Celery Beat..."
exec celery -A config.celery.app beat -l info
