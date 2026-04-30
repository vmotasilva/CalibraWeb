#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import django

sys.path.insert(0, 'c:\\CalibraWeb')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from metrologia.models import Instrumento, SolicitacaoCotacao

inst = Instrumento.objects.get(tag='TH-05')
print("\n=== DIAGNÓSTICO TH-05 ===\n")

solicitacoes = SolicitacaoCotacao.objects.filter(
    itens__instrumento=inst
).distinct()

print(f"Solicitações: {solicitacoes.count()}")
for sol in solicitacoes:
    print(f"\nSOL: {sol.numero}")
    print(f"  Atendimentos: {sol.atendimentos.count()}")
    
    for atend in sol.atendimentos.all():
        try:
            item_cot = atend.item_cotacao
            print(f"    - Atend #{atend.id}: {item_cot.tipo_servico} / {item_cot.local_atendimento}")
            print(f"      Status: {atend.status}, Data Realizada: {atend.data_realizada}")
        except:
            print(f"    - Atend #{atend.id}: (erro ao carregar)")

print("\n")
