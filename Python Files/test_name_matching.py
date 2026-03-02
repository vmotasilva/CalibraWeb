"""
Script de teste para validar o name matching functionality.
Execute com: python manage.py shell < test_name_matching.py
"""

from procedures.utils.name_matching import (
    calcular_similaridade,
    buscar_colaborador_por_nome,
    tentar_linkar_colaborador
)
from rh.models import Colaborador

print("=" * 60)
print("TESTE DE NAME MATCHING")
print("=" * 60)

# Teste 1: Similaridade
print("\n[TESTE 1] Calcular Similaridade")
print("-" * 60)

nome1 = "João Silva"
nome2 = "Joao Silva"
score = calcular_similaridade(nome1, nome2)
print(f"'{nome1}' vs '{nome2}': {score:.2%}")

nome1 = "Maria Oliveira"
nome2 = "Maria Oliveira da Silva"
score = calcular_similaridade(nome1, nome2)
print(f"'{nome1}' vs '{nome2}': {score:.2%}")

nome1 = "Pedro Santos"
nome2 = "Carlos Silva"
score = calcular_similaridade(nome1, nome2)
print(f"'{nome1}' vs '{nome2}': {score:.2%}")

# Teste 2: Buscar na base
print("\n[TESTE 2] Buscar Colaborador por Nome")
print("-" * 60)

colaboradores = Colaborador.objects.all()[:5]
if not colaboradores.exists():
    print("❌ Sem colaboradores na base para teste")
else:
    for colab in colaboradores:
        print(f"\nColaborador na BD: {colab.nome_completo}")
        
        # Teste com nome exato
        resultado, score = buscar_colaborador_por_nome(colab.nome_completo)
        if resultado:
            print(f"  ✅ Encontrado (Score: {score:.2%})")
        else:
            print(f"  ❌ Não encontrado (Score: {score:.2%})")
        
        # Teste com nome parcial
        nome_parcial = colab.nome_completo.split()[0]
        resultado, score = buscar_colaborador_por_nome(nome_parcial)
        print(f"  Parcial '{nome_parcial}': {resultado.nome_completo if resultado else 'N/A'} ({score:.2%})")

# Teste 3: Tentar linkar
print("\n[TESTE 3] Tentar Linkar Colaborador")
print("-" * 60)

if colaboradores.exists():
    colab_real = colaboradores.first()
    
    # Teste 1: Sem FK, com nome aproximado
    nome_aproximado = colab_real.nome_completo.replace(' ', '')  # Remove espaços
    resultado = tentar_linkar_colaborador(nome_aproximado)
    print(f"Nome aproximado '{nome_aproximado}':")
    if resultado:
        print(f"  ✅ Linkado para: {resultado.nome_completo}")
    else:
        print(f"  ❌ Não conseguiu linkar")
    
    # Teste 2: Com FK direto
    resultado = tentar_linkar_colaborador("qualquer coisa", colaborador_fk=colab_real)
    print(f"\nCom FK direto:")
    print(f"  ✅ Retorna FK: {resultado.nome_completo if resultado else 'None'}")

print("\n" + "=" * 60)
print("TESTES CONCLUÍDOS")
print("=" * 60)
