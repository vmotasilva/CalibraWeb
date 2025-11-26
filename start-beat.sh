#!/usr/bin/env bash
# Celery Beat startup script

set -e

echo "==> Starting Celery Beat..."
exec celery -A config.celery.app beat -l info
