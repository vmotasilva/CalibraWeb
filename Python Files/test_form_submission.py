#!/usr/bin/env python
"""
Test form submission using manage.py shell
"""
import os
import sys
os.chdir(r'c:\CalibraWeb')

# Adjust Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from metrologia.models import HistoricoCalibracao

# Get the historico
historico = HistoricoCalibracao.objects.filter(id=127).first()
if not historico:
    print("❌ Historico não encontrado")
    sys.exit(1)

print(f"✅ Historico encontrado: {historico.id}")

# Get the user
user = User.objects.filter(is_staff=True).first()
if not user:
    print("❌ User não encontrado")
    sys.exit(1)

print(f"✅ User encontrado: {user.username}")

# Create client
client = Client()
client.login(username=user.username, password='admin')

# Test data
post_data = {
    'resultado_carimbo': 'APROVADO_SEM_CORRECAO',
    'data_validacao_carimbo': '2024-01-15',
    'nome_validador': user.get_full_name() or user.username,
    'carimbo_x': '150',
    'carimbo_y': '200',
    'carimbo_page': '1',
}

print("\n📋 POST Data:")
for key, value in post_data.items():
    print(f"  {key}: {value}")

# Make POST request
url = f'/metrologia/historico/{historico.id}/aplicar-carimbo/'
print(f"\n🔄 POSTing to {url}...")

response = client.post(url, data=post_data, follow=False)

print(f"\n📊 Response Status: {response.status_code}")

if response.status_code == 302:
    print("✅ Redirect successful!")
    print(f"Location: {response.get('Location')}")
elif response.status_code == 500:
    print("❌ Server error 500")
    if hasattr(response, 'content'):
        print(f"Error content (first 500 chars): {response.content[:500].decode('utf-8', errors='ignore')}")
else:
    print(f"Response content preview: {response.content[:200]}")
