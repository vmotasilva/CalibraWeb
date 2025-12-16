#!/usr/bin/env python
"""
Script para testar a atualização automática de status de Solicitação
"""
import os
import django
from datetime import date, datetime, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from metrologia.models import (
    SolicitacaoCotacao, 
    CotacaoFornecedor, 
    AtendimentoSolicitacao,
    ItemCotacao,
    ItemSolicitacaoCotacao
)

print("\n" + "="*80)
print("TESTE: Verificação automática de status 'Parcialmente Realizado' e 'Realizado'")
print("="*80 + "\n")

# Encontrar uma solicitação com atendimentos
solicitacoes = SolicitacaoCotacao.objects.filter(atendimentos__isnull=False).distinct()

if not solicitacoes.exists():
    print("❌ Nenhuma solicitação com atendimentos encontrada!")
    exit(1)

for solicitacao in solicitacoes[:3]:  # Testar até 3 solicitações
    print(f"\n📋 Solicitação: {solicitacao.numero}")
    print(f"   Status atual: {solicitacao.get_status_display()}")
    print(f"   Atendimentos: {solicitacao.atendimentos.count()}")
    
    if solicitacao.atendimentos.count() == 0:
        print("   ℹ️  Sem atendimentos, pulando...")
        continue
    
    # Contar atendimentos completos
    atendimentos_completos = 0
    atendimentos_total = solicitacao.atendimentos.count()
    
    for atendimento in solicitacao.atendimentos.all():
        local = atendimento.item_cotacao.local_atendimento
        
        status_str = f"     - {atendimento.item_solicitacao.instrumento.tag} ({local}): "
        
        if local == 'NO_LOCAL':
            if atendimento.data_realizada:
                status_str += f"✅ Concluído ({atendimento.data_realizada})"
                atendimentos_completos += 1
            else:
                status_str += "⏳ Pendente"
        elif local == 'NO_LABORATORIO':
            if atendimento.data_retorno:
                status_str += f"✅ Concluído ({atendimento.data_retorno})"
                atendimentos_completos += 1
            else:
                status_str += "⏳ Pendente"
        elif local == 'COMPRAR_NOVO':
            if atendimento.data_chegada:
                status_str += f"✅ Concluído ({atendimento.data_chegada})"
                atendimentos_completos += 1
            else:
                status_str += "⏳ Pendente"
        
        print(status_str)
    
    print(f"\n   Progresso: {atendimentos_completos}/{atendimentos_total} concluídos")
    
    # Calcular status esperado
    if atendimentos_completos == 0:
        status_esperado = "PLANEJADA"
    elif atendimentos_completos > 0 and atendimentos_completos < atendimentos_total:
        status_esperado = "PARCIALMENTE_REALIZADO"
    elif atendimentos_completos == atendimentos_total:
        status_esperado = "REALIZADO"
    else:
        status_esperado = "DESCONHECIDO"
    
    print(f"   Status esperado: {status_esperado}")
    
    # Atualizar status
    solicitacao.atualizar_status_automatico()
    print(f"   Status após atualizar: {solicitacao.get_status_display()}")
    
    if solicitacao.status == status_esperado:
        print("   ✅ Status correto!")
    else:
        print(f"   ❌ Status incorreto! Esperado: {status_esperado}, Obtido: {solicitacao.status}")

print("\n" + "="*80)
print("TESTE CONCLUÍDO")
print("="*80 + "\n")
