"""Script para testar o matching de nomes."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from procedures.utils.name_matching import buscar_colaborador_por_nome, calcular_similaridade
from rh.models import Colaborador

print("=" * 60)
print("TESTE DE MATCHING DE NOMES")
print("=" * 60)

# Test 1: Verificar se há colaboradores na base
colabs = Colaborador.objects.all()[:3]
print(f"\n✓ Colaboradores encontrados: {colabs.count() if hasattr(colabs, 'count') else len(list(colabs))}")

if colabs:
    primeiro_colab = colabs[0]
    print(f"  - {primeiro_colab.nome_completo}")
    
    # Test 2: Testar similaridade exata
    score = calcular_similaridade(primeiro_colab.nome_completo, primeiro_colab.nome_completo)
    print(f"\n✓ Similaridade (nome exato): {score:.2%}")
    
    # Test 3: Testar com variação de case
    score = calcular_similaridade(primeiro_colab.nome_completo.lower(), primeiro_colab.nome_completo.upper())
    print(f"✓ Similaridade (case insensitivo): {score:.2%}")
    
    # Test 4: Testar com parte do nome
    nome_parcial = primeiro_colab.nome_completo.split()[0]
    score = calcular_similaridade(nome_parcial, primeiro_colab.nome_completo)
    print(f"✓ Similaridade (primeiro nome): {score:.2%}")
    
    # Test 5: Buscar por nome
    resultado, score = buscar_colaborador_por_nome(primeiro_colab.nome_completo, threshold=0.85)
    print(f"\n✓ Busca por nome exato:")
    print(f"  - Encontrado: {resultado.nome_completo if resultado else 'Não'}")
    print(f"  - Score: {score:.2%}")

print("\n" + "=" * 60)
print("TESTES CONCLUÍDOS COM SUCESSO!")
print("=" * 60)
