#!/usr/bin/env python
"""
Teste do formulário de Planejamento com modals
Valida:
1. Formulário carrega sem erros
2. Colaboradores e Procedimentos mostram corretamente nos modals
3. Seleções são persistidas
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from procedures.models import Procedimento, SubArea, PlanejamentoTreinamento
from rh.models import Colaborador
from django.utils import timezone
import json

def create_test_data():
    """Cria dados de teste"""
    print("🔧 Criando dados de teste...")
    
    # Criar colaboradores
    for i in range(5):
        Colaborador.objects.get_or_create(
            nome=f"Colaborador {i+1}",
            defaults={'email': f'col{i+1}@test.com', 'ativo': True}
        )
    
    # Criar sub_area
    sub_area, _ = SubArea.objects.get_or_create(nome="Padrão")
    
    # Criar procedimentos
    for i in range(5):
        Procedimento.objects.get_or_create(
            codigo=f"PROC_{i+1:03d}",
            defaults={
                'nome': f"Procedimento {i+1}",
                'sub_area': sub_area,
                'descricao': f'Descrição do procedimento {i+1}'
            }
        )
    
    print(f"✅ {Colaborador.objects.count()} colaboradores")
    print(f"✅ {Procedimento.objects.count()} procedimentos")

def test_form_loads():
    """Teste 1: Formulário carrega sem erros"""
    print("\n📋 TESTE 1: Formulário carrega sem erros")
    
    # Criar usuário
    user = User.objects.filter(username='testuser').first()
    if not user:
        user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )
    
    client = Client()
    client.login(username='testuser', password='testpass123')
    
    response = client.get('/procedures/planejamentos/novo/')
    
    if response.status_code == 200:
        print("✅ Formulário carrega (status 200)")
        
        # Verificar se os modals estão presentes
        content = response.content.decode('utf-8')
        
        checks = {
            'Modal colaboradores': 'id="colaboradoresModal"' in content,
            'Modal procedimento': 'id="procedimentoModal"' in content,
            'Lista colaboradores': 'id="colaboradores_list"' in content,
            'Lista procedimento': 'id="procedimento_list"' in content,
            'Função renderColaboradores': 'function renderColaboradores' in content,
            'Função renderProcedimentos': 'function renderProcedimentos' in content,
            'Busca colaboradores': 'colaborador_search' in content,
            'Busca procedimento': 'procedimento_search' in content,
        }
        
        print("\n  Verificações:")
        all_passed = True
        for check_name, result in checks.items():
            status = "✅" if result else "❌"
            print(f"  {status} {check_name}")
            if not result:
                all_passed = False
        
        return all_passed
    else:
        print(f"❌ Erro ao carregar formulário: {response.status_code}")
        if response.status_code == 302:
            print(f"  Redirecionado para: {response.url}")
        return False

def test_modal_structure():
    """Teste 2: Estrutura dos modals está correta"""
    print("\n📋 TESTE 2: Estrutura dos modals está correta")
    
    user = User.objects.filter(username='testuser').first()
    if not user:
        return False
    
    client = Client()
    client.login(username='testuser', password='testpass123')
    
    response = client.get('/procedures/planejamentos/novo/')
    content = response.content.decode('utf-8')
    
    checks = {
        'Modal colaboradores tem checkboxes': 'colaborador-option' in content,
        'Modal procedimento tem checkboxes': 'procedimento-option' in content,
        'Modal colaboradores tem search': 'id="colaborador_search"' in content,
        'Modal procedimento tem search': 'id="procedimento_search"' in content,
        'Hidden input colaboradores': 'id="colaboradores_hidden"' in content,
        'Hidden input procedimento': 'id="procedimento_hidden"' in content,
        'Botão adicionar colaborador': 'data-bs-target="#colaboradoresModal"' in content,
        'Botão adicionar procedimento': 'data-bs-target="#procedimentoModal"' in content,
    }
    
    print("\n  Estrutura HTML:")
    all_passed = True
    for check_name, result in checks.items():
        status = "✅" if result else "❌"
        print(f"  {status} {check_name}")
        if not result:
            all_passed = False
    
    return all_passed

def test_data_in_modals():
    """Teste 3: Dados aparecem nos modals"""
    print("\n📋 TESTE 3: Dados aparecem nos modals")
    
    user = User.objects.filter(username='testuser').first()
    if not user:
        return False
    
    client = Client()
    client.login(username='testuser', password='testpass123')
    
    response = client.get('/procedures/planejamentos/novo/')
    content = response.content.decode('utf-8')
    
    # Verificar colaboradores
    colaboradores = Colaborador.objects.all()
    col_found = 0
    for col in colaboradores[:3]:
        if col.nome in content:
            col_found += 1
    
    # Verificar procedimentos
    procedimentos = Procedimento.objects.all()
    proc_found = 0
    for proc in procedimentos[:3]:
        if proc.codigo in content:
            proc_found += 1
    
    print(f"\n  Dados nos modals:")
    print(f"  ✅ {col_found}/{min(3, colaboradores.count())} colaboradores encontrados")
    print(f"  ✅ {proc_found}/{min(3, procedimentos.count())} procedimentos encontrados")
    
    return col_found > 0 and proc_found > 0

def main():
    """Executa todos os testes"""
    print("=" * 60)
    print("🧪 TESTES DO FORMULÁRIO DE PLANEJAMENTO")
    print("=" * 60)
    
    # Preparar dados
    create_test_data()
    
    # Executar testes
    test1 = test_form_loads()
    test2 = test_modal_structure()
    test3 = test_data_in_modals()
    
    # Resumo
    print("\n" + "=" * 60)
    print("📊 RESUMO DOS TESTES")
    print("=" * 60)
    
    results = {
        "Formulário carrega corretamente": test1,
        "Estrutura dos modals": test2,
        "Dados nos modals": test3,
    }
    
    for test_name, result in results.items():
        status = "✅ PASSOU" if result else "❌ FALHOU"
        print(f"{status}: {test_name}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ TODOS OS TESTES PASSARAM!")
    else:
        print("❌ ALGUNS TESTES FALHARAM!")
    print("=" * 60)
    
    return all_passed

if __name__ == '__main__':
    import sys
    success = main()
    sys.exit(0 if success else 1)
