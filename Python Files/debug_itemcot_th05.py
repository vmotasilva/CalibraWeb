#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import django

sys.path.insert(0, 'c:\\CalibraWeb')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from metrologia.models import Instrumento, ItemCotacao, AtendimentoSolicitacao

inst = Instrumento.objects.get(tag='TH-05')
print("\n=== ItemCotacao para TH-05 ===\n")

# TODAS as ItemCotacao para TH-05 (sem limite)
todos_item_cot = ItemCotacao.objects.filter(instrumento=inst)
print(f"Total ItemCotacao: {todos_item_cot.count()}")

for ic in todos_item_cot:
    print(f"\n  ItemCotacao #{ic.id}")
    print(f"    Cotacao Fornecedor: {ic.cotacao_fornecedor.numero} ({ic.cotacao_fornecedor.fornecedor.nome_fantasia})")
    print(f"    tipo_servico: {ic.tipo_servico}")
    print(f"    local_atendimento: {ic.local_atendimento}")
    print(f"    Atendimentos: {ic.atendimentos.count()}")
    
    for at in ic.atendimentos.all():
        print(f"      - Atend #{at.id}: {at.status}, realizada={at.data_realizada}")

print("\n")
