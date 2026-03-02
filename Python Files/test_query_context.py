#!/usr/bin/env python
import os
import sys
import django

sys.path.insert(0, 'c:\\CalibraWeb')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from metrologia.models import ItemCotacao, Instrumento

# Buscar TH-05
inst = Instrumento.objects.get(tag='TH-05')
print(f"\n{'='*80}")
print(f"DEBUG: Instrumento {inst.tag} (ID: {inst.id})")
print(f"{'='*80}\n")

# Query como na view
cotacoes_itens = list(
    ItemCotacao.objects.filter(
        instrumento=inst
    ).select_related(
        'cotacao_fornecedor__fornecedor',
        'item_solicitacao__solicitacao'
    ).prefetch_related(
        'atendimentos__item_cotacao__cotacao_fornecedor'
    ).order_by('-data_criacao')
)

print(f"1. Total ItemCotacao encontrados: {len(cotacoes_itens)}")

# Separar como na view
cotacoes_calibracao = [c for c in cotacoes_itens if c.tipo_servico == 'CALIBRACAO']
cotacoes_aquisicao = [c for c in cotacoes_itens if c.tipo_servico == 'AQUISICAO']

print(f"2. Calibrações (tipo_servico='CALIBRACAO'): {len(cotacoes_calibracao)}")
print(f"3. Aquisições (tipo_servico='AQUISICAO'): {len(cotacoes_aquisicao)}")

# Detalhar calibrações
for i, cal in enumerate(cotacoes_calibracao, 1):
    print(f"\n   [{i}] ItemCotacao #{cal.id}")
    print(f"       tipo_servico: {cal.tipo_servico}")
    print(f"       local_atendimento: {cal.local_atendimento}")
    print(f"       instrumento: {cal.instrumento.tag}")
    print(f"       Atendimentos vinculados: {cal.atendimentos.count()}")
    
    for j, atend in enumerate(cal.atendimentos.all(), 1):
        print(f"          [{j}] AtendimentoSolicitacao #{atend.id}")
        print(f"              Status: {atend.status}")
        print(f"              Data Prevista: {atend.data_prevista_atendimento}")
        print(f"              Data Realizada: {atend.data_realizada}")

print(f"\n{'='*80}\n")
