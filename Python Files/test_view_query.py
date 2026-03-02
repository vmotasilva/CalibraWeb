#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from metrologia.models import Instrumento, SolicitacaoCotacao

# Test with TH-05
instr = Instrumento.objects.get(tag='TH-05')
print(f"Instrumento: {instr.tag} (ID: {instr.id})")

# Test 1: Direct query
print("\n1. Query direto - SolicitacaoCotacao.objects.filter(itens__instrumento=instr):")
sols = SolicitacaoCotacao.objects.filter(itens__instrumento=instr).distinct()
print(f"   Resultado: {sols.count()} solicitações")
for s in sols:
    print(f"   - {s.numero} ({s.status}) - ID: {s.id}")

# Test 2: Check if items exist
print("\n2. Items que contêm TH-05:")
from metrologia.models import ItemSolicitacaoCotacao
items = ItemSolicitacaoCotacao.objects.filter(instrumento=instr)
print(f"   Resultado: {items.count()} items")
for item in items:
    print(f"   - Item ID: {item.id}, Solicitação: {item.solicitacao.numero}")

# Test 3: Check data_criacao field
print("\n3. Verificar dados da solicitação:")
sol = SolicitacaoCotacao.objects.filter(itens__instrumento=instr).first()
if sol:
    print(f"   Número: {sol.numero}")
    print(f"   Status: {sol.status}")
    print(f"   Data Criação: {sol.data_criacao}")
    print(f"   Responsável: {sol.responsavel}")
    print(f"   Items: {sol.itens.count()}")
