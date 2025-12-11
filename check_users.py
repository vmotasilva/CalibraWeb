#!/usr/bin/env python
"""
Get the admin user and test login properly
"""
import os
import sys
os.chdir(r'c:\CalibraWeb')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.test import Client
from django.contrib.auth.models import User

# Get all users
users = User.objects.all()
print(f"Total de usuários: {len(users)}")

for user in users:
    print(f"\n📌 User: {user.username}")
    print(f"   is_staff: {user.is_staff}")
    print(f"   is_superuser: {user.is_superuser}")
    print(f"   full_name: {user.get_full_name()}")

# Try to login with different passwords
print("\n\n🔐 Testing login...")
client = Client()

# Try with the admin user
admin_user = User.objects.filter(username='admin').first()
if admin_user:
    print(f"\nTesting with user 'admin'...")
    # We don't have password, but let's try to see what happens
    response = client.get('/metrologia/historico/127/editar/')
    print(f"GET request status: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ Already authenticated!")
    elif response.status_code == 302:
        print("❌ Not authenticated, redirected to:", response.get('Location'))
