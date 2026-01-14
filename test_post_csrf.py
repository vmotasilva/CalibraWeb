#!/usr/bin/env python
"""
Test actual POST with CSRF token extracted from page
"""
import os
import sys
import django
import re

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(__file__))

django.setup()

from django.test import Client
from django.contrib.auth.models import User
from procedures.models import ColaboradorPerfil, PerfilTreinamento

print("=" * 70)
print("CSRF POST TEST")
print("=" * 70)

# Create client
client = Client()

# Get or create user
try:
    user = User.objects.get(username='admin')
except User.DoesNotExist:
    user = User.objects.create_superuser('admin', 'admin@test.com', 'admin123')

# Login
logged_in = client.login(username='admin', password='admin123')
print(f"\n1. Login result: {logged_in}")

# Get the page to extract CSRF token
print(f"\n2. Fetching page to extract CSRF token...")
response = client.get('/procedures/perfis/1/')
print(f"   Response status: {response.status_code}")

content = response.content.decode('utf-8')

# Extract CSRF token
csrf_match = re.search(r'name=["\']csrfmiddlewaretoken["\'][^>]*value=["\']([^"\']+)["\']', content)
if csrf_match:
    csrf_token = csrf_match.group(1)
    print(f"   ✓ Found CSRF token: {csrf_token[:30]}...{csrf_token[-20:]}")
else:
    print(f"   ✗ Could not find CSRF token")
    sys.exit(1)

# Extract form action URL
action_match = re.search(r'action=["\']([^"\']*editar_colaborador[^"\']*)["\']', content)
if action_match:
    form_action = action_match.group(1)
    print(f"   ✓ Found form action: {form_action}")
else:
    print(f"   ✗ Could not find form action URL")
    # Try to construct it manually
    form_action = '/procedures/perfis/1/colaboradores/editar/'
    print(f"   → Using manual URL: {form_action}")

# Find an existing ColaboradorPerfil to edit
print(f"\n3. Looking for ColaboradorPerfil to edit...")
cp_list = ColaboradorPerfil.objects.filter(perfil_id=1)[:1]
if cp_list:
    cp = cp_list[0]
    print(f"   ✓ Found ColaboradorPerfil: {cp.id}")
else:
    print(f"   ✗ No ColaboradorPerfil found, using cp_id=1 anyway")
    cp_id = 1

if cp_list:
    cp_id = cp.id

# Test POST without CSRF token first (should fail)
print(f"\n4. Test POST WITHOUT CSRF token...")
response = client.post(
    form_action,
    {'cp_id': str(cp_id)},
    follow=False
)
print(f"   Response status: {response.status_code}")
if response.status_code == 403:
    print(f"   ✓ Correctly rejected (403 Forbidden)")
else:
    print(f"   ⚠ Status {response.status_code} (expected 403)")

# Test POST WITH CSRF token
print(f"\n5. Test POST WITH CSRF token...")
response = client.post(
    form_action,
    {'csrfmiddlewaretoken': csrf_token, 'cp_id': str(cp_id)},
    follow=False,
    HTTP_HOST='localhost:18000'
)
print(f"   Response status: {response.status_code}")

if response.status_code in [200, 302]:
    print(f"   ✓ POST ACCEPTED!")
    if response.status_code == 302:
        print(f"   Redirect to: {response.get('Location', 'N/A')}")
elif response.status_code == 403:
    print(f"   ✗ POST REJECTED (403 CSRF)")
    # Try to find error message
    if b'CSRF' in response.content:
        # Extract error message
        error_match = re.search(b'Reason given for failure:.*?<li>([^<]+)</li>', response.content, re.DOTALL)
        if error_match:
            error = error_match.group(1).decode('utf-8').strip()
            print(f"   Error: {error}")
else:
    print(f"   ? Unexpected status: {response.status_code}")

print("\n" + "=" * 70)
