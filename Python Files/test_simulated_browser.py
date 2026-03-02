#!/usr/bin/env python
"""
Simulated browser POST test - exactly like a real browser would send
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(__file__))

django.setup()

from django.test import Client
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session

# Clean old sessions
Session.objects.all().delete()

# Create client exactly like a browser
client = Client(enforce_csrf_checks=True)  # IMPORTANT: Enforce CSRF checks!

# Create user
try:
    user = User.objects.get(username='admin')
except User.DoesNotExist:
    user = User.objects.create_superuser('admin', 'admin@test.com', 'admin123')

print("=" * 70)
print("SIMULATED BROWSER POST TEST (WITH CSRF ENFORCEMENT)")
print("=" * 70)

# Step 1: Login (like browser does)
print(f"\n1. Login...")
client.login(username='admin', password='admin123')
print(f"   ✓ Logged in")

# Step 2: GET page to see CSRF token
print(f"\n2. GET /procedures/perfis/1/...")
response = client.get('/procedures/perfis/1/')
print(f"   Status: {response.status_code}")

# Extract CSRF token from HTML
import re
csrf_match = re.search(r'name=["\']csrfmiddlewaretoken["\'][^>]*value=["\']([^"\']+)["\']', response.content.decode())
csrf_token = csrf_match.group(1) if csrf_match else None
print(f"   CSRF Token: {csrf_token[:30] if csrf_token else 'NOT FOUND'}...")

# Step 3: POST with CSRF token (just like browser form submission)
print(f"\n3. POST /procedures/perfis/1/colaboradores/editar/ (WITH csrf_token)...")
if csrf_token:
    response = client.post(
        '/procedures/perfis/1/colaboradores/editar/',
        {'csrfmiddlewaretoken': csrf_token, 'cp_id': '1'},
        HTTP_HOST='127.0.0.1:18000'
    )
    print(f"   Status: {response.status_code}")
    
    if response.status_code in [200, 302]:
        print(f"   ✓ SUCCESS! POST was accepted")
        if response.status_code == 302:
            print(f"   Redirected to: {response.get('Location')}")
    elif response.status_code == 403:
        print(f"   ✗ FAILED with 403 CSRF")
        # Find error message
        if b'CSRF cookie not set' in response.content:
            print(f"   Error: CSRF cookie not set")
        elif b'CSRF token from POST' in response.content:
            print(f"   Error: CSRF token incorrect")
    else:
        print(f"   ? Unexpected status")
else:
    print(f"   ✗ Could not extract CSRF token from page")

print("\n" + "=" * 70)
print("Result: If you see SUCCESS above, the browser should work too!")
print("=" * 70)
