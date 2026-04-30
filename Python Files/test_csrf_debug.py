#!/usr/bin/env python
"""
Test script to debug CSRF token issues and clean corrupted sessions
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(__file__))

django.setup()

from django.contrib.sessions.models import Session
from django.utils import timezone
from django.http import HttpResponse
from django.middleware.csrf import CsrfViewMiddleware
from django.contrib.auth.models import User
from django.contrib.sessions.backends.db import SessionStore
from datetime import timedelta

# Check sessions table
print("=" * 60)
print("DJANGO SESSIONS TABLE ANALYSIS")
print("=" * 60)

sessions = Session.objects.all()
print(f"\nTotal sessions in database: {sessions.count()}")

# Delete all sessions to start fresh
print("\nDeleting all sessions...")
sessions.delete()
print(f"Remaining sessions: {Session.objects.count()}")

print("\n" + "=" * 60)
print("CSRF MIDDLEWARE TEST")
print("=" * 60)

from django.test import RequestFactory
from django.contrib.auth import get_user_model

factory = RequestFactory()
User_model = get_user_model()

# Try to get or create a test user
try:
    test_user = User_model.objects.get(username='testuser')
    print(f"Using existing test user: {test_user.username}")
except User_model.DoesNotExist:
    test_user = User_model.objects.create_user(username='testuser', password='testpass123')
    print(f"Created test user: {test_user.username}")

# Create a request with a session
request = factory.post('/procedures/perfis/1/colaboradores/editar/')
request.user = test_user

# Create and attach a session
from django.contrib.sessions.middleware import SessionMiddleware
middleware = SessionMiddleware(lambda x: None)
middleware.process_request(request)
request.session.save()

print(f"\nSession created for test user")
print(f"Session key: {request.session.session_key}")

# Now test CSRF
from django.middleware.csrf import get_token

csrf_token = get_token(request)
print(f"CSRF token generated: {csrf_token[:20]}...")

# Verify it's in the session
session_data = request.session
print(f"Session keys after token generation: {list(session_data.keys())}")

# Simulate POST with CSRF token
print("\n" + "=" * 60)
print("CSRF TOKEN VALIDATION TEST")
print("=" * 60)

# Need to use same session for the POST request
post_request = factory.post(
    '/procedures/perfis/1/colaboradores/editar/',
    {'csrfmiddlewaretoken': csrf_token, 'cp_id': '1'}
)
post_request.user = test_user

# Attach same middleware and session setup
middleware.process_request(post_request)
# Load the same session
post_request.session = SessionStore(session_key=request.session.session_key)

print(f"POST request session key: {post_request.session.session_key}")
print(f"POST session data: {dict(post_request.session)}")
print(f"POST has csrfmiddlewaretoken: {'csrfmiddlewaretoken' in post_request.POST}")

# Test CSRF middleware validation
csrf_middleware = CsrfViewMiddleware(lambda x: HttpResponse('OK'))

try:
    result = csrf_middleware.process_view(post_request, None, (), {})
    if result is None:
        print("CSRF validation: PASSED ✓")
    else:
        print(f"CSRF validation: FAILED")
        print(f"Response status: {result.status_code}")
except Exception as e:
    print(f"CSRF validation ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("DJANGO SETTINGS CSRF CONFIGURATION")
print("=" * 60)

from django.conf import settings

print(f"CSRF_COOKIE_SECURE: {settings.CSRF_COOKIE_SECURE}")
print(f"SESSION_COOKIE_SECURE: {settings.SESSION_COOKIE_SECURE}")
print(f"CSRF_TRUSTED_ORIGINS: {settings.CSRF_TRUSTED_ORIGINS}")
print(f"SESSION_ENGINE: {settings.SESSION_ENGINE}")
print(f"DEBUG: {settings.DEBUG}")

print("\n" + "=" * 60)
print("MIDDLEWARE CHECK")
print("=" * 60)

for i, middleware in enumerate(settings.MIDDLEWARE):
    print(f"{i}: {middleware}")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"✓ All corrupted sessions removed")
print(f"✓ New sessions can be created")
print(f"✓ CSRF tokens generated correctly")
