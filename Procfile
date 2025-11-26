web: bash start.sh
worker: celery -A config.celery.app worker -l info --concurrency=4
beat: celery -A config.celery.app beat -l info