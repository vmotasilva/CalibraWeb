#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import django

sys.path.insert(0, 'c:\\CalibraWeb')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from metrologia.models import Instrumento, AtendimentoSolicitacao

inst = Instrumento.objects.get(tag='TH-05')
print("\n=== Atendimentos para TH-05 ===\n")

# Todos os atendimentos para este instrumento
atendimentos = AtendimentoSolicitacao.objects.filter(
    item_solicitacao__instrumento=inst
)
print(f"Total Atendimentos: {atendimentos.count()}\n")

for at in atendimentos:
    try:
        ic = at.item_cotacao
        print(f"  Atend #{at.id}")
        print(f"    Solicitacao: {at.solicitacao.numero}")
        print(f"    ItemCotacao: #{ic.id} ({ic.cotacao_fornecedor.numero})")
        print(f"    tipo_servico: {ic.tipo_servico}")
        print(f"    Status: {at.status}")
        print(f"    Data Realizada: {at.data_realizada}")
    except Exception as e:
        print(f"  Atend #{at.id}: ERRO - {str(e)}")

print("\n")
