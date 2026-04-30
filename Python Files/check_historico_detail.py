#!/usr/bin/env python
"""
Check the historico 127 database record in detail
"""
import os
import sys
os.chdir(r'c:\CalibraWeb')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from metrologia.models import HistoricoCalibracao

# Get historico
historico = HistoricoCalibracao.objects.filter(id=127).first()
if not historico:
    print("❌ Historico not found")
    sys.exit(1)

print(f"📌 Historico ID: {historico.id}")
print(f"   Description: {historico}")
print(f"\n   certificado field value: '{historico.certificado}'")
print(f"   certificado_carimbado field value: '{historico.certificado_carimbado}'")

# List all fields
print(f"\n📋 All fields:")
for field in historico._meta.fields:
    value = getattr(historico, field.name)
    if field.name.startswith('certificado'):
        print(f"   {field.name}: {value} (type: {type(value)})")

# Try to access the field files directly
print(f"\n🔍 Checking actual stored values:")
print(f"   certificado.name: '{historico.certificado.name if historico.certificado else 'EMPTY'}'")
print(f"   certificado_carimbado.name: '{historico.certificado_carimbado.name if historico.certificado_carimbado else 'EMPTY'}'")
