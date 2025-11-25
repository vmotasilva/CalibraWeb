web: gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers=3
worker: celery -A config.celery.app worker -l info --concurrency=4
beat: celery -A config.celery.app beat -l info