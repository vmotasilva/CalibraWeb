#!/usr/bin/env python
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client

client = Client()

# Test with historico 127 that we know has ranges
response = client.get('/metrologia/historico/127/editar/')

print(f"Status: {response.status_code}")

if response.status_code == 200:
    content = response.content.decode('utf-8')
    
    # Check for the key indicators
    has_title = 'Resultados de Medição por Faixa' in content
    has_empty_msg = 'Nenhum resultado de faixa cadastrado ainda' in content
    has_ranges = 'editResultModal' in content
    
    print(f"Has measurement ranges section title: {has_title}")
    print(f"Shows 'no results' message: {has_empty_msg}")
    print(f"Has range edit modals: {has_ranges}")
    
    if has_ranges:
        print("\n✓ SUCCESS: Measurement ranges are now displaying!")
    else:
        print("\n✗ FAIL: Measurement ranges are still not displaying")
