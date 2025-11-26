#!/usr/bin/env bash
# Celery Worker startup script

set -e

echo "==> Starting Celery Worker..."
exec celery -A config.celery.app worker -l info --concurrency=4
