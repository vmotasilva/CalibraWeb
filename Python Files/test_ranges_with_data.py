#!/usr/bin/env python
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from metrologia.models import HistoricoCalibracao

# Create test user if it doesn't exist
user, created = User.objects.get_or_create(
    username='testuser',
    defaults={'is_staff': True, 'is_superuser': True}
)
if created:
    user.set_password('testpass123')
    user.save()

# Find a historico with results
historico = HistoricoCalibracao.objects.filter(resultados_faixa__isnull=False).distinct().first()

if not historico:
    print("No historico with results found")
else:
    print(f"Testing with historico: {historico.id} ({historico})")
    print(f"Number of resultados_faixa: {historico.resultados_faixa.count()}")
    
    client = Client()
    client.login(username='testuser', password='testpass123')
    
    response = client.get(f'/metrologia/historico/{historico.id}/editar/')
    
    print(f"Response Status: {response.status_code}")
    
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
            # Count modals
            import re
            modal_count = len(re.findall(r'editResultModal', content))
            print(f"Number of range result rows: {modal_count}")
        else:
            print("\n✗ FAIL: Measurement ranges are still not displaying")
