#!/usr/bin/env python
"""
Create admin superuser for local testing.
Credentials:
  - Username: admin
  - Email: admin@calibraweb.local
  - Password: TestPass123456!@#
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# Check if admin exists
if not User.objects.filter(username='admin').exists():
    user = User.objects.create_superuser(
        username='admin',
        email='admin@calibraweb.local',
        password='TestPass123456!@#'
    )
    print('[CREATED] Superuser admin criado com sucesso!')
else:
    user = User.objects.get(username='admin')
    print('[EXISTS] Superuser admin ja existe')

# Verify
print('\n[INFO] Credenciais de acesso:')
print(f'[OK] Username: {user.username}')
print(f'[OK] Email: {user.email}')
print(f'[OK] Is Superuser: {user.is_superuser}')
print(f'[OK] Is Staff: {user.is_staff}')
print('\n[INFO] Use estas credenciais no Django Admin:')
print('       http://127.0.0.1:8000/admin/')
print('       Username: admin')
print('       Password: TestPass123456!@#')
