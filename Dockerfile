FROM python:3.12-slim

# Prevents Python from writing .pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (build + runtime)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    bash \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

# Skip collectstatic during build; handled by start.sh at runtime
# to ensure SECRET_KEY and DATABASE_URL are available.
# ARG DJANGO_STATIC=1
# ENV DJANGO_SETTINGS_MODULE=config.settings
# RUN python manage.py collectstatic --noinput || echo "Skipping collectstatic if settings not configured"

EXPOSE 8000
CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 3 --timeout 120 --access-logfile - --error-logfile -"]