#!/usr/bin/env python
"""
Verify the current state of certificates for historico 127
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
print(f"\n📋 Database State:")
print(f"  certificado field: '{historico.certificado.name if historico.certificado else '(empty)'}'")
print(f"  certificado_carimbado field: '{historico.certificado_carimbado.name if historico.certificado_carimbado else '(empty)'}'")
print(f"  certificado_validado: {historico.certificado_validado}")

print(f"\n📁 File System Check:")

# List all files related to this historico
print(f"\n  Looking for files with '127' or '521' (id pattern)...")
import glob

# Search in certificados folder
certificados_dir = r'c:\CalibraWeb\certificados'
all_files = glob.glob(f'{certificados_dir}/**/*', recursive=True)

relevant_files = [f for f in all_files if ('127' in f or '521' in f) and os.path.isfile(f)]

print(f"\n  Found {len(relevant_files)} files:")
for f in relevant_files:
    size = os.path.getsize(f)
    print(f"    - {os.path.relpath(f, certificados_dir)} ({size} bytes)")

# Check if the carimbado file exists in the actual filesystem
if historico.certificado_carimbado:
    carimbado_path = historico.certificado_carimbado.path
    print(f"\n  Carimbado file path from DB: {carimbado_path}")
    if os.path.exists(carimbado_path):
        size = os.path.getsize(carimbado_path)
        print(f"    ✅ File exists ({size} bytes)")
    else:
        print(f"    ❌ File not found!")

# Check if original file exists somewhere
print(f"\n  Searching for original certificate files (Cert_521, LE-02)...")
original_candidates = glob.glob(f'{certificados_dir}/Cert_521*.pdf') + glob.glob(f'{certificados_dir}/*LE-02*.pdf')
for f in original_candidates:
    if os.path.isfile(f):
        size = os.path.getsize(f)
        print(f"    - {os.path.basename(f)} ({size} bytes)")
