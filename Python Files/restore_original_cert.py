#!/usr/bin/env python
"""
Restore the original certificate for historico 127
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

# Check if original certificate file exists in filesystem
original_file_path = r'c:\CalibraWeb\certificados\Cert_521_LE-02.pdf'
if not os.path.exists(original_file_path):
    print(f"❌ Original file not found: {original_file_path}")
    sys.exit(1)

print(f"✅ Found original file: {original_file_path}")

# Get file size
file_size = os.path.getsize(original_file_path)
print(f"   File size: {file_size} bytes")

# Read the file
with open(original_file_path, 'rb') as f:
    file_content = f.read()

print(f"✅ File read successfully: {len(file_content)} bytes")

# Check if certificado field is empty
if historico.certificado:
    print(f"⚠️  Certificado field already has value: {historico.certificado.name}")
    response = input("Do you want to overwrite it? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled.")
        sys.exit(1)

# Save the file to the certificado field
filename = os.path.basename(original_file_path)
historico.certificado.save(filename, ContentFile(file_content), save=True)

print(f"✅ Certificado field restored!")
print(f"   Field value: {historico.certificado.name}")
print(f"   File size in DB: {historico.certificado.size} bytes")

# Verify
historico.refresh_from_db()
print(f"\n✅ Verification:")
print(f"   certificado: {historico.certificado.name}")
print(f"   certificado_carimbado: {historico.certificado_carimbado.name if historico.certificado_carimbado else '(empty)'}")
print(f"   certificado_validado: {historico.certificado_validado}")
