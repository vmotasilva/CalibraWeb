#!/usr/bin/env python
"""Script para corrigir treinamentos de colaboradores desligados"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from procedures.models import RegistroTreinamento
from rh.models import Colaborador

print("=" * 80)
print("VERIFICANDO TREINAMENTOS DE COLABORADORES DESLIGADOS")
print("=" * 80)

# Encontrar treinamentos de colaboradores desligados que estão marcados como "ativo"
treinamentos_problema = RegistroTreinamento.objects.filter(
    colaborador__isnull=False,
    colaborador__is_active=False,  # Colaborador desligado
    ativo=True  # Treinamento marcado como ativo
)

print(f"\n✓ Encontrados {treinamentos_problema.count()} registros de treinamento com problema:")
print("  (Colaborador desligado + Treinamento ativo)\n")

if treinamentos_problema.count() == 0:
    print("✓ Nenhum problema encontrado!")
    print("=" * 80)
    exit(0)

# Listar os problemas
for rt in treinamentos_problema[:10]:  # Mostrar até 10
    print(f"\n  ID: {rt.id}")
    print(f"    Colaborador: {rt.colaborador.nome_completo} (ID: {rt.colaborador.id})")
    print(f"    Status: DESLIGADO (is_active=False)")
    print(f"    Procedimento/Treinamento: {rt.procedimento.numero if rt.procedimento else rt.titulo_treinamento}")
    print(f"    Data Treinamento: {rt.data_treinamento}")
    print(f"    Ativo: {rt.ativo} → DEVE SER False")

if treinamentos_problema.count() > 10:
    print(f"\n  ... e mais {treinamentos_problema.count() - 10} registros")

# Perguntar se deseja corrigir
print("\n" + "=" * 80)
print("CORRIGINDO...")
print("=" * 80)

# Atualizar todos os registros problemáticos
atualizado = 0
for rt in treinamentos_problema:
    rt.ativo = False
    rt.save()
    atualizado += 1

print(f"\n✓ {atualizado} registros foram marcados como INATIVOS")

# Verificar resultado
verificacao = RegistroTreinamento.objects.filter(
    colaborador__isnull=False,
    colaborador__is_active=False,
    ativo=True
)

print(f"\n✓ Verificação pós-correção:")
print(f"  Treinamentos ainda problemáticos: {verificacao.count()}")

if verificacao.count() == 0:
    print("\n✅ PROBLEMA RESOLVIDO! Todos os treinamentos de colaboradores desligados foram marcados como inativos.")
else:
    print(f"\n⚠️ AVISO: Ainda há {verificacao.count()} registros problemáticos!")

print("\n" + "=" * 80)
print("FIM")
print("=" * 80)
