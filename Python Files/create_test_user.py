#!/usr/bin/env python
"""
Create a test user for testing CSRF fix
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(__file__))

django.setup()

from django.contrib.auth.models import User

# Try to create or get a test user
try:
    user = User.objects.get(username='admin')
    print(f"User 'admin' already exists")
except User.DoesNotExist:
    user = User.objects.create_superuser('admin', 'admin@test.com', 'admin123')
    print(f"Created superuser 'admin' with password 'admin123'")

print("\n✓ You can now login with username: admin, password: admin123")
print("✓ Go to http://localhost:18000/admin/ or http://localhost:18000/ to test")
