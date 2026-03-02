#!/usr/bin/env python
"""
Debug Django settings to verify CSRF configuration
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(__file__))

django.setup()

from django.conf import settings

print("=" * 70)
print("DJANGO SETTINGS DIAGNOSTIC")
print("=" * 70)

print(f"\n1. DEBUG Setting: {settings.DEBUG}")
print(f"   Type: {type(settings.DEBUG)}")
print(f"   Is True: {settings.DEBUG is True}")

print(f"\n2. CSRF Settings:")
print(f"   CSRF_USE_SESSIONS: {settings.CSRF_USE_SESSIONS}")
print(f"   CSRF_COOKIE_SECURE: {settings.CSRF_COOKIE_SECURE}")
print(f"   CSRF_COOKIE_HTTPONLY: {settings.CSRF_COOKIE_HTTPONLY}")
print(f"   CSRF_COOKIE_SAMESITE: {getattr(settings, 'CSRF_COOKIE_SAMESITE', 'NOT SET')}")
print(f"   CSRF_COOKIE_AGE: {getattr(settings, 'CSRF_COOKIE_AGE', 'NOT SET')}")
print(f"   CSRF_COOKIE_NAME: {getattr(settings, 'CSRF_COOKIE_NAME', 'NOT SET')}")

print(f"\n3. SESSION Settings:")
print(f"   SESSION_ENGINE: {settings.SESSION_ENGINE}")
print(f"   SESSION_COOKIE_SECURE: {settings.SESSION_COOKIE_SECURE}")
print(f"   SESSION_COOKIE_HTTPONLY: {settings.SESSION_COOKIE_HTTPONLY}")
print(f"   SESSION_COOKIE_AGE: {settings.SESSION_COOKIE_AGE}")
print(f"   SESSION_COOKIE_NAME: {settings.SESSION_COOKIE_NAME}")

print(f"\n4. ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")

print(f"\n5. CSRF_TRUSTED_ORIGINS: {settings.CSRF_TRUSTED_ORIGINS}")

print(f"\n6. Middleware Order:")
for i, mw in enumerate(settings.MIDDLEWARE):
    print(f"   {i}: {mw}")

print(f"\n7. Additional CSRF Settings:")
print(f"   CSRF_FAILURE_VIEW: {getattr(settings, 'CSRF_FAILURE_VIEW', 'DEFAULT')}")
print(f"   CSRF_HEADER_NAME: {getattr(settings, 'CSRF_HEADER_NAME', 'HTTP_X_CSRFTOKEN')}")

# Check if environment variables are overriding settings
print(f"\n8. Environment Variables:")
print(f"   DEBUG env: {os.environ.get('DEBUG', 'NOT SET')}")
print(f"   ALLOWED_HOSTS env: {os.environ.get('ALLOWED_HOSTS', 'NOT SET')}")
print(f"   IS_LOCAL_ENV detected: {any(h in os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1') for h in ['localhost', '127.0.0.1'])}")

print("\n" + "=" * 70)
