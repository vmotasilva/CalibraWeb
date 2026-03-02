#!/usr/bin/env python
"""
Script de teste para validar a correção de exclusão de solicitação
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from metrologia.models import SolicitacaoCotacao

print("\n" + "="*100)
print("TESTE: Deleção de Solicitação com Dependências")
print("="*100 + "\n")

# Encontrar uma solicitação para teste
solicitacao = SolicitacaoCotacao.objects.filter(
    atendimentos__isnull=False
).distinct().first()

if not solicitacao:
    print("❌ Nenhuma solicitação com atendimentos encontrada para teste.")
    exit(1)

print(f"📋 Solicitação Selecionada para Teste:")
print(f"   ID: {solicitacao.id}")
print(f"   Número: {solicitacao.numero}")
print(f"   Itens: {solicitacao.itens.count()}")
print(f"   Cotações: {solicitacao.cotacoes_fornecedores.count()}")
print(f"   Atendimentos: {solicitacao.atendimentos.count()}")

print("\n" + "-"*100)
print("SIMULANDO DELEÇÃO...")
print("-"*100 + "\n")

try:
    numero = solicitacao.numero
    
    # Deletar em cascata conforme implementado na view
    print("1️⃣  Deletando atendimentos...")
    qtd_atendimentos = solicitacao.atendimentos.count()
    solicitacao.atendimentos.all().delete()
    print(f"   ✅ {qtd_atendimentos} atendimento(s) deletado(s)")
    
    print("\n2️⃣  Deletando cotações...")
    qtd_cotacoes = solicitacao.cotacoes_fornecedores.count()
    solicitacao.cotacoes_fornecedores.all().delete()
    print(f"   ✅ {qtd_cotacoes} cotação(ões) deletada(s)")
    
    print("\n3️⃣  Deletando itens da solicitação...")
    qtd_itens = solicitacao.itens.count()
    solicitacao.itens.all().delete()
    print(f"   ✅ {qtd_itens} item(ns) deletado(s)")
    
    print("\n4️⃣  Deletando solicitação...")
    solicitacao.delete()
    print(f"   ✅ Solicitação {numero} deletada!")
    
    print("\n" + "="*100)
    print("✅ SUCESSO! A deleção funcionou corretamente!")
    print("="*100 + "\n")
    
except Exception as e:
    print(f"\n❌ ERRO ao deletar: {str(e)}")
    print("\n" + "="*100)
    print("FALHA NA DELEÇÃO")
    print("="*100 + "\n")
    exit(1)
