# Flower Configuration for Celery Task Monitoring
# File: config/flower_config.py
# Usage: celery -A config flower --config=config.flower_config

import os
from datetime import timedelta

# ================================================
# Flower Server Configuration
# ================================================

# Port to run Flower on
port = int(os.getenv('FLOWER_PORT', 5555))

# Address to bind to
address = '0.0.0.0'

# URL prefix for reverse proxy (if behind nginx)
url_prefix = os.getenv('FLOWER_URL_PREFIX', '')

# ================================================
# Logging Configuration
# ================================================

# Log level (debug, info, warning, error)
logging_level = os.getenv('FLOWER_LOG_LEVEL', 'info')

# Log format
log_format = '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s'

# ================================================
# Flower Dashboard Configuration
# ================================================

# Persistence database (local, memory, or db connection string)
# Using SQLite for simplicity
db = os.getenv('FLOWER_DB', 'flower.db')

# Maximum number of tasks to keep in memory
max_tasks = int(os.getenv('FLOWER_MAX_TASKS', 10000))

# ================================================
# Worker Monitoring
# ================================================

# Update worker heartbeat every N seconds
worker_offline_threshold = int(os.getenv('FLOWER_WORKER_OFFLINE_THRESHOLD', 60))

# ================================================
# Task Monitoring
# ================================================

# Show task arguments and results in the UI
# WARNING: May expose sensitive data
show_task_args = os.getenv('FLOWER_SHOW_TASK_ARGS', 'false').lower() == 'true'

# Hide task arguments and results
hide_task_args = os.getenv('FLOWER_HIDE_TASK_ARGS', 'true').lower() == 'true'

# Task result backend
result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

# Persist Flower's database to disk
persistent = True

# ================================================
# Authentication & Security
# ================================================

# Basic auth username and password
# Set via environment variables
basic_auth = None
username = os.getenv('FLOWER_USERNAME', '')
password = os.getenv('FLOWER_PASSWORD', '')

if username and password:
    basic_auth = [f"{username}:{password}"]

# Enable SSL/TLS
ssl_certfile = os.getenv('FLOWER_SSL_CERTFILE', None)
ssl_keyfile = os.getenv('FLOWER_SSL_KEYFILE', None)
ssl_version = 'TLSv1_2'

# ================================================
# Performance Configuration
# ================================================

# WebSocket ping interval (seconds)
# Reduces WebSocket pings to save bandwidth
persistent_sessions = True

# Connection pool size
broker_connection_pool_size = int(os.getenv('FLOWER_POOL_SIZE', 10))

# ================================================
# Notification Configuration
# ================================================

# Email notifications for task failures
email_on_failure = os.getenv('FLOWER_EMAIL_ON_FAILURE', 'false').lower() == 'true'

# Email settings (requires email backend configured)
email_host = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
email_port = int(os.getenv('EMAIL_PORT', 587))
email_from = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@calibraweb.com')
email_to = os.getenv('FLOWER_ALERT_EMAIL', '')

# ================================================
# API Configuration
# ================================================

# Enable API endpoints
api = True

# ================================================
# Advanced Configuration
# ================================================

# Allow task pool management
allow_termination = os.getenv('FLOWER_ALLOW_TERMINATION', 'true').lower() == 'true'

# Inspect timeout (seconds)
inspect_timeout = int(os.getenv('FLOWER_INSPECT_TIMEOUT', 5))

# ================================================
# Celery Configuration
# ================================================

# Celery app
app = 'config'

# Celery settings module
settings = 'config.settings'

# Broker connection retry delay (seconds)
broker_connection_retry_on_startup = True
broker_connection_retry = True
broker_connection_max_retries = 3

# ================================================
# Theme & Customization
# ================================================

# Custom theme
# Available: default, material (via bootstrap theme)
theme = os.getenv('FLOWER_THEME', 'default')

# Display task details on task success
show_taskargs = os.getenv('FLOWER_SHOW_TASKARGS', 'false').lower() == 'true'

# Auto-refresh interval (seconds)
# Set to 0 to disable
refresh = int(os.getenv('FLOWER_REFRESH', 2000))

# ================================================
# Development Configuration
# ================================================

# Enable debug mode (development only)
debug = os.getenv('FLOWER_DEBUG', 'false').lower() == 'true'

# CORS support (for API usage)
cors = ['*'] if os.getenv('FLOWER_CORS', 'false').lower() == 'true' else []
