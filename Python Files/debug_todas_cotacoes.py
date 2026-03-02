#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from metrologia.models import Instrumento, ItemCotacao

# Get TH-05 instrument
try:
    instrumento = Instrumento.objects.get(tag='TH-05')
    print(f"✓ Instrumento encontrado: {instrumento.tag} (ID: {instrumento.id})")
    
    # Get all ItemCotacao for this instrument
    todas_cotacoes = ItemCotacao.objects.filter(
        instrumento=instrumento
    ).select_related(
        'cotacao_fornecedor__fornecedor',
        'item_solicitacao__solicitacao'
    ).order_by('-cotacao_fornecedor__data_criacao')
    
    print(f"\n✓ Total de ItemCotacao: {todas_cotacoes.count()}")
    
    for i, cotacao in enumerate(todas_cotacoes, 1):
        print(f"\n  [{i}] ItemCotacao #{cotacao.id}")
        print(f"      Cotacao Fornecedor: #{cotacao.cotacao_fornecedor.numero}")
        print(f"      Fornecedor: {cotacao.cotacao_fornecedor.fornecedor.nome_fantasia}")
        print(f"      Tipo: {cotacao.tipo_servico}")
        print(f"      Valor: R$ {cotacao.valor_total}")
        print(f"      Solicitacao ID: {cotacao.item_solicitacao.solicitacao.id}")
        print(f"      Data: {cotacao.cotacao_fornecedor.data_criacao|date:'d/m/Y'}")
    
except Instrumento.DoesNotExist:
    print("✗ Instrumento TH-05 não encontrado")
except Exception as e:
    print(f"✗ Erro: {str(e)}")
    import traceback
    traceback.print_exc()
