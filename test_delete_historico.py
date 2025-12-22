#!/usr/bin/env python
"""
Teste de integração para a funcionalidade de deleção de histórico
"""
import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from metrologia.models import Instrumento, HistoricoCalibracao
from django.urls import reverse

def test_delete_historico():
    print("\n" + "="*70)
    print("TESTE DE INTEGRAÇÃO: Deleção de Histórico de Calibração")
    print("="*70)
    
    # Criar usuário de teste
    try:
        user = User.objects.get(username='testuser')
        user.delete()
    except:
        pass
    
    user = User.objects.create_superuser('testuser', 'test@test.com', 'testpass123')
    print(f"✓ Usuário de teste criado: {user.username}")
    
    # Obter um instrumento e histórico existentes
    inst = Instrumento.objects.first()
    hist = HistoricoCalibracao.objects.filter(instrumento=inst).first()
    
    if not inst or not hist:
        print("✗ ERRO: Não há dados suficientes no banco para teste")
        return False
    
    print(f"\n✓ Instrumento encontrado: {inst.codigo} (ID: {inst.id})")
    print(f"✓ Histórico encontrado: ID {hist.id}, Data: {hist.data_calibracao}")
    
    # Simular cliente HTTP
    client = Client()
    client.login(username='testuser', password='testpass123')
    print(f"✓ Usuário autenticado no cliente")
    
    # TESTE 1: Acessar página de confirmação (GET)
    print("\n" + "-"*70)
    print("[TESTE 1] Acessar página de confirmação (GET)")
    print("-"*70)
    
    url_delete = reverse('remover_historico', kwargs={'historico_id': hist.id})
    print(f"URL: {url_delete}")
    
    response = client.get(url_delete)
    print(f"Status HTTP: {response.status_code}")
    
    if response.status_code == 200:
        print("✓ Página de confirmação renderizada com sucesso")
        content = response.content.decode()
        if 'Confirmar Remoção' in content:
            print("✓ Template contém título 'Confirmar Remoção'")
        else:
            print("✗ AVISO: Título 'Confirmar Remoção' não encontrado")
    else:
        print(f"✗ ERRO: Status inesperado {response.status_code}")
        return False
    
    # TESTE 2: Submeter formulário de deleção (POST)
    print("\n" + "-"*70)
    print("[TESTE 2] Submeter formulário de deleção (POST)")
    print("-"*70)
    
    hist_id_before = hist.id
    instrumento_id = inst.id
    
    print(f"Deletando histórico ID: {hist_id_before}")
    response = client.post(url_delete, follow=True)
    
    print(f"Status HTTP: {response.status_code}")
    print(f"Redirecionado para: {response.request['PATH_INFO']}")
    
    # Verificar se foi deletado do banco
    try:
        HistoricoCalibracao.objects.get(id=hist_id_before)
        print("✗ ERRO: Histórico não foi deletado!")
        return False
    except HistoricoCalibracao.DoesNotExist:
        print("✓ Histórico foi deletado com sucesso!")
    
    # Verificar se redirecionou para o instrumento
    expected_redirect = f"/metrologia/instrumento/{instrumento_id}/"
    if expected_redirect in response.request['PATH_INFO']:
        print(f"✓ Redirecionado para o instrumento corretamente: {expected_redirect}")
    else:
        print(f"✗ AVISO: Redirecionamento inesperado para: {response.request['PATH_INFO']}")
        print(f"  Esperado: {expected_redirect}")
    
    # Verificar mensagem de sucesso
    content = response.content.decode()
    if 'Histórico removido com sucesso' in content:
        print("✓ Mensagem de sucesso exibida ao usuário")
    else:
        print("✗ AVISO: Mensagem de sucesso não encontrada")
    
    print("\n" + "="*70)
    print("TESTE CONCLUÍDO COM SUCESSO!")
    print("="*70)
    return True

if __name__ == '__main__':
    try:
        success = test_delete_historico()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ ERRO DURANTE O TESTE: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
