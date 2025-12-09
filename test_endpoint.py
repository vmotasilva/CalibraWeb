#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User

# Create a test client
client = Client()

# Create a test user if it doesn't exist
user, created = User.objects.get_or_create(
    username='testuser',
    defaults={'email': 'test@test.com'}
)
if created:
    user.set_password('testpass123')
    user.save()

# Login with the test user
client.login(username='testuser', password='testpass123')

# Try to access the URL with proper HTTP_HOST
try:
    response = client.get('/api/imp-inst/', HTTP_HOST='localhost')
    print(f"Status Code: {response.status_code}")
    if response.status_code != 200:
        print(f"Response content (first 1000 chars):")
        print(response.content.decode('utf-8', errors='ignore')[:1000])
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
