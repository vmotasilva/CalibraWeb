#!/usr/bin/env python
"""
Test the aplicar_carimbo_certificado_view directly with fresh data
"""
import os
import sys
os.chdir(r'c:\CalibraWeb')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from metrologia.models import HistoricoCalibracao
from qms.views import aplicar_carimbo_certificado_view
import traceback

print("🔍 Testing aplicar_carimbo_certificado_view directly...")

# Get objects
historico = HistoricoCalibracao.objects.filter(id=127).first()
if not historico:
    print("❌ Historico not found")
    sys.exit(1)

user = User.objects.filter(is_staff=True).first()
if not user:
    print("❌ User not found")
    sys.exit(1)

print(f"✅ Historico: {historico}")
print(f"✅ User: {user}")
print(f"✅ certificado exists: {bool(historico.certificado)}")
print(f"✅ certificado_carimbado exists: {bool(historico.certificado_carimbado)}")

# Create a POST request with realistic data
factory = RequestFactory()
post_data = {
    'resultado': 'APROVADO_SEM_CORRECAO',
    'data_validacao': '2024-12-11',
    'nome_validador': 'Vinicius Mota Silva',
    'carimbo_x': '150',
    'carimbo_y': '200',
    'carimbo_page': '1',
}

request = factory.post(f'/metrologia/historico/{historico.id}/aplicar-carimbo/', data=post_data)
request.user = user

print("\n📋 POST Data:")
for key, value in post_data.items():
    print(f"  {key}: {value}")

print("\n🔄 Calling view directly...")

try:
    response = aplicar_carimbo_certificado_view(request, historico.id)
    print(f"\n✅ Response status: {response.status_code}")
    if hasattr(response, 'url'):
        print(f"   Redirect to: {response.url}")
except Exception as e:
    print(f"\n❌ Error in view:")
    print(f"  Type: {type(e).__name__}")
    print(f"  Message: {str(e)}")
    print("\n📋 Full traceback:")
    traceback.print_exc()
