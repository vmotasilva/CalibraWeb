"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
import logging
import sys

logger = logging.getLogger(__name__)

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

logger.info("[WSGI] Initializing Django application...")

try:
    application = get_wsgi_application()
    logger.info("[WSGI] Django application initialized successfully")
except Exception as e:
    logger.error(f"[WSGI] Failed to initialize Django: {e}", exc_info=True)
    sys.exit(1)
