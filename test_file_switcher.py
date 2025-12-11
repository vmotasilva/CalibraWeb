#!/usr/bin/env python
"""Test file switcher functionality for certificates."""
import os
import django
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from metrologia.models import HistoricoCalibracao
from django.contrib.auth.models import User

# Initialize test client
client = Client()

# Try to login
user = User.objects.first()
if user:
    # For test client, we just force login
    client.force_login(user)
    print(f"✓ Logged in as: {user.username}")
else:
    print("⚠ No user found, using unauthenticated client")

# Get historico 127
historico = HistoricoCalibracao.objects.get(id=127)
print(f"\n{'='*60}")
print(f"Testando Historico ID: 127")
print(f"{'='*60}")

# Check if certificates exist
print(f"\n✓ Certificado Original: {bool(historico.certificado)}")
if historico.certificado:
    print(f"  - Path: {historico.certificado.name}")
    print(f"  - Size: {historico.certificado.size} bytes")

print(f"\n✓ Certificado Carimbado: {bool(historico.certificado_carimbado)}")
if historico.certificado_carimbado:
    print(f"  - Path: {historico.certificado_carimbado.name}")
    print(f"  - Size: {historico.certificado_carimbado.size} bytes")

# Test get_certificado_bytes_view with tipo parameter
print(f"\n{'='*60}")
print("Testando GET /metrologia/historico/127/certificado-bytes/")
print(f"{'='*60}")

# Test tipo=original
print(f"\n[TEST] Request with tipo=original")
response = client.get(f'/metrologia/historico/127/certificado-bytes/?tipo=original')
print(f"  - Status Code: {response.status_code}")
if response.status_code == 200:
    print(f"  - Content-Type: {response.get('Content-Type')}")
    print(f"  - Content-Length: {len(response.content)} bytes")
    print(f"  - ✓ Original PDF loaded successfully")
else:
    print(f"  - ✗ Error: {response.content}")

# Test tipo=carimbado
print(f"\n[TEST] Request with tipo=carimbado")
response = client.get(f'/metrologia/historico/127/certificado-bytes/?tipo=carimbado')
print(f"  - Status Code: {response.status_code}")
if response.status_code == 200:
    print(f"  - Content-Type: {response.get('Content-Type')}")
    print(f"  - Content-Length: {len(response.content)} bytes")
    print(f"  - ✓ Stamped PDF loaded successfully")
else:
    print(f"  - ✗ Error: {response.content}")

# Test default (no parameter)
print(f"\n[TEST] Request with no tipo parameter (default)")
response = client.get(f'/metrologia/historico/127/certificado-bytes/')
print(f"  - Status Code: {response.status_code}")
if response.status_code == 200:
    print(f"  - Content-Type: {response.get('Content-Type')}")
    print(f"  - Content-Length: {len(response.content)} bytes")
    print(f"  - ✓ Default PDF loaded successfully")
else:
    print(f"  - ✗ Error: {response.content}")

# Test download with tipo parameter
print(f"\n{'='*60}")
print("Testando GET /metrologia/historico/127/download/")
print(f"{'='*60}")

# Test tipo=original download
print(f"\n[TEST] Download with tipo=original")
response = client.get(f'/metrologia/historico/127/download/?tipo=original')
print(f"  - Status Code: {response.status_code}")
if response.status_code == 200:
    print(f"  - Content-Type: {response.get('Content-Type')}")
    print(f"  - Content-Disposition: {response.get('Content-Disposition')}")
    content_length = response.get('Content-Length', 'streaming')
    print(f"  - Content-Length: {content_length} bytes")
    print(f"  - ✓ Original download successful")
else:
    print(f"  - ✗ Error: {response.content}")

# Test tipo=carimbado download
print(f"\n[TEST] Download with tipo=carimbado")
response = client.get(f'/metrologia/historico/127/download/?tipo=carimbado')
print(f"  - Status Code: {response.status_code}")
if response.status_code == 200:
    print(f"  - Content-Type: {response.get('Content-Type')}")
    print(f"  - Content-Disposition: {response.get('Content-Disposition')}")
    content_length = response.get('Content-Length', 'streaming')
    print(f"  - Content-Length: {content_length} bytes")
    print(f"  - ✓ Stamped download successful")
else:
    print(f"  - ✗ Error: {response.content}")

print(f"\n{'='*60}")
print("✓ All tests completed!")
print(f"{'='*60}\n")
