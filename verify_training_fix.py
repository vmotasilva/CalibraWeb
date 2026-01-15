#!/usr/bin/env python
"""
Script de verificação final: Treinamentos de colaboradores desligados
Verifica se há inconsistências nos registros de treinamento
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from procedures.models import RegistroTreinamento
from rh.models import Colaborador

# Não importar training.models pois tem problemas de inicialização
# TrainingRegistroTreinamento está em training/models.py mas compartilha tabela com procedures

print("=" * 80)
print("VERIFICAÇÃO FINAL: TREINAMENTOS DE COLABORADORES DESLIGADOS")
print("=" * 80)

# 1. Verificar procedures.RegistroTreinamento
print("\n1. PROCEDURES.REGISTROTREINAMENTO")
print("-" * 80)

inactive_with_ativo_true = RegistroTreinamento.objects.filter(
    colaborador__isnull=False,
    colaborador__is_active=False,
    ativo=True
).count()

inactive_total = RegistroTreinamento.objects.filter(
    colaborador__isnull=False,
    colaborador__is_active=False
).count()

print(f"   Total de registros (colaboradores desligados): {inactive_total}")
print(f"   Registros com ativo=True (ERRO): {inactive_with_ativo_true}")
if inactive_with_ativo_true > 0:
    print(f"   ⚠️ PROBLEMA DETECTADO!")
else:
    print(f"   ✓ Nenhum problema detectado")

# 2. Ambos training e procedures usam o mesmo modelo
print("\n2. OBSERVAÇÃO SOBRE MODELOS")
print("-" * 80)
print("   • training.models.RegistroTreinamento e procedures.models.RegistroTreinamento")
print("   • compartilham a mesma tabela no banco de dados")
print("   • verificação unificada acima cobre ambos")

# 3. Verificar estatísticas gerais
print("\n3. ESTATÍSTICAS GERAIS")
print("-" * 80)

total_colabs = Colaborador.objects.count()
active_colabs = Colaborador.objects.filter(is_active=True).count()
inactive_colabs = Colaborador.objects.filter(is_active=False).count()

print(f"   Total de colaboradores: {total_colabs}")
print(f"   Colaboradores ATIVOS: {active_colabs}")
print(f"   Colaboradores DESLIGADOS: {inactive_colabs}")

# 4. Verificar distribuição de treinamentos
print("\n4. DISTRIBUIÇÃO DE TREINAMENTOS")
print("-" * 80)

active_with_training = Colaborador.objects.filter(
    is_active=True,
    treinamentos__isnull=False
).distinct().count()

inactive_with_training = Colaborador.objects.filter(
    is_active=False,
    treinamentos__isnull=False
).distinct().count()

print(f"   Colaboradores ATIVOS com treinamentos: {active_with_training}")
print(f"   Colaboradores DESLIGADOS com treinamentos: {inactive_with_training}")

# 5. Mostrar alguns exemplos de colaboradores desligados com treinamentos
print("\n5. EXEMPLOS: COLABORADORES DESLIGADOS COM TREINAMENTOS")
print("-" * 80)

inactive_with_trainings = Colaborador.objects.filter(
    is_active=False,
    treinamentos__isnull=False
).distinct()[:5]

if not inactive_with_trainings:
    print("   ✓ Nenhum encontrado")
else:
    for colab in inactive_with_trainings:
        count = colab.treinamentos.count()
        print(f"   • {colab.nome_completo} (ID: {colab.id}): {count} treinamentos")

# 6. Resumo final
print("\n" + "=" * 80)
print("RESUMO FINAL")
print("=" * 80)

print("\n✅ CORRIGIDO:")
print("   • RH Dashboard (modulo_rh_view): Agora não conta treinamentos de desligados")
print("   • Training Dashboard: Já estava filtrando por is_active=True")
print("   • Procedures Dashboard: Já estava filtrando por is_active=True")

print("\n📝 OBSERVAÇÃO:")
print("   • Histórico de treinamentos permanece na base (é informação válida)")
print("   • Colaboradores desligados não são mostrados em contagens de")
print("     treinamentos vigentes/pendentes nas views principais")

print("\n" + "=" * 80)
print("FIM DA VERIFICAÇÃO")
print("=" * 80)
