#!/usr/bin/env python
"""Teste standalone da query de cotações"""
import os
import sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from metrologia.models import Instrumento, ItemCotacao, AtendimentoSolicitacao

print("=" * 80)
print("TESTE DE COTAÇÕES - TH-05")
print("=" * 80)

try:
    inst = Instrumento.objects.get(tag='TH-05')
    print(f"\n✓ Instrumento encontrado: {inst.tag} (ID: {inst.id})")
    
    # Test 1: ItemCotacao direct query
    print("\n1. QUERY ItemCotacao DIRETO:")
    iq = ItemCotacao.objects.filter(instrumento=inst)
    print(f"   Count: {iq.count()}")
    for ic in iq:
        print(f"   - ID: {ic.id}, Instrumento ID: {ic.instrumento_id}, Tipo: {ic.tipo_servico}")
    
    # Test 2: With select_related
    print("\n2. QUERY ItemCotacao COM SELECT_RELATED:")
    todas = ItemCotacao.objects.filter(
        instrumento=inst
    ).select_related(
        'cotacao_fornecedor__fornecedor',
        'item_solicitacao__solicitacao'
    ).order_by('-cotacao_fornecedor__data_criacao')
    print(f"   Count: {todas.count()}")
    for ic in todas:
        print(f"   - ID: {ic.id}, CF ID: {ic.cotacao_fornecedor_id}, Tipo: {ic.tipo_servico}")
    
    # Test 3: list() conversion
    print("\n3. APÓS CONVERTER PARA LIST:")
    todas_list = list(todas)
    print(f"   Count: {len(todas_list)}")
    for ic in todas_list:
        print(f"   - ID: {ic.id}, Fornecedor: {ic.cotacao_fornecedor.fornecedor.nome_fantasia}")

except Exception as e:
    print(f"\n✗ Erro: {str(e)}")
    import traceback
    traceback.print_exc()
