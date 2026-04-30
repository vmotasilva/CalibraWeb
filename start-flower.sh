#!/bin/bash
# Start Flower for Celery Task Monitoring
# Usage: bash start-flower.sh

# Set environment
source .env 2>/dev/null || true

# Default values
FLOWER_PORT=${FLOWER_PORT:-5555}
FLOWER_LOG_LEVEL=${FLOWER_LOG_LEVEL:-info}

echo "=========================================="
echo "Starting Celery Flower Monitoring"
echo "=========================================="
echo "Port: $FLOWER_PORT"
echo "Log Level: $FLOWER_LOG_LEVEL"
echo "=========================================="

# Start Flower
celery -A config flower \
    --port=${FLOWER_PORT} \
    --loglevel=${FLOWER_LOG_LEVEL} \
    --config=config.flower_config \
    --workdir=/app \
    --broker=${CELERY_BROKER_URL:-redis://localhost:6379/0}

echo "Flower stopped"
