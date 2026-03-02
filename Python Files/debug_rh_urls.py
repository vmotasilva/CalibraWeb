#!/usr/bin/env python
"""Script para debugar URLs de colaboradores no RH"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from rh.models import Colaborador
from django.db.models import Q

print("=" * 80)
print("DEBUG: RH Colaborador URLs")
print("=" * 80)

# Pegar alguns colaboradores
colaboradores = Colaborador.objects.all()[:10]

print(f"\nTotal de colaboradores: {Colaborador.objects.count()}")
print(f"\nPrimeiros 10 colaboradores:")

for c in colaboradores:
    print(f"\nID: {c.id} | Nome: {c.nome_completo} | Matrícula: {c.matricula}")
    if c.lider:
        print(f"  → Líder: ID={c.lider.id}, Nome={c.lider.nome_completo}")
    if c.supervisor:
        print(f"  → Supervisor: ID={c.supervisor.id}, Nome={c.supervisor.nome_completo}")
    if c.gerente:
        print(f"  → Gerente: ID={c.gerente.id}, Nome={c.gerente.nome_completo}")

# Procurar por um colaborador chamado RAMON (da imagem que o user mostrou)
print("\n" + "=" * 80)
print("Procurando por RAMON...")
print("=" * 80)

ramons = Colaborador.objects.filter(nome_completo__icontains='RAMON')
for ramon in ramons:
    print(f"\nID: {ramon.id} | Nome: {ramon.nome_completo} | Matrícula: {ramon.matricula}")

# Procurar por quem tem ID = 159
print("\n" + "=" * 80)
print("Procurando por ID = 159...")
print("=" * 80)

try:
    colab_159 = Colaborador.objects.get(id=159)
    print(f"ID: {colab_159.id} | Nome: {colab_159.nome_completo} | Matrícula: {colab_159.matricula}")
except Colaborador.DoesNotExist:
    print("Colaborador com ID 159 não existe!")

# Procurar por ID = 400
print("\n" + "=" * 80)
print("Procurando por ID = 400...")
print("=" * 80)

try:
    colab_400 = Colaborador.objects.get(id=400)
    print(f"ID: {colab_400.id} | Nome: {colab_400.nome_completo} | Matrícula: {colab_400.matricula}")
except Colaborador.DoesNotExist:
    print("Colaborador com ID 400 não existe!")

# Mostrar IDs duplicados se houver
print("\n" + "=" * 80)
print("Verificando IDs duplicados...")
print("=" * 80)

from django.db.models import Count

duplicados = Colaborador.objects.values('id').annotate(count=Count('id')).filter(count__gt=1)
if duplicados:
    print("AVISO: Encontrados IDs duplicados!")
    for dup in duplicados:
        print(f"  ID {dup['id']} aparece {dup['count']} vezes")
else:
    print("✓ Nenhum ID duplicado encontrado")

print("\n" + "=" * 80)
print("FIM DO DEBUG")
print("=" * 80)
