#!/usr/bin/env python
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User

client = Client()

# Create test user if it doesn't exist
user, created = User.objects.get_or_create(
    username='testuser',
    defaults={'is_staff': True, 'is_superuser': True}
)
if created:
    user.set_password('testpass123')
    user.save()

# Login
client.login(username='testuser', password='testpass123')

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
        # Show a sample
        import re
        ranges = re.findall(r'<strong>([\d.]+)</strong> a <strong>([\d.]+)</strong>', content)
        if ranges:
            print(f"Found {len(ranges)} measurement ranges")
            print("Sample ranges:")
            for min_val, max_val in ranges[:3]:
                print(f"  {min_val} a {max_val}")
    else:
        print("\n✗ FAIL: Measurement ranges are still not displaying")
else:
    print(f"Failed to get page: {response.status_code}")
