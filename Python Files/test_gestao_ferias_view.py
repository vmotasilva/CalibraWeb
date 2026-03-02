#!/usr/bin/env python
"""Teste para reproduzir erro 500 na view de gestão de férias"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import RequestFactory, Client
from django.contrib.auth.models import User
from rh.views.views import gestao_ferias_view
from rh.models import Colaborador, Ferias
from organization.models import Setor
from datetime import date, timedelta

# Setup
factory = RequestFactory()
client = Client()

# Verificar se há dados
print(f"Colaboradores: {Colaborador.objects.count()}")
print(f"Férias: {Ferias.objects.count()}")
print(f"Usuários: {User.objects.count()}")

# Criar admin se não existir
from django.utils import timezone
admin, created = User.objects.get_or_create(
    username='testadmin',
    defaults={
        'is_staff': True, 
        'is_superuser': True,
        'last_login': timezone.now()
    }
)
print(f"\nAdmin criado: {created}")

# Testar com cliente autenticado
print("\n=== Testando com Django Client ===")
client.force_login(admin)

try:
    response = client.get('/rh/gestao-ferias/')
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.get('Content-Type', 'N/A')}")
    
    if response.status_code != 200:
        print(f"ERRO: {response.status_code}")
        if hasattr(response, 'context') and response.context:
            if 'exception' in response.context:
                print(f"Exception: {response.context['exception']}")
        # Mostrar primeiros 500 caracteres do conteúdo
        print(f"Response body (primeiros 500 chars):\n{response.content[:500].decode('utf-8', errors='ignore')}")
    else:
        print("✅ Sucesso!")
        
except Exception as e:
    print(f"❌ Exceção: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
