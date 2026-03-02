#!/usr/bin/env python
"""
Test script to verify all three status states are working correctly:
- OK (Em dias): quando data_treinamento >= ultima_revisao
- PENDENTE: quando tem lista_presenca mas data < ultima_revisao
- NAO_INICIADO: quando não tem data_treinamento
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from procedures.models import RegistroTreinamento

# Find examples of each status state
todos_registros = RegistroTreinamento.objects.select_related('procedimento', 'lista_presenca', 'colaborador').all()

print("=" * 80)
print("ANÁLISE DE STATUS EM TRÊS ESTADOS")
print("=" * 80)

# Agrupando por status
ok_registros = []
pendente_registros = []
nao_iniciado_registros = []

for reg in todos_registros:
    status = reg.status_treinamento
    if status == 'OK':
        ok_registros.append(reg)
    elif status == 'PENDENTE':
        pendente_registros.append(reg)
    elif status == 'NAO_INICIADO':
        nao_iniciado_registros.append(reg)

print(f"\n✅ Status OK (Em dias): {len(ok_registros)} registros")
if ok_registros:
    r = ok_registros[0]
    print(f"   Exemplo: {r.colaborador.nome_completo} - {r.procedimento.codigo}")
    print(f"   Data: {r.data_treinamento} >= Revisão: {r.procedimento.ultima_revisao}")
    print(f"   Comparação: {r.data_treinamento >= r.procedimento.ultima_revisao if r.data_treinamento and r.procedimento.ultima_revisao else 'N/A'}")

print(f"\n🔴 Status PENDENTE: {len(pendente_registros)} registros")
if pendente_registros:
    r = pendente_registros[0]
    print(f"   Exemplo: {r.colaborador.nome_completo} - {r.procedimento.codigo}")
    print(f"   Data: {r.data_treinamento}")
    print(f"   Revisão: {r.procedimento.ultima_revisao}")
    print(f"   Lista Presença: {r.lista_presenca}")

print(f"\n⚪ Status NÃO INICIADO: {len(nao_iniciado_registros)} registros")
if nao_iniciado_registros:
    r = nao_iniciado_registros[0]
    print(f"   Exemplo: {r.colaborador.nome_completo} - {r.procedimento.codigo}")
    print(f"   Data: {r.data_treinamento}")
    print(f"   Lista Presença: {r.lista_presenca}")

print("\n" + "=" * 80)
print(f"TOTAL: {len(ok_registros) + len(pendente_registros) + len(nao_iniciado_registros)} registros analisados")
print("=" * 80)
