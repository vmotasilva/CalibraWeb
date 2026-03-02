#!/usr/bin/env python
"""
Teste simples do formulário de Planejamento
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User

def main():
    print("=" * 60)
    print("🧪 TESTE DO FORMULÁRIO DE PLANEJAMENTO COM MODALS")
    print("=" * 60)
    
    # Criar usuário
    user = User.objects.filter(username='testuser').first()
    if not user:
        print("✅ Criando usuário de teste...")
        user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )
    
    client = Client()
    if not client.login(username='testuser', password='testpass123'):
        print("❌ Erro ao fazer login")
        return False
    
    print("✅ Login realizado")
    
    # Requisição ao formulário
    print("\n📋 Carregando formulário...")
    response = client.get('/procedures/planejamentos/novo/')
    
    if response.status_code == 200:
        print("✅ Formulário carregado (status 200)")
    else:
        print(f"❌ Erro ao carregar: {response.status_code}")
        if response.status_code == 302:
            print(f"   Redirecionado para: {response.url}")
        return False
    
    content = response.content.decode('utf-8')
    
    # Verificar elementos principais
    print("\n🔍 Verificando elementos...")
    
    checks = {
        'Modal colaboradores': 'id="colaboradoresModal"' in content,
        'Modal procedimento': 'id="procedimentoModal"' in content,
        'Lista colaboradores': 'id="colaboradores_list"' in content,
        'Lista procedimento': 'id="procedimento_list"' in content,
        'Função renderColaboradores': 'function renderColaboradores' in content,
        'Função renderProcedimentos': 'function renderProcedimentos' in content,
        'Input search colaborador': 'id="colaborador_search"' in content,
        'Input search procedimento': 'id="procedimento_search"' in content,
        'Hidden input colaboradores': 'id="colaboradores_hidden"' in content,
        'Hidden input procedimento': 'id="procedimento_hidden"' in content,
        'Botão modal colaborador': 'data-bs-target="#colaboradoresModal"' in content,
        'Botão modal procedimento': 'data-bs-target="#procedimentoModal"' in content,
    }
    
    all_passed = True
    for check_name, result in checks.items():
        status = "✅" if result else "❌"
        print(f"  {status} {check_name}")
        if not result:
            all_passed = False
    
    # Resumo
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ TODOS OS TESTES PASSARAM!")
        print("\n📝 O formulário está pronto com:")
        print("   • Modal para selecionar colaboradores")
        print("   • Modal para selecionar procedimentos")
        print("   • Listas para exibir seleções")
        print("   • Botões para adicionar itens")
        print("   • Busca/filtro nos modals")
    else:
        print("❌ ALGUNS ELEMENTOS ESTÃO FALTANDO!")
    print("=" * 60)
    
    return all_passed

if __name__ == '__main__':
    import sys
    success = main()
    sys.exit(0 if success else 1)
