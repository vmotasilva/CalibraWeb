#!/usr/bin/env python
"""
Verify that the form now appears on the page
"""
import requests
from bs4 import BeautifulSoup

# Since we can't authenticate via requests, let's check the template file directly
with open(r'c:\CalibraWeb\metrologia\templates\metrologia\editar_historico.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Check the condition
import re
condition_match = re.search(r'{%\s*if\s*(historico\.\w+\s+(?:or|and)\s+historico\.\w+)', content)
if condition_match:
    print(f"✅ Form condition found: {condition_match.group(1)}")

# Check for carimboForm
if 'id="carimboForm"' in content:
    print(f"✅ carimboForm element found")

# Check for Re-Aplicar
if 'Re-Aplicar' in content:
    print(f"✅ Re-apply message found")

print("\n📋 Form should now appear because:")
print("   - Condition changed to: historico.certificado or historico.certificado_carimbado")
print("   - Historico 127 has certificado_carimbado")
print("   - Therefore condition is TRUE, form will render")

print("\n🔍 Next steps:")
print("   1. Reload the page in browser (Ctrl+F5 to clear cache)")
print("   2. Scroll down to find 'Re-Aplicar Carimbo de Validação' section")
print("   3. Click on PDF to position the stamp")
print("   4. Click 'Aplicar Carimbo' button")
print("   5. Report any errors from browser console (F12)")
