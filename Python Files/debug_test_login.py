#!/usr/bin/env python
import os
import sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_test')

import django
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from django.urls import reverse
import uuid

# Run migrations
from django.core.management import call_command
call_command('migrate', '--run-syncdb', verbosity=0)

# Create a test user
user = User.objects.create_user(username=f'test_{uuid.uuid4().hex[:8]}', password='test123')
print(f"Created user: {user.username}")

# Create a client and log in
client = Client()
client.force_login(user)
print("User force_login called")

# Try to access the URL
url = reverse('acoes:plano_acao_list')
print(f"Accessing URL: {url}")

response = client.get(url)
print(f"Status Code: {response.status_code}")
print(f"Redirect Location: {response.get('Location', 'No redirect header')}")

if response.status_code in [301, 302, 303, 307, 308]:
    print(f"REDIRECT DETECTED to: {response.url}")
else:
    print(f"SUCCESS - Got page!")

