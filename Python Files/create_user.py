#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User

user, created = User.objects.get_or_create(
    username='admin',
    defaults={
        'is_staff': True,
        'is_superuser': True,
        'email': 'admin@example.com'
    }
)

if created:
    user.set_password('admin123')
    user.save()
    print(f"✓ User 'admin' created with password 'admin123'")
else:
    print(f"✓ User 'admin' already exists")
