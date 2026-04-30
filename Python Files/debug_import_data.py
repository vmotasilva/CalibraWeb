#!/usr/bin/env python
"""Debug script para análise de importação recente"""

import os
import django
import pandas as pd

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from procedures.models import RegistroTreinamento
from django.utils import timezone

# Verificar últimos registros criados (últimas 24 horas)
from django.db.models import Q
ultimos = RegistroTreinamento.objects.all().order_by('-id')[:50]

print(f"\n{'='*80}")
print(f"ANÁLISE DOS ÚLTIMOS 50 REGISTROS")
print(f"{'='*80}\n")

data_null_count = 0
lista_null_count = 0

for r in ultimos:
    data_status = "✅" if r.data_treinamento else "❌ NULL"
    lista_status = "✅" if r.lista_presenca else "❌ NULL"
    
    if r.data_treinamento is None:
        data_null_count += 1
    if r.lista_presenca is None:
        lista_null_count += 1
    
    print(f"ID {r.id:4d} | {r.colaborador.nome_completo:30s} | "
          f"Data: {data_status:8s} ({r.data_treinamento}) | "
          f"Lista: {lista_status:8s} ({r.lista_presenca_id})")

print(f"\n{'='*80}")
print(f"RESUMO:")
print(f"{'='*80}")
print(f"Últimos 50 registros: {len(list(ultimos))}")
print(f"Com data_treinamento NULL: {data_null_count}")
print(f"Com lista_presenca NULL: {lista_null_count}")
print(f"\nCOMCLUSÃO: {'❌ PROBLEMA DETECTADO' if data_null_count > 5 else '✅ Funcionando normalmente'}")
