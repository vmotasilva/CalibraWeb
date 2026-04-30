#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from metrologia.models import AtendimentoSolicitacao, Instrumento

# Get TH-05 instrument
try:
    instrumento = Instrumento.objects.get(tag='TH-05')
    print(f"✓ Instrumento encontrado: {instrumento.tag} (ID: {instrumento.id})")
    
    # Get quotations for this instrument
    atendimentos = AtendimentoSolicitacao.objects.filter(
        item_cotacao__instrumento=instrumento
    ).select_related(
        'item_cotacao__cotacao_fornecedor__fornecedor',
        'item_cotacao__item_solicitacao__solicitacao'
    ).prefetch_related(
        'historicos_calibracao'
    )
    
    print(f"\n✓ Total de atendimentos/cotações: {atendimentos.count()}")
    
    for i, atendimento in enumerate(atendimentos, 1):
        print(f"\n  [{i}] Atendimento #{atendimento.id}")
        print(f"      Status: {atendimento.get_status_display()}")
        print(f"      Tipo Serviço: {atendimento.item_cotacao.tipo_servico}")
        print(f"      Local: {atendimento.item_cotacao.local_atendimento}")
        try:
            fornecedor_nome = atendimento.item_cotacao.cotacao_fornecedor.fornecedor.nome_fantasia or atendimento.item_cotacao.cotacao_fornecedor.fornecedor.razao_social
        except:
            fornecedor_nome = str(atendimento.item_cotacao.cotacao_fornecedor.fornecedor)
        print(f"      Fornecedor: {fornecedor_nome}")
        print(f"      Data Prevista: {atendimento.data_prevista_atendimento}")
        print(f"      Históricos: {atendimento.historicos_calibracao.count()}")
    
    # Separate by type
    calibracoes = atendimentos.filter(item_cotacao__tipo_servico='CALIBRACAO')
    aquisicoes = atendimentos.filter(item_cotacao__tipo_servico='AQUISICAO')
    
    print(f"\n✓ Resumo:")
    print(f"   Calibrações: {calibracoes.count()}")
    print(f"   Aquisições: {aquisicoes.count()}")
    
except Instrumento.DoesNotExist:
    print("✗ Instrumento TH-05 não encontrado")
except Exception as e:
    print(f"✗ Erro: {str(e)}")
