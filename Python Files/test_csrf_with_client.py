#!/usr/bin/env python
"""
Test CSRF with Django test client (which properly manages sessions and cookies)
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(__file__))

django.setup()

from django.test import Client
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session

print("=" * 60)
print("CSRF TEST WITH DJANGO TEST CLIENT")
print("=" * 60)

# Clean up sessions
print("\nCleaning up old sessions...")
Session.objects.all().delete()

# Create test user
try:
    test_user = User.objects.get(username='testuser')
    print(f"Using existing test user: {test_user.username}")
except User.DoesNotExist:
    test_user = User.objects.create_user(username='testuser', password='testpass123')
    print(f"Created test user: {test_user.username}")

# Create client
client = Client()

print("\n--- Step 1: Get the form page (to get CSRF token) ---")
response = client.get('/')
print(f"GET / response: {response.status_code}")
if 'csrftoken' in response.cookies:
    print(f"  CSRF token from cookie: {response.cookies['csrftoken'].value[:20]}...")
print(f"  Session cookie: {response.cookies.get('sessionid', 'NOT SET')}")

# Login
print("\n--- Step 2: Login ---")
logged_in = client.login(username='testuser', password='testpass123')
print(f"Login successful: {logged_in}")

# Get the perfil detalhe page
print("\n--- Step 3: Get perfil page ---")
response = client.get('/procedures/perfis/1/')
print(f"GET /procedures/perfis/1/ response: {response.status_code}")
if response.status_code == 200:
    # Look for CSRF token in response
    import re
    match = re.search(r'csrfmiddlewaretoken["\']?\s*[=:]\s*["\']([^"\']+)["\']', response.content.decode())
    if match:
        print(f"  CSRF token in page: {match.group(1)[:20]}...")

# Try POST without CSRF token
print("\n--- Step 4: POST without CSRF (should fail) ---")
response = client.post('/procedures/perfis/1/colaboradores/editar/', 
                      {'cp_id': '1'},
                      HTTP_HOST='localhost:18000',
                      follow=False)
print(f"POST response: {response.status_code}")
if response.status_code == 403:
    print("  CSRF rejected as expected ✓")
elif response.status_code == 302:
    print("  POST redirected (possible CSRF bypass detected)")
    print(f"  Location: {response.get('Location', 'N/A')}")

# Try POST with CSRF token
print("\n--- Step 5: POST with CSRF token ---")
# Get CSRF token from page
response = client.get('/procedures/perfis/1/')
csrf_token = None
if response.status_code == 200:
    import re
    # Look for the CSRF token in multiple formats
    patterns = [
        r"csrfmiddlewaretoken['\"]?\s*[=:]\s*['\"]([^'\"]+)['\"]",
        r'name=["\']csrfmiddlewaretoken["\'].*?value=["\']([^"\']+)["\']',
        r'<input[^>]*csrfmiddlewaretoken[^>]*value=["\']([^"\']+)["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, response.content.decode(), re.IGNORECASE)
        if match:
            csrf_token = match.group(1)
            print(f"  Found CSRF token: {csrf_token[:20]}...")
            break

if csrf_token:
    response = client.post('/procedures/perfis/1/colaboradores/editar/',
                          {'csrfmiddlewaretoken': csrf_token, 'cp_id': '1'},
                          HTTP_HOST='localhost:18000',
                          follow=False)
    print(f"POST response: {response.status_code}")
    if response.status_code in [200, 302]:
        print("  POST accepted ✓ (status allowed)")
    elif response.status_code == 403:
        print(f"  POST rejected with 403 CSRF ✗")
        if b'CSRF' in response.content:
            print("  Response contains CSRF error message")
else:
    print("  Could not find CSRF token in page")
    print(f"  Page content length: {len(response.content)}")

print("\n" + "=" * 60)
print("END OF TEST")
print("=" * 60)
