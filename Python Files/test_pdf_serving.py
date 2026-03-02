#!/usr/bin/env python
# coding: utf-8
"""
Script para testar PDF serving
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User

# Criar cliente de teste
client = Client()

# Obter ou criar usuário de teste
user, created = User.objects.get_or_create(
    username='testuser',
    defaults={'is_staff': True, 'is_superuser': True}
)

# Fazer login
client.force_login(user)

print("=" * 60)
print("TESTE PDF SERVING")
print("=" * 60)

# Template ID
template_id = 5

# Teste 1: Verificar se template existe
from procedures.models import TemplateListaPresenca
try:
    template = TemplateListaPresenca.objects.get(id=template_id)
    print(f"\n[1/3] Template encontrado: {template.nome}")
    print(f"  Tem PDF? {bool(template.arquivo_pdf_template)}")
    if template.arquivo_pdf_template:
        print(f"  Arquivo: {template.arquivo_pdf_template.name}")
        print(f"  Tamanho: {template.arquivo_pdf_template.size} bytes")
except:
    print("\n[1/3] Template não encontrado")

# Teste 2: Acessar endpoint PDF
print("\n[2/3] Testando endpoint de PDF...")
response = client.get(f'/procedures/templates-presenca/{template_id}/pdf/')
print(f"  Status: {response.status_code}")
print(f"  Content-Type: {response.get('Content-Type', 'N/A')}")
print(f"  Content-Length: {response.get('Content-Length', 'N/A')}")
print(f"  Tamanho da resposta: {len(response.content)} bytes")

# Teste 3: Acessar página mapear
print("\n[3/3] Testando página mapear...")
response = client.get(f'/procedures/templates-presenca/{template_id}/mapear/')
print(f"  Status: {response.status_code}")
content = response.content.decode()
print(f"  PDF_URL na página: {'Sim' if 'PDF_URL' in content else 'Não'}")
print(f"  Canvas presente: {'Sim' if 'pdf-canvas' in content else 'Não'}")
print(f"  PDF.js CDN presente: {'Sim' if 'pdf.min.js' in content else 'Não'}")

# Procurar pela URL do PDF no HTML
if 'const PDF_URL' in content:
    import re
    match = re.search(r"const PDF_URL = '([^']+)'", content)
    if match:
        pdf_url = match.group(1)
        print(f"  PDF URL extraída: {pdf_url}")
