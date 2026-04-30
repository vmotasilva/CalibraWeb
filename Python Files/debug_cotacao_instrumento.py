#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Debug: Verificar convergência de dados - Cotação vs Instrumento
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

if __name__ == '__main__':

if __name__ == '__main__':

    from metrologia.models import Instrumento, ItemCotacao, AtendimentoSolicitacao, SolicitacaoCotacao

    # Procurar pelo instrumento TH-05
    try:
        inst = Instrumento.objects.get(tag='TH-05')
        print(f"\n{'='*80}")
        print(f"✅ Instrumento encontrado: {inst.tag}")
        print(f"{'='*80}\n")
    
    # 1. Verificar cotações diretas
    print(f"1️⃣  COTAÇÕES DIRETAS (ItemCotacao.instrumento = TH-05):")
    cotacoes = ItemCotacao.objects.filter(instrumento=inst)
    print(f"   Total: {cotacoes.count()}")
    
    for cotacao in cotacoes:
        print(f"\n   ├─ ID: {cotacao.id}")
        print(f"   ├─ Cotação Fornecedor: {cotacao.cotacao_fornecedor.numero}")
        print(f"   ├─ Fornecedor: {cotacao.cotacao_fornecedor.fornecedor.nome}")
        print(f"   ├─ tipo_servico: {cotacao.tipo_servico} (esperado: CALIBRACAO ou AQUISICAO)")
        print(f"   ├─ local_atendimento: {cotacao.local_atendimento} (esperado: NO_LOCAL, NO_LABORATORIO, COMPRAR_NOVO)")
        print(f"   ├─ Atendimentos:")
        
        for atend in cotacao.atendimentos.all():
            print(f"   │  ├─ ID: {atend.id}")
            print(f"   │  ├─ Status: {atend.status}")
            print(f"   │  ├─ Data Realizada: {atend.data_realizada}")
            print(f"   │  ├─ Data Envio: {atend.data_envio}")
            print(f"   │  ├─ Data Retorno: {atend.data_retorno}")
            print(f"   │  └─ Data Chegada: {atend.data_chegada}")
    
    # 2. Verificar atendimentos diretos
    print(f"\n\n2️⃣  ATENDIMENTOS DIRETOS (ItemSolicitacao.instrumento = TH-05):")
    atendimentos = AtendimentoSolicitacao.objects.filter(
        item_solicitacao__instrumento=inst
    ).select_related('item_cotacao__cotacao_fornecedor')
    
    print(f"   Total: {atendimentos.count()}")
    for atend in atendimentos:
        print(f"\n   ├─ ID: {atend.id}")
        print(f"   ├─ Solicitação: {atend.solicitacao.numero}")
        print(f"   ├─ Item Cotação: {atend.item_cotacao}")
        print(f"   ├─ Local Atendimento: {atend.item_cotacao.local_atendimento}")
        print(f"   ├─ Tipo Serviço: {atend.item_cotacao.tipo_servico}")
        print(f"   └─ Status: {atend.status}")
    
    # 3. Verificar solicitações
    print(f"\n\n3️⃣  SOLICITAÇÕES COM ESTE INSTRUMENTO:")
    solicitacoes = SolicitacaoCotacao.objects.filter(
        itens__instrumento=inst
    ).distinct()
    
    print(f"   Total: {solicitacoes.count()}")
    for sol in solicitacoes:
        print(f"\n   ├─ {sol.numero}")
        print(f"   ├─ Status: {sol.status}")
        print(f"   └─ Atendimentos: {sol.atendimentos.count()}")
    
    # 4. Debug da query que escrevi
    print(f"\n\n4️⃣  DEBUG DA QUERY (como escrita na view):")
    cotacoes_itens = ItemCotacao.objects.filter(
        instrumento=inst
    ).select_related(
        'cotacao_fornecedor__fornecedor',
        'item_solicitacao__solicitacao'
    ).prefetch_related(
        'atendimentos__item_cotacao__cotacao_fornecedor'
    )
    
    print(f"   Total com query: {cotacoes_itens.count()}")
    
    # Separar por tipo
    calibracoes = [c for c in cotacoes_itens if c.tipo_servico == 'CALIBRACAO']
    aquisicoes = [c for c in cotacoes_itens if c.tipo_servico == 'AQUISICAO']
    
    print(f"   ├─ Calibrações (tipo_servico='CALIBRACAO'): {len(calibracoes)}")
    print(f"   └─ Aquisições (tipo_servico='AQUISICAO'): {len(aquisicoes)}")
    
    # 5. Verificar rastreios laboratorio
    print(f"\n\n5️⃣  RASTREIOS EM LABORATÓRIO:")
    rastreios = AtendimentoSolicitacao.objects.filter(
        item_solicitacao__instrumento=inst,
        item_cotacao__local_atendimento='NO_LABORATORIO'
    )
    
    print(f"   Total: {rastreios.count()}")
    for r in rastreios:
        print(f"   ├─ ID: {r.id}")
        print(f"   ├─ Cotação: {r.item_cotacao.cotacao_fornecedor.numero}")
        print(f"   ├─ Data Envio: {r.data_envio}")
        print(f"   ├─ Data Retorno: {r.data_retorno}")
        print(f"   └─ Status: {r.status}")
    
    # 6. Valores únicos de local_atendimento
    print(f"\n\n6️⃣  VALORES ÚNICOS DE local_atendimento PARA ESTE INSTRUMENTO:")
    valores = ItemCotacao.objects.filter(
        instrumento=inst
    ).values_list('local_atendimento', flat=True).distinct()
    
    for valor in valores:
        print(f"   ├─ {valor}")
    
    print(f"\n{'='*80}\n")
    
except Instrumento.DoesNotExist:
    print("❌ Instrumento TH-05 não encontrado!")
except Exception as e:
    print(f"❌ Erro: {str(e)}")
    import traceback
    traceback.print_exc()