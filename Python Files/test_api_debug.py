#!/usr/bin/env python
import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from procedures.models import Disciplina, DisciplinaProcedimento, Procedimento
from django.test import Client
from django.contrib.auth.models import User

try:
    # Verificar se disciplina 2 existe
    disc = Disciplina.objects.get(id=2)
    print(f"✓ Disciplina 2 existe: {disc.codigo}")
    
    # Contar procedimentos associados
    count = DisciplinaProcedimento.objects.filter(disciplina=disc).count()
    print(f"✓ Procedimentos associados: {count}")
    
    # Testar API opcoes-filtro com autenticação
    client = Client()
    
    # Criar usuário de teste ou usar admin
    user = User.objects.filter(is_staff=True).first()
    if user:
        client.force_login(user)
        print(f"✓ Usuário autenticado: {user.username}")
    else:
        print("⚠ Nenhum usuário staff encontrado")
    
    response = client.get('/procedures/disciplinas/2/api/opcoes-filtro/')
    print(f"✓ GET opcoes-filtro status: {response.status_code}")
    
    if response.status_code == 200:
        print(f"  Response: {response.json()}")
    else:
        print(f"  ✗ Error: {response.content[:500]}")
        
    # Testar API filtrar-procedimentos
    response = client.get('/procedures/disciplinas/2/api/filtrar-procedimentos/')
    print(f"✓ GET filtrar-procedimentos status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"  Response: {len(data)} procedimentos encontrados")
    else:
        print(f"  ✗ Error: {response.content[:500]}")
        
except Disciplina.DoesNotExist:
    print("✗ Disciplina 2 não encontrada!")
    sys.exit(1)
except Exception as e:
    print(f"✗ Erro: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n✅ Teste completo!")
