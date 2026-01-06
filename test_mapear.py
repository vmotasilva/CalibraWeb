#!/usr/bin/env python
# coding: utf-8
"""
Script para testar a funcionalidade da página Mapear Placeholders
"""
import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User

# Criar cliente de teste
client = Client()

# Obter ou criar usuário de teste
user, created = User.objects.get_or_create(username='testuser', defaults={'is_staff': True, 'is_superuser': True})

# Fazer login
client.force_login(user)

# Acessar a página Mapear Placeholders
response = client.get('/procedures/templates-presenca/5/mapear/')
print(f"Status: {response.status_code}")

content = response.content.decode()

# Verificar componentes
checks = {
    "data-placeholder": "Placeholders found",
    "pdf-canvas": "PDF Canvas found",
    "pdf-click-mode": "Click-mode toggle found",
    "pdf_viewer.js": "pdf_viewer.js loaded",
    "pdf.min.js": "PDF.js CDN loaded",
    "mapear_template_fields.css": "CSS loaded"
}

for check, label in checks.items():
    found = "YES" if check in content else "NO"
    print(f"{label}: {found}")

# Contar placeholders
count = content.count('data-placeholder')
print(f"\nTotal placeholders: {count}")


