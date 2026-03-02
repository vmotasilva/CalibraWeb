#!/usr/bin/env python
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from rh.models import Colaborador
from organization.models import Setor
from django.db import connection
from django.conf import settings
import time

# Ativar DEBUG para capture queries
settings.DEBUG = True

# Simular a view
print("=" * 60)
print("SIMULANDO CARREGAMENTO DO DASHBOARD RH")
print("=" * 60)

start = time.time()
colaboradores = Colaborador.objects.filter(
    id__in=Colaborador.objects.all().values_list('id', flat=True)
).select_related(
    'setor', 'centro_custo', 'lider', 'supervisor', 'gerente'
).prefetch_related(
    'treinamentos__procedimento'
).order_by("nome_completo")

query_count_after_prepare = len(connection.queries)
print(f"\n1. Queries após preparar queryset (antes de evaluar): {query_count_after_prepare}")

colab_list = list(colaboradores)
query_count_after_list = len(connection.queries)
print(f"2. Queries após list() (loading data): {query_count_after_list}")
print(f"   Carregados {len(colab_list)} colaboradores")

# Iterar para extrair filtros
start_iter = time.time()
setores_ids = set()
lideres_ids = set()
supervisores_ids = set()
gerentes_ids = set()

for f in colab_list:
    if f.setor_id:
        setores_ids.add(f.setor_id)
    if f.lider_id:
        lideres_ids.add(f.lider_id)
    if f.supervisor_id:
        supervisores_ids.add(f.supervisor_id)
    if f.gerente_id:
        gerentes_ids.add(f.gerente_id)

iter_time = time.time() - start_iter
print(f"3. Iteração: {iter_time:.3f}s - Extraído {len(setores_ids)} setores, {len(lideres_ids)} líderes, {len(supervisores_ids)} supervisores, {len(gerentes_ids)} gerentes")

# Carregar filtros
setores = Setor.objects.filter(id__in=setores_ids)
query_count_final = len(connection.queries)
print(f"4. Total de Queries: {query_count_final}")

print("\n" + "=" * 60)
print("DETALHES DAS QUERIES:")
print("=" * 60)
total_time = 0
for i, q in enumerate(connection.queries, 1):
    total_time += float(q['time'])
    sql = q['sql'].replace('\n', ' ')
    if len(sql) > 120:
        sql = sql[:120] + "..."
    print(f"{i}. [{q['time']}s] {sql}")

print(f"\nTempo Total de Queries: {total_time:.3f}s")
print(f"Tempo Total do Script: {time.time() - start:.3f}s")
