#!/usr/bin/env python
"""
Clear the stamped certificate to allow re-stamping
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

# Check if there's a stamped certificate
if not historico.certificado_carimbado:
    print("✅ No stamped certificate to remove")
    sys.exit(0)

print(f"\n📋 Current state:")
print(f"   Original: {historico.certificado.name if historico.certificado else '(empty)'}")
print(f"   Stamped: {historico.certificado_carimbado.name}")

# Delete the stamped certificate file
stamped_file_path = historico.certificado_carimbado.path
if os.path.exists(stamped_file_path):
    os.remove(stamped_file_path)
    print(f"\n🗑️  Deleted file: {stamped_file_path}")

# Clear the database field
historico.certificado_carimbado.delete()
historico.certificado_validado = False
historico.save()

print(f"\n✅ Stamped certificate removed from database!")
print(f"   certificado_carimbado: (empty)")
print(f"   certificado_validado: {historico.certificado_validado}")

print(f"\n✅ You can now re-stamp the original certificate!")
