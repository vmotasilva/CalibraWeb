#!/usr/bin/env python
"""
Teste rápido da página de planejamento
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User

# Criar/obter usuário
user = User.objects.filter(username='testuser').first()
if not user:
    user = User.objects.create_user(
        username='testuser',
        email='test@test.com',
        password='testpass123',
        is_staff=True,
        is_superuser=True
    )

# Fazer login e requisição
client = Client()
client.login(username='testuser', password='testpass123')
response = client.get('/procedures/planejamentos/novo/')

print(f"Status: {response.status_code}")

if response.status_code == 200:
    print("✅ Página carregou com sucesso!")
    
    # Verificar conteúdo importante
    content = response.content.decode('utf-8')
    
    checks = {
        'Modal colaboradores': 'id="colaboradoresModal"' in content,
        'Modal procedimento': 'id="procedimentoModal"' in content,
        'Script completo': '</script>' in content,
        'Block fechado': '{% endblock %}' not in content or 'endblock' in content,  
    }
    
    for name, result in checks.items():
        status = "✅" if result else "❌"
        print(f"{status} {name}")
else:
    print(f"❌ Erro ao carregar página: {response.status_code}")
    if response.status_code == 500:
        print("🔴 ERRO 500 DETECTADO!")
        print(response.content[:500])
