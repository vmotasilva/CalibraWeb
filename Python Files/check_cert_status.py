#!/usr/bin/env python
"""
Check the certificate status
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
print(f"  certificado exists: {bool(historico.certificado)}")
if historico.certificado:
    print(f"    file: {historico.certificado}")
    print(f"    size: {historico.certificado.size} bytes")

print(f"\n  certificado_carimbado exists: {bool(historico.certificado_carimbado)}")
if historico.certificado_carimbado:
    print(f"    file: {historico.certificado_carimbado}")
    print(f"    size: {historico.certificado_carimbado.size} bytes")

print(f"\n  certificado_validado: {historico.certificado_validado}")

print("\n🔍 Form condition:")
print(f"  not historico.certificado_carimbado: {not historico.certificado_carimbado}")
print(f"  historico.certificado: {bool(historico.certificado)}")
print(f"  Both true (form shows): {not historico.certificado_carimbado and bool(historico.certificado)}")
