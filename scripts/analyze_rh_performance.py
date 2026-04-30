#!/usr/bin/env python
"""
Script para otimizar performance do dashboard RH.
Análise e sugestões de otimização.
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection
from django.apps import apps
from rh.models import Colaborador
from procedures.models import RegistroTreinamento
from organization.models import Setor

print("=" * 70)
print("ANÁLISE DE PERFORMANCE - DASHBOARD RH")
print("=" * 70)

# 1. Verificar índices existentes
print("\n📊 ÍNDICES NO BANCO DE DADOS:")
print("-" * 70)

inspector = connection.introspection
db_tables = {
    'rh_colaborador': ['is_active', 'afastado', 'em_ferias', 'lider_id', 'supervisor_id', 'gerente_id', 'setor_id'],
    'procedures_registrotreinamento': ['colaborador_nome', 'procedimento_id'],
}

for table, important_fields in db_tables.items():
    print(f"\n📋 Tabela: {table}")
    try:
        indexes = connection.introspection.get_indexes(connection.cursor(), table)
        if indexes:
            for field, index_info in indexes.items():
                print(f"  ✓ {field}: {index_info}")
        else:
            print(f"  ⚠️  Sem índices encontrados")
    except Exception as e:
        print(f"  ❌ Erro ao verificar: {e}")

# 2. Estatísticas das tabelas
print("\n\n📈 ESTATÍSTICAS DAS TABELAS:")
print("-" * 70)

counts = {
    'Colaboradores': Colaborador.objects.count(),
    'Colaboradores Ativos': Colaborador.objects.filter(is_active=True).count(),
    'Colaboradores Afastados': Colaborador.objects.filter(afastado=True).count(),
    'Registros de Treinamento': RegistroTreinamento.objects.count(),
    'Setores': Setor.objects.count(),
}

for label, count in counts.items():
    print(f"  {label}: {count}")

# 3. Sugestões de otimização
print("\n\n💡 SUGESTÕES DE OTIMIZAÇÃO:")
print("-" * 70)

suggestions = [
    ("1. Adicionar índices", [
        "ALTER TABLE rh_colaborador ADD INDEX idx_is_active (is_active);",
        "ALTER TABLE rh_colaborador ADD INDEX idx_afastado (afastado);",
        "ALTER TABLE rh_colaborador ADD INDEX idx_em_ferias (em_ferias);",
        "ALTER TABLE rh_colaborador ADD INDEX idx_lider (lider_id);",
        "ALTER TABLE rh_colaborador ADD INDEX idx_supervisor (supervisor_id);",
        "ALTER TABLE rh_colaborador ADD INDEX idx_gerente (gerente_id);",
        "ALTER TABLE rh_colaborador ADD INDEX idx_setor (setor_id);",
        "ALTER TABLE procedures_registrotreinamento ADD INDEX idx_colaborador (colaborador_nome);",
    ]),
    ("2. Implementar caching", [
        "Cache dos filtros (setores, líderes, etc.) por 5 minutos",
        "Cache do dashboard renderizado por usuário/permissão por 2 minutos",
        "Use Django cache framework ou Redis",
    ]),
    ("3. Usar select_related/prefetch_related", [
        "✓ Já implementado no código",
    ]),
    ("4. Paginação", [
        "✓ Dashboard já usa paginação",
    ]),
]

for title, items in suggestions:
    print(f"\n{title}:")
    for item in items:
        print(f"  • {item}")

print("\n\n" + "=" * 70)
print("FIM DA ANÁLISE")
print("=" * 70)
