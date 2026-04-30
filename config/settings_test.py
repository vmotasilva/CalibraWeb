# config/settings_test.py
# Test Settings - Uses in-memory cache to avoid Redis dependency

import os
from config.settings import *  # noqa

# Mark as testing mode
TESTING = True

# Override for testing
DEBUG = True
ALLOWED_HOSTS = ['*']

# Disable 2FA for testing
TWO_FACTOR_PATCH_ADMIN = False
TWO_FACTOR_REQUIRED = False
LOGIN_URL = 'admin:login'

# Remove 2FA from middleware and installed apps
MIDDLEWARE = [m for m in MIDDLEWARE if 'two_factor' not in m]
INSTALLED_APPS = [a for a in INSTALLED_APPS if 'two_factor' not in a and 'otp' not in a]

# Use in-memory cache for testing (no Redis required)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'test-cache',
        'OPTIONS': {
            'MAX_ENTRIES': 10000,
        }
    },
    'sessions': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'test-sessions',
    },
    'statistics': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'test-statistics',
    },
}

# Use in-memory session backend for testing
SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# Disable Celery for testing - run tasks synchronously
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = 'memory://'
CELERY_RESULT_BACKEND = 'cache+memory://'

# Email to console for testing
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Test Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Disable migrations for faster tests
class DisableMigrations:
    def __contains__(self, item):
        return True
    def __getitem__(self, item):
        return None

MIGRATION_MODULES = DisableMigrations()

# Logging for tests
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'null': {
            'class': 'logging.NullHandler',
        },
    },
    'root': {
        'handlers': ['null'],
        'level': 'WARNING',
    },
}

# Security settings for testing
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False

# Disable S3 for testing
USE_S3 = False
