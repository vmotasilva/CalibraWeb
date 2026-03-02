#!/usr/bin/env python
"""
Check the current state of historico 127 certificado_carimbado
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

print(f"📌 Historico: {historico}")
print(f"\n📋 Certificate Status:")
print(f"  certificado: {bool(historico.certificado)} - {historico.certificado.name if historico.certificado else '(empty)'}")
print(f"  certificado_carimbado: {bool(historico.certificado_carimbado)} - {historico.certificado_carimbado.name if historico.certificado_carimbado else '(empty)'}")
print(f"  certificado_validado: {historico.certificado_validado}")

if historico.certificado_carimbado:
    print(f"\n✅ Carimbo exists - button should appear!")
    carimbado_path = historico.certificado_carimbado.path
    if os.path.exists(carimbado_path):
        size = os.path.getsize(carimbado_path)
        print(f"   File: {carimbado_path}")
        print(f"   Size: {size} bytes")
else:
    print(f"\n❌ No carimbo found - button will NOT appear")
