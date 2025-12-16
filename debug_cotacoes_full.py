#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from metrologia.models import Instrumento, ItemCotacao, AtendimentoSolicitacao

try:
    inst = Instrumento.objects.get(tag='TH-05')
    print(f"✓ Instrumento: {inst.tag} (ID: {inst.id})\n")

    # Verify ItemCotacao
    item_cotacoes = ItemCotacao.objects.filter(instrumento=inst)
    print(f"ItemCotacao count: {item_cotacoes.count()}")
    for ic in item_cotacoes:
        print(f"  - ID: {ic.id}, Fornecedor: {ic.cotacao_fornecedor.fornecedor.nome_fantasia}, Tipo: {ic.tipo_servico}")

    # Verify AtendimentoSolicitacao
    atendimentos = AtendimentoSolicitacao.objects.filter(item_cotacao__instrumento=inst)
    print(f"\nAtendimentoSolicitacao count: {atendimentos.count()}")
    for at in atendimentos:
        print(f"  - ID: {at.id}, Status: {at.status}, Tipo: {at.item_cotacao.tipo_servico}")
    
    # Check all ItemCotacao in database
    print(f"\n\nTOTAL ItemCotacao no banco: {ItemCotacao.objects.all().count()}")
    print("Todos os ItemCotacao:")
    for ic in ItemCotacao.objects.all()[:10]:
        print(f"  - ID: {ic.id}, Instrumento: {ic.instrumento.tag if ic.instrumento else 'None'}, Fornecedor: {ic.cotacao_fornecedor.fornecedor.nome_fantasia}")

except Exception as e:
    print(f"✗ Erro: {str(e)}")
    import traceback
    traceback.print_exc()
