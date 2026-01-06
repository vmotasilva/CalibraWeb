#!/bin/bash
export PYTHONUNBUFFERED=1
PORT=${PORT:-8000}

exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:${PORT} \
  --workers 3 \
  --worker-class sync \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  --log-level debug \
  --forwarded-allow-ips="*"
