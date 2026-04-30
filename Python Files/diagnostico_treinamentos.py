#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Diagnóstico: Discrepância em contagem de treinamentos
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, 'c:\\CalibraWeb')

django.setup()

from rh.models import Colaborador
from procedures.models import RegistroTreinamento

print("\n" + "="*80)
print("DIAGNÓSTICO: Discrepância em Contagem de Treinamentos")
print("="*80)

# Pegar alguns colaboradores com treinamentos
colaboradores = Colaborador.objects.filter(
    treinamentos__isnull=False
).distinct()[:3]

for colab in colaboradores:
    print(f"\n📋 {colab.nome_completo} (ID: {colab.id})")
    print("-" * 80)
    
    treinamentos = colab.treinamentos.all()
    print(f"Total de registros: {treinamentos.count()}\n")
    
    vigentes_ok = 0
    vigentes_e_ok = 0
    pendentes = 0
    nao_iniciados = 0
    
    status_count = {}
    
    for rt in treinamentos:
        status = rt.status_treinamento
        
        # Método 1: Como no dashboard (vigentes em ("VIGENTE", "OK"))
        if status in ("VIGENTE", "OK"):
            vigentes_e_ok += 1
        
        # Método 2: Como no detalhe (vigentes em status == "OK")
        if status == "OK":
            vigentes_ok += 1
        
        # Contar todos os status
        if status not in status_count:
            status_count[status] = 0
        status_count[status] += 1
        
        # Categorizar
        if status == "PENDENTE":
            pendentes += 1
        elif status == "NAO_INICIADO":
            nao_iniciados += 1
    
    print("Distribuição de Status:")
    for status, count in sorted(status_count.items()):
        print(f"  {status}: {count}")
    
    print(f"\nContagem por Método:")
    print(f"  Dashboard (VIGENTE ou OK): {vigentes_e_ok} vigentes")
    print(f"  Detalhe (OK apenas):       {vigentes_ok} vigentes")
    print(f"  Pendentes:                 {pendentes}")
    print(f"  Não Iniciados:             {nao_iniciados}")
    
    if vigentes_e_ok != vigentes_ok:
        print(f"\n  ⚠️  DISCREPÂNCIA: {vigentes_e_ok - vigentes_ok} registros com status 'VIGENTE'")

print("\n" + "="*80 + "\n")
