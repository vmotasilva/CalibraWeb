#!/usr/bin/env python
"""
Manually update the historico 127 to mark the stamped certificate
"""
import os
import sys
os.chdir(r'c:\CalibraWeb')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from metrologia.models import HistoricoCalibracao
from django.core.files.base import ContentFile

# Get historico
historico = HistoricoCalibracao.objects.filter(id=127).first()
if not historico:
    print("❌ Historico not found")
    sys.exit(1)

print(f"📌 Historico: {historico}")

# Check if the file exists in filesystem
stamped_file = r'c:\CalibraWeb\media\certificados\carimbados\certificado_carimbado_127.pdf'
if not os.path.exists(stamped_file):
    print(f"❌ Stamped file not found: {stamped_file}")
    sys.exit(1)

print(f"✅ Found stamped file: {stamped_file}")
print(f"   Size: {os.path.getsize(stamped_file)} bytes")

# Read the file
with open(stamped_file, 'rb') as f:
    file_content = f.read()

print(f"✅ File read: {len(file_content)} bytes")

# Save to model
filename = 'certificado_carimbado_127.pdf'
historico.certificado_carimbado.save(filename, ContentFile(file_content), save=True)

print(f"✅ Saved to model!")
print(f"   Field: {historico.certificado_carimbado.name}")
print(f"   Size: {historico.certificado_carimbado.size} bytes")

# Update flag
historico.certificado_validado = True
historico.save()

print(f"\n✅ Database updated!")
print(f"   certificado_carimbado: {historico.certificado_carimbado.name}")
print(f"   certificado_validado: {historico.certificado_validado}")
