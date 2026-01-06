"""Script para testar integração completa - criar lista com nomes flexíveis."""
import os
import django
from datetime import datetime, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from procedures.models import ListaPresenca, RegistroTreinamento, Procedimento
from rh.models import Colaborador
from django.contrib.auth.models import User

print("=" * 70)
print("TESTE DE INTEGRAÇÃO - CRIAÇÃO COM NOMES FLEXÍVEIS")
print("=" * 70)

# Obter primeiro user, colaborador e procedimento
try:
    user = User.objects.first()
    colab = Colaborador.objects.first()
    procedimento = Procedimento.objects.first()
    
    print(f"\n✓ User: {user.username}")
    print(f"✓ Colaborador: {colab.nome_completo}")
    print(f"✓ Procedimento: {procedimento.nome if procedimento else 'Nenhum disponível'}")
    
    # Test 1: Criar lista com nome livre do instrutor
    print("\n" + "-" * 70)
    print("TEST 1: Criar lista com instrutor_nome (nome livre)")
    print("-" * 70)
    
    lista = ListaPresenca.objects.create(
        titulo="Treinamento Teste - Nomes Flexíveis",
        instrutor_nome="João Silva da Qualidade",  # Nome livre
        instrutor=None,  # Sem FK (flexível)
        data_sessao=datetime.now().date(),
        criado_por=user
    )
    
    print(f"✓ Lista criada: {lista.codigo}")
    print(f"  - Título: {lista.titulo}")
    print(f"  - Instrutor (nome livre): {lista.instrutor_nome}")
    print(f"  - Instrutor (FK): {lista.instrutor}")
    
    # Test 2: Criar registro com nome flexível do colaborador
    print("\n" + "-" * 70)
    print("TEST 2: Criar registro com colaborador_nome (nome livre)")
    print("-" * 70)
    
    registro = RegistroTreinamento.objects.create(
        lista_presenca=lista,
        colaborador_nome="Maria Santos da Silva",  # Nome livre
        colaborador=colab,  # FK do colaborador (match automático poderia ter feito)
        procedimento=procedimento,  # Adicionar procedimento para validação
        tipo="PROCEDIMENTO",
        data_treinamento=datetime.now().date()
    )
    
    print(f"✓ Registro criado: ID {registro.id}")
    print(f"  - Nome (livre): {registro.colaborador_nome}")
    print(f"  - Colaborador (FK): {registro.colaborador}")
    print(f"  - Tipo: {registro.tipo}")
    
    # Test 3: Consultar lista
    print("\n" + "-" * 70)
    print("TEST 3: Consultar lista criada")
    print("-" * 70)
    
    lista_consultada = ListaPresenca.objects.get(pk=lista.pk)
    print(f"✓ Lista consultada: {lista_consultada.codigo}")
    print(f"  - Instrutor (nome): {lista_consultada.instrutor_nome}")
    print(f"  - Registros: {lista_consultada.registros.count()}")
    
    # Test 4: Consultar registro
    print("\n" + "-" * 70)
    print("TEST 4: Consultar registro criado")
    print("-" * 70)
    
    registro_consultado = RegistroTreinamento.objects.get(pk=registro.pk)
    print(f"✓ Registro consultado: ID {registro_consultado.id}")
    print(f"  - Nome colaborador (livre): {registro_consultado.colaborador_nome}")
    print(f"  - Colaborador (FK): {registro_consultado.colaborador.nome_completo if registro_consultado.colaborador else 'Não vinculado'}")
    
    # Limpeza (remover dados de teste)
    print("\n" + "-" * 70)
    print("LIMPEZA: Removendo dados de teste")
    print("-" * 70)
    
    lista.delete()
    print("✓ Lista e registros associados removidos")
    
    print("\n" + "=" * 70)
    print("✅ TODOS OS TESTES PASSARAM COM SUCESSO!")
    print("=" * 70)
    
except Exception as e:
    print(f"\n❌ ERRO: {str(e)}")
    import traceback
    traceback.print_exc()
