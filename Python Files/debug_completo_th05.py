#!/usr/bin/env python
import os
import sys
import django

sys.path.insert(0, 'c:\\CalibraWeb')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from metrologia.models import Instrumento, SolicitacaoCotacao

# Buscar todas as solicitações com TH-05
inst = Instrumento.objects.get(tag='TH-05')
print(f"\n{'='*100}")
print(f"DIAGNÓSTICO COMPLETO: Instrumento {inst.tag}")
print(f"{'='*100}\n")

# Ver TODAS as solicitações que mencionam este instrumento
solicitacoes = SolicitacaoCotacao.objects.filter(
    itens__instrumento=inst
).distinct()

print(f"Solicitações com TH-05: {solicitacoes.count()}")
for sol in solicitacoes:
    print(f"\n{'─'*100}")
    print(f"SOLICITAÇÃO: {sol.numero} (ID: {sol.id})")
    print(f"  Status: {sol.status}")
    print(f"  Data Criação: {sol.data_criacao}")
    print(f"  Atendimentos Totais: {sol.atendimentos.count()}")
    
    # Ver os itens dela
    print(f"\n  ITENS SOLICITADOS:")
    for item in sol.itens.filter(instrumento=inst):
        print(f"    ├─ ItemSolicitacao #{item.id}: {item.instrumento.tag}")
        print(f"    │  Natureza: {item.natureza_necessidade}")
        print(f"    │  Atendimentos: {item.atendimentos.count()}")
        
        for atend in item.atendimentos.all():
            print(f"    │    └─ Atendimento #{atend.id}")
            print(f"    │       Item Cotação: {atend.item_cotacao}")
            print(f"    │       tipo_servico: {atend.item_cotacao.tipo_servico}")
            print(f"    │       local_atendimento: {atend.item_cotacao.local_atendimento}")
            print(f"    │       Status: {atend.status}")
            print(f"    │       Data Realizada: {atend.data_realizada}")
            print(f"    │       Data Envio: {atend.data_envio}")
            print(f"    │       Data Retorno: {atend.data_retorno}")
            print(f"    │       Data Chegada: {atend.data_chegada}")
    
    # Ver cotações
    print(f"\n  COTAÇÕES DA SOLICITAÇÃO:")
    for cot_forn in sol.cotacoes_fornecedores.all():
        print(f"    ├─ Cotação #{cot_forn.id}: {cot_forn.fornecedor.nome_fantasia}")
        
        for item_cot in cot_forn.itens.filter(instrumento=inst):
            print(f"    │  ├─ ItemCotacao #{item_cot.id}: {item_cot.instrumento.tag}")
            print(f"    │  │  tipo_servico: {item_cot.tipo_servico}")
            print(f"    │  │  local_atendimento: {item_cot.local_atendimento}")
            print(f"    │  │  valor: R$ {item_cot.valor_total}")
            print(f"    │  │  Atendimentos: {item_cot.atendimentos.count()}")

print(f"\n{'='*100}\n")
