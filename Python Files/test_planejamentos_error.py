#!/usr/bin/env python
import os
import django
import sys
import traceback

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User

try:
    client = Client()
    
    # Tentar sem autenticação
    print("📍 Testando GET /procedures/planejamentos/ (sem autenticação)...")
    response = client.get('/procedures/planejamentos/')
    print(f"Status: {response.status_code}")
    
    if response.status_code == 500:
        print("❌ ERRO 500 ENCONTRADO!")
        print(f"Content: {response.content[:1000]}")
    
    # Tentar com autenticação
    user = User.objects.filter(is_staff=True).first()
    if user:
        client.force_login(user)
        print(f"\n📍 Testando com usuário autenticado: {user.username}")
        response = client.get('/procedures/planejamentos/')
        print(f"Status: {response.status_code}")
        
        if response.status_code == 500:
            print("❌ ERRO 500 ENCONTRADO!")
            print(f"Content:\n{response.content.decode()[:2000]}")
        else:
            print(f"✓ Resposta OK (content-length: {len(response.content)})")
            
except Exception as e:
    print(f"❌ Erro Python: {e}")
    traceback.print_exc()
