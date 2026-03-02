#!/usr/bin/env python
"""
Test if CSRF token is rendered in template
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(__file__))

django.setup()

from django.test import Client
from django.contrib.auth.models import User
import re

print("=" * 70)
print("CSRF TOKEN RENDERING TEST")
print("=" * 70)

# Create client
client = Client()

# Create or get user
try:
    user = User.objects.get(username='admin')
except User.DoesNotExist:
    user = User.objects.create_superuser('admin', 'admin@test.com', 'admin123')

# Login
client.login(username='admin', password='admin123')

# Get the perfil page
print("\n1. Fetching /procedures/perfis/1/...")
response = client.get('/procedures/perfis/1/')
print(f"   Response status: {response.status_code}")

if response.status_code == 200:
    content = response.content.decode('utf-8')
    
    # Search for CSRF token in various formats
    patterns = [
        (r'<input[^>]*name=["\']csrfmiddlewaretoken["\'][^>]*value=["\']([^"\']+)["\']', 'HTML input format'),
        (r"<input[^>]*name='csrfmiddlewaretoken'[^>]*value='([^']+)'", 'HTML input format (single quotes)'),
        (r'{% csrf_token %}', 'Template tag (not rendered)'),
        (r"'X-CSRFToken':\s*'([^']+)'", 'JavaScript header'),
        (r'"csrfmiddlewaretoken":\s*"([^"]+)"', 'JSON format'),
    ]
    
    print(f"\n2. Searching for CSRF token in response (length: {len(content)} chars)...")
    
    for pattern, desc in patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            print(f"\n   ✓ Found: {desc}")
            for i, match in enumerate(matches[:2]):  # Show first 2 matches
                if len(match) > 50:
                    print(f"     [{i+1}] {match[:30]}...{match[-20:]}")
                else:
                    print(f"     [{i+1}] {match}")
        else:
            if 'not rendered' not in desc.lower():
                print(f"   ✗ Not found: {desc}")
    
    # Check if page has the modal form
    print(f"\n3. Checking for form elements...")
    if 'form-editar-colaborador' in content:
        print(f"   ✓ Form 'form-editar-colaborador' found")
    else:
        print(f"   ✗ Form 'form-editar-colaborador' NOT found")
    
    if 'editar_colaborador_perfil' in content:
        print(f"   ✓ Action URL 'editar_colaborador_perfil' found")
    else:
        print(f"   ✗ Action URL 'editar_colaborador_perfil' NOT found")
    
    if '<input type="hidden" name="cp_id"' in content:
        print(f"   ✓ Hidden input 'cp_id' found")
    else:
        print(f"   ✗ Hidden input 'cp_id' NOT found")
    
    # Check session
    print(f"\n4. Checking session...")
    if 'sessionid' in response.cookies:
        print(f"   ✓ Session cookie 'sessionid' set")
        print(f"     Value: {response.cookies['sessionid'].value[:30]}...")
    else:
        print(f"   ✗ Session cookie 'sessionid' NOT set")
    
    # Get CSRF token from context (may be None)
    print(f"\n5. Checking context CSRF token...")
    if response.context is not None:
        if 'csrf_token' in response.context:
            csrf_from_context = response.context['csrf_token']
            print(f"   ✓ csrf_token in context")
            print(f"     Value: {csrf_from_context[:30]}...{csrf_from_context[-20:]}")
        else:
            print(f"   ✗ csrf_token NOT in context")
            print(f"     Available keys: {list(response.context.keys())}")
    else:
        print(f"   ✓ Response context is None (OK for template-only pages)")
    
    
    # Try to find token in meta tags
    meta_csrf = re.search(r'<meta[^>]*name=["\']csrf["\'][^>]*content=["\']([^"\']+)["\']', content)
    if meta_csrf:
        print(f"   ✓ Found CSRF token in meta tag")
        print(f"     Value: {meta_csrf.group(1)[:30]}...{meta_csrf.group(1)[-20:]}")
    
else:
    print(f"   ✗ Page returned status {response.status_code}")
    print(f"     Content preview: {response.content[:200]}")

print("\n" + "=" * 70)
