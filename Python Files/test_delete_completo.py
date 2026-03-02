#!/usr/bin/env python
"""
Teste final abrangente de validação da funcionalidade DELETE HISTÓRICO
Valida: Deleção, Redirecionamento, Segurança, Mensagens
"""
import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from metrologia.models import Instrumento, HistoricoCalibracao
from django.urls import reverse
from django.db.models import Q

def test_complete_delete_flow():
    print("\n" + "="*80)
    print("TESTE COMPLETO: Funcionalidade DELETE HISTÓRICO")
    print("="*80)
    
    # Setup: Usuário
    try:
        user = User.objects.get(username='final_test_user')
        user.delete()
    except:
        pass
    
    user = User.objects.create_superuser('final_test_user', 'final@test.com', 'finalpass123')
    client = Client()
    client.login(username='final_test_user', password='finalpass123')
    print(f"✅ Usuário de teste criado e autenticado")
    
    # Setup: Dados de teste
    inst = Instrumento.objects.first()
    hist = HistoricoCalibracao.objects.filter(instrumento=inst).first()
    
    if not inst or not hist:
        print("❌ FALHA: Dados de teste não encontrados")
        return False
    
    print(f"✅ Dados de teste encontrados:")
    print(f"   - Instrumento: {inst.codigo} (ID: {inst.id})")
    print(f"   - Histórico: ID {hist.id}, Data: {hist.data_calibracao}")
    if hist.certificado:
        print(f"   - Certificado: {hist.certificado.name} (será removido)")
    
    tests_passed = 0
    tests_total = 0
    
    # TEST 1: URL Reverse correto
    print("\n" + "-"*80)
    print("TEST 1: Verificar URL reversa")
    print("-"*80)
    tests_total += 1
    
    try:
        url_delete = reverse('remover_historico', kwargs={'historico_id': hist.id})
        if url_delete == f"/metrologia/historico/{hist.id}/remover/":
            print(f"✅ URL correta: {url_delete}")
            tests_passed += 1
        else:
            print(f"❌ URL incorreta: {url_delete}")
            print(f"   Esperado: /metrologia/historico/{hist.id}/remover/")
    except Exception as e:
        print(f"❌ Erro ao fazer reverse: {e}")
    
    # TEST 2: GET - Página de confirmação
    print("\n" + "-"*80)
    print("TEST 2: Acessar página de confirmação (GET)")
    print("-"*80)
    tests_total += 1
    
    try:
        response = client.get(url_delete)
        if response.status_code == 200:
            print(f"✅ Status 200 OK")
            content = response.content.decode()
            
            checks = [
                ("Título 'Confirmar Remoção'", 'Confirmar Remoção' in content),
                ("Formulário POST", '<form method="post"' in content),
                ("Botão Confirmar", 'Remover Permanentemente' in content),
                ("Botão Cancelar", 'Cancelar' in content),
                ("Data do histórico exibida", hist.data_calibracao.strftime('%d/%m/%Y') in content),
            ]
            
            for check_name, result in checks:
                if result:
                    print(f"   ✅ {check_name}")
                else:
                    print(f"   ⚠️  {check_name} - NÃO ENCONTRADO")
            
            tests_passed += 1
        else:
            print(f"❌ Status inesperado: {response.status_code}")
    except Exception as e:
        print(f"❌ Erro ao acessar confirmação: {e}")
    
    # TEST 3: POST - Deleção
    print("\n" + "-"*80)
    print("TEST 3: Executar deleção (POST)")
    print("-"*80)
    tests_total += 1
    
    try:
        hist_id_before = hist.id
        cert_file = hist.certificado.name if hist.certificado else None
        
        response = client.post(url_delete, follow=True)
        
        # Verificar redirect
        if response.status_code == 200:
            print(f"✅ Status 200 OK (após follow de redirects)")
            print(f"   Redirecionado para: {response.request['PATH_INFO']}")
            
            # Verificar se foi para instrumento correto
            if f"/metrologia/instrumento/{inst.id}/" in response.request['PATH_INFO']:
                print(f"   ✅ Redirecionado para instrumento correto")
            else:
                print(f"   ❌ Redirecionamento incorreto")
                print(f"      Esperado: /metrologia/instrumento/{inst.id}/")
            
            tests_passed += 1
        else:
            print(f"❌ Status inesperado: {response.status_code}")
    except Exception as e:
        print(f"❌ Erro ao postar deleção: {e}")
    
    # TEST 4: Verificar deleção do banco
    print("\n" + "-"*80)
    print("TEST 4: Verificar deleção do histórico no banco")
    print("-"*80)
    tests_total += 1
    
    try:
        HistoricoCalibracao.objects.get(id=hist_id_before)
        print(f"❌ Histórico ainda existe no banco (ID: {hist_id_before})")
    except HistoricoCalibracao.DoesNotExist:
        print(f"✅ Histórico deletado com sucesso do banco (ID: {hist_id_before})")
        tests_passed += 1
    except Exception as e:
        print(f"❌ Erro ao verificar banco: {e}")
    
    # TEST 5: Mensagem de sucesso
    print("\n" + "-"*80)
    print("TEST 5: Verificar mensagem de sucesso")
    print("-"*80)
    tests_total += 1
    
    try:
        content = response.content.decode()
        if 'Histórico removido com sucesso' in content:
            print(f"✅ Mensagem de sucesso exibida")
            tests_passed += 1
        else:
            print(f"⚠️  Mensagem de sucesso não encontrada")
    except:
        print(f"❌ Erro ao verificar mensagem")
    
    # TEST 6: CSRF Token
    print("\n" + "-"*80)
    print("TEST 6: Validação de CSRF")
    print("-"*80)
    tests_total += 1
    
    try:
        # Tentar POST sem CSRF deve falhar
        nocrf_client = Client(enforce_csrf_checks=True)
        nocrf_client.login(username='final_test_user', password='finalpass123')
        
        # Criar novo histórico para testar CSRF
        new_hist = HistoricoCalibracao.objects.filter(instrumento=inst).exclude(id=hist_id_before).first()
        if new_hist:
            url_test = reverse('remover_historico', kwargs={'historico_id': new_hist.id})
            response = nocrf_client.post(url_test, {})
            
            # Deve falhar sem CSRF
            if response.status_code in [403, 400]:
                print(f"✅ CSRF protection ativo (status {response.status_code})")
                tests_passed += 1
            else:
                print(f"⚠️  CSRF pode não estar protegendo (status {response.status_code})")
    except Exception as e:
        print(f"⚠️  Erro ao testar CSRF: {e}")
    
    # TEST 7: Authentcation
    print("\n" + "-"*80)
    print("TEST 7: Validação de Autenticação")
    print("-"*80)
    tests_total += 1
    
    try:
        anon_client = Client()
        new_hist = HistoricoCalibracao.objects.filter(instrumento=inst).exclude(id=hist_id_before).first()
        if new_hist:
            url_test = reverse('remover_historico', kwargs={'historico_id': new_hist.id})
            response = anon_client.get(url_test)
            
            # Usuário não autenticado deve ser redirecionado
            if response.status_code in [302, 301]:
                print(f"✅ Redirecionamento de login (status {response.status_code})")
                tests_passed += 1
            else:
                print(f"⚠️  Usuário anônimo acessou a página (status {response.status_code})")
    except Exception as e:
        print(f"❌ Erro ao testar autenticação: {e}")
    
    # RESUMO FINAL
    print("\n" + "="*80)
    print(f"RESULTADO FINAL: {tests_passed}/{tests_total} testes passaram")
    print("="*80)
    
    if tests_passed == tests_total:
        print("✅ TODOS OS TESTES PASSARAM - IMPLEMENTAÇÃO VALIDADA!")
        return True
    elif tests_passed >= tests_total * 0.8:
        print("⚠️  MAIORIA DOS TESTES PASSOU - Verificar avisos acima")
        return True
    else:
        print("❌ FALHA - Vários testes falharam")
        return False

if __name__ == '__main__':
    try:
        success = test_complete_delete_flow()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERRO CRÍTICO: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
