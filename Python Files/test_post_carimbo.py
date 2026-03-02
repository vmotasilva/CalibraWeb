#!/usr/bin/env python
"""Test POST to stamp view"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User

# Get test user
user = User.objects.first()
if not user:
    user = User.objects.create_user(username='testuser', password='test123')

print(f"✓ User: {user.username}")

# Create client
client = Client()
client.force_login(user)

# POST data
data = {
    'resultado': 'APROVADO_SEM_CORRECAO',
    'data_validacao': '2025-12-11',
    'nome_validador': 'Test User',
    'carimbo_x': '450',
    'carimbo_y': '100',
    'carimbo_page': '1',
}

print(f"✓ Data: {data}")

# Make request
try:
    response = client.post('/metrologia/historico/127/aplicar-carimbo/', data)
    print(f"✓ Status: {response.status_code}")
    
    if response.status_code != 302:
        print(f"❌ Expected 302 redirect, got {response.status_code}")
        if response.content:
            print(f"Content: {response.content[:500]}")
    else:
        print(f"✓ Redirect to: {response.url}")
        print("✅ POST successful!")
        
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
