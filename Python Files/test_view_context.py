#!/usr/bin/env python
"""Script para testar a view do dashboard"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from rh.models import Colaborador
from procedures.models import RegistroTreinamento
from core.models import TURNOS_CHOICES
from organization.models import Setor
from datetime import date, timedelta

print(f"Total de registros de treinamento: {RegistroTreinamento.objects.count()}")
print(f"Registros com colaborador: {RegistroTreinamento.objects.filter(colaborador__isnull=False).count()}")

# SIMULANDO O QUE A VIEW FAZ
print("\n=== SIMULANDO LÓGICA DA VIEW ===\n")

# Gráfico por Líder
print("=== DADOS PARA GRÁFICO POR LÍDER ===")
treinamentos_por_lider = []
líderes = Colaborador.objects.filter(
    liderados__isnull=False, 
    liderados__is_active=True
).distinct().order_by('nome_completo')

print(f"Líderes com liderados ativos: {líderes.count()}")
print(f"Query: Colaborador.objects.filter(liderados__isnull=False, liderados__is_active=True).distinct()")

for lider in líderes:
    liderados_ids = lider.liderados.filter(is_active=True).values_list('id', flat=True)
    print(f"\nLíder: {lider.nome_completo}")
    print(f"  Liderados ativos: {len(liderados_ids)}")
    
    vigentes = RegistroTreinamento.objects.filter(
        colaborador_id__in=liderados_ids,
        data_treinamento__isnull=False
    ).count()
    pendentes = RegistroTreinamento.objects.filter(
        colaborador_id__in=liderados_ids,
        data_treinamento__isnull=True
    ).count()
    
    print(f"  Vigentes: {vigentes}, Pendentes: {pendentes}")
    
    total = vigentes + pendentes
    if total > 0:
        treinamentos_por_lider.append({
            'nome': lider.nome_completo[:25],
            'vigentes': vigentes,
            'pendentes': pendentes
        })

print(f"\nTotal com dados (antes de ordenar): {len(treinamentos_por_lider)}")
treinamentos_por_lider.sort(key=lambda x: x['vigentes'] + x['pendentes'], reverse=True)
treinamentos_por_lider = treinamentos_por_lider[:10]
print(f"Total com dados (após top 10): {len(treinamentos_por_lider)}")

for item in treinamentos_por_lider:
    print(f"  - {item['nome']}: {item['vigentes']} vigentes, {item['pendentes']} pendentes")
