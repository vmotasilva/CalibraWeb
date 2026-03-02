#!/usr/bin/env python
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from metrologia.models import Instrumento, SolicitacaoCotacao

inst = Instrumento.objects.get(tag='TH-05')
print(f"Instrumento: {inst.tag} (ID: {inst.id})\n")

# Test 1: Using 'itens' reverse relation
print("1. Query usando 'itens' (reverse relation):")
sols = SolicitacaoCotacao.objects.filter(itens__instrumento=inst).distinct()
print(f"   Resultado: {sols.count()} solicitações")
for s in sols:
    print(f"   - {s.numero}: {s.status}")

# Test 2: Using 'solicitacoes_itens' on Instrumento
print("\n2. Query usando 'solicitacoes_itens' (reverse relation no Instrumento):")
items = inst.solicitacoes_itens.all()
print(f"   Resultado: {items.count()} items")
for item in items:
    print(f"   - Item de solicitação: {item.solicitacao.numero}")
