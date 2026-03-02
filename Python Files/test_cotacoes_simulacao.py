#!/usr/bin/env python
"""
Script de Simulação Melhorada: Testes Detalhados de Cotações
Com dados de teste criados para cada cenário específico
"""
import os
import django
from datetime import date, datetime, timedelta
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from metrologia.models import (
    SolicitacaoCotacao, 
    CotacaoFornecedor, 
    AtendimentoSolicitacao,
    ItemCotacao,
    ItemSolicitacaoCotacao,
    Instrumento,
)
from fornecedores.models import Fornecedor

print("\n" + "="*100)
print("SIMULAÇÃO MELHORADA: TESTES DETALHADOS DE CENÁRIOS DE COTAÇÕES")
print("="*100 + "\n")

# Estatísticas
stats = {
    'cenarios': [],
}

def relatorio_cenario(num, titulo, resultado, detalhes):
    """Adiciona um cenário ao relatório"""
    stats['cenarios'].append({
        'num': num,
        'titulo': titulo,
        'resultado': resultado,
        'detalhes': detalhes
    })
    
    icon = "✅" if resultado else "❌"
    print(f"{icon} CENÁRIO {num}: {titulo}")
    print(f"   {detalhes}")
    print(f"   Resultado: {'PASSOU ✓' if resultado else 'FALHOU ✗'}\n")

contador = 0

# ==============================================================================
print("-" * 100)
print("SEÇÃO 1: CENÁRIOS COM COMPRAR_NOVO")
print("-" * 100 + "\n")

# Encontrar solicitação com COMPRAR_NOVO
solicitacao = SolicitacaoCotacao.objects.filter(
    atendimentos__item_cotacao__local_atendimento='COMPRAR_NOVO'
).distinct().first()

if solicitacao:
    atendimentos = solicitacao.atendimentos.filter(
        item_cotacao__local_atendimento='COMPRAR_NOVO'
    )
    
    # CENÁRIO 1.1
    contador += 1
    for atend in atendimentos:
        atend.data_chegada = None
        atend.save()
    solicitacao.atualizar_status_automatico()
    resultado = solicitacao.status == 'PLANEJADA'
    relatorio_cenario(
        contador, 
        "COMPRAR_NOVO: Planejado, nada chegou",
        resultado,
        f"Total atendimentos: {atendimentos.count()} | Status: {solicitacao.get_status_display()}"
    )
    
    # CENÁRIO 1.2
    contador += 1
    if atendimentos.count() >= 2:
        atendimentos[0].data_chegada = date.today()
        atendimentos[0].save()
        solicitacao.atualizar_status_automatico()
        resultado = solicitacao.status == 'PARCIALMENTE_REALIZADO'
        relatorio_cenario(
            contador,
            "COMPRAR_NOVO: Parcialmente Realizado (alguns chegaram)",
            resultado,
            f"Concluídos: 1/{atendimentos.count()} | Status: {solicitacao.get_status_display()}"
        )
    
    # CENÁRIO 1.3
    contador += 1
    for atend in atendimentos:
        atend.data_chegada = date.today()
        atend.save()
    solicitacao.atualizar_status_automatico()
    resultado = solicitacao.status == 'REALIZADO'
    relatorio_cenario(
        contador,
        "COMPRAR_NOVO: Todos Realizado (todos chegaram)",
        resultado,
        f"Concluídos: {atendimentos.count()}/{atendimentos.count()} | Status: {solicitacao.get_status_display()}"
    )
else:
    print("⚠️  Sem solicitações com atendimentos COMPRAR_NOVO. Pulando seção 1.\n")

# ==============================================================================
print("-" * 100)
print("SEÇÃO 2: CENÁRIOS COM NO_LABORATORIO")
print("-" * 100 + "\n")

solicitacao = SolicitacaoCotacao.objects.filter(
    atendimentos__item_cotacao__local_atendimento='NO_LABORATORIO'
).distinct().first()

if solicitacao:
    atendimentos = solicitacao.atendimentos.filter(
        item_cotacao__local_atendimento='NO_LABORATORIO'
    )
    
    # CENÁRIO 2.1
    contador += 1
    for atend in atendimentos:
        atend.data_envio = None
        atend.data_retorno = None
        atend.save()
    solicitacao.atualizar_status_automatico()
    resultado = solicitacao.status == 'PLANEJADA'
    relatorio_cenario(
        contador,
        "NO_LABORATORIO: Planejado, nenhum enviado",
        resultado,
        f"Total atendimentos: {atendimentos.count()} | Status: {solicitacao.get_status_display()}"
    )
    
    # CENÁRIO 2.2
    contador += 1
    if atendimentos.count() >= 2:
        atendimentos[0].data_envio = date.today() - timedelta(days=10)
        atendimentos[0].data_retorno = date.today()
        atendimentos[0].save()
        solicitacao.atualizar_status_automatico()
        resultado = solicitacao.status == 'PARCIALMENTE_REALIZADO'
        relatorio_cenario(
            contador,
            "NO_LABORATORIO: Parcialmente Realizado (alguns retornaram)",
            resultado,
            f"Retornados: 1/{atendimentos.count()} | Status: {solicitacao.get_status_display()}"
        )
    
    # CENÁRIO 2.3
    contador += 1
    for atend in atendimentos:
        atend.data_envio = date.today() - timedelta(days=10)
        atend.data_retorno = date.today()
        atend.save()
    solicitacao.atualizar_status_automatico()
    resultado = solicitacao.status == 'REALIZADO'
    relatorio_cenario(
        contador,
        "NO_LABORATORIO: Todos Realizado (todos retornaram)",
        resultado,
        f"Retornados: {atendimentos.count()}/{atendimentos.count()} | Status: {solicitacao.get_status_display()}"
    )
else:
    print("⚠️  Sem solicitações com atendimentos NO_LABORATORIO. Pulando seção 2.\n")

# ==============================================================================
print("-" * 100)
print("SEÇÃO 3: CENÁRIOS COM NO_LOCAL")
print("-" * 100 + "\n")

solicitacao = SolicitacaoCotacao.objects.filter(
    atendimentos__item_cotacao__local_atendimento='NO_LOCAL'
).distinct().first()

if solicitacao:
    atendimentos = solicitacao.atendimentos.filter(
        item_cotacao__local_atendimento='NO_LOCAL'
    )
    
    # CENÁRIO 3.1
    contador += 1
    for atend in atendimentos:
        atend.data_realizada = None
        atend.tecnico_responsavel = None
        atend.save()
    solicitacao.atualizar_status_automatico()
    resultado = solicitacao.status == 'PLANEJADA'
    relatorio_cenario(
        contador,
        "NO_LOCAL: Planejado, nenhum realizado",
        resultado,
        f"Total atendimentos: {atendimentos.count()} | Status: {solicitacao.get_status_display()}"
    )
    
    # CENÁRIO 3.2
    contador += 1
    if atendimentos.count() >= 2:
        atendimentos[0].data_realizada = date.today()
        atendimentos[0].tecnico_responsavel = "Técnico Silva"
        atendimentos[0].save()
        solicitacao.atualizar_status_automatico()
        resultado = solicitacao.status == 'PARCIALMENTE_REALIZADO'
        relatorio_cenario(
            contador,
            "NO_LOCAL: Parcialmente Realizado (alguns realizados)",
            resultado,
            f"Realizados: 1/{atendimentos.count()} | Status: {solicitacao.get_status_display()}"
        )
    
    # CENÁRIO 3.3
    contador += 1
    for atend in atendimentos:
        atend.data_realizada = date.today()
        atend.tecnico_responsavel = "Técnico Silva"
        atend.save()
    solicitacao.atualizar_status_automatico()
    resultado = solicitacao.status == 'REALIZADO'
    relatorio_cenario(
        contador,
        "NO_LOCAL: Todos Realizado (todos realizados)",
        resultado,
        f"Realizados: {atendimentos.count()}/{atendimentos.count()} | Status: {solicitacao.get_status_display()}"
    )
else:
    print("⚠️  Sem solicitações com atendimentos NO_LOCAL. Pulando seção 3.\n")

# ==============================================================================
print("-" * 100)
print("SEÇÃO 4: TRANSIÇÕES DE STATUS MANUAIS")
print("-" * 100 + "\n")

solicitacao = SolicitacaoCotacao.objects.filter(
    atendimentos__isnull=False
).distinct().first()

if solicitacao:
    # CENÁRIO 4.1
    contador += 1
    status_antes = solicitacao.status
    solicitacao.marcar_concluida()
    resultado = solicitacao.status == 'CONCLUIDA'
    relatorio_cenario(
        contador,
        "Marcar como CONCLUIDA (manual)",
        resultado,
        f"De: {status_antes} | Para: {solicitacao.get_status_display()}"
    )
    
    # CENÁRIO 4.2
    contador += 1
    solicitacao.reabrir()
    resultado = solicitacao.status != 'CONCLUIDA'
    relatorio_cenario(
        contador,
        "Reabrir de CONCLUIDA",
        resultado,
        f"Novo status: {solicitacao.get_status_display()}"
    )
    
    # CENÁRIO 4.3
    contador += 1
    solicitacao.marcar_cancelada()
    resultado = solicitacao.status == 'CANCELADA'
    relatorio_cenario(
        contador,
        "Marcar como CANCELADA (manual)",
        resultado,
        f"Para: {solicitacao.get_status_display()}"
    )
    
    # CENÁRIO 4.4
    contador += 1
    solicitacao.reativar()
    resultado = solicitacao.status == 'ABERTA'
    relatorio_cenario(
        contador,
        "Reativar de CANCELADA",
        resultado,
        f"Para: {solicitacao.get_status_display()}"
    )
else:
    print("⚠️  Sem solicitações com atendimentos. Pulando seção 4.\n")

# ==============================================================================
print("-" * 100)
print("SEÇÃO 5: COTAÇÕES MÚLTIPLAS")
print("-" * 100 + "\n")

from django.db.models import Count

solicitacao = SolicitacaoCotacao.objects.annotate(
    qtd_cotacoes=Count('cotacoes_fornecedores', distinct=True)
).filter(qtd_cotacoes__gte=2).first()

if solicitacao:
    cotacoes = solicitacao.cotacoes_fornecedores.all()
    
    # CENÁRIO 5.1
    contador += 1
    for cotacao in cotacoes:
        cotacao.status = 'RASCUNHO'
        cotacao.save()
    solicitacao.atualizar_status_automatico()
    resultado = solicitacao.status in ['INSTRUMENTOS_SELECIONADOS', 'AGUARDANDO_PLANEJAMENTO']
    relatorio_cenario(
        contador,
        "Múltiplas Cotações: Todas em RASCUNHO",
        resultado,
        f"Total: {cotacoes.count()} | Status: {solicitacao.get_status_display()}"
    )
    
    # CENÁRIO 5.2
    contador += 1
    for cotacao in cotacoes:
        cotacao.status = 'RESPONDIDA'
        cotacao.save()
    solicitacao.atualizar_status_automatico()
    resultado = solicitacao.status == 'COTACAO_SOLICITADA'
    relatorio_cenario(
        contador,
        "Múltiplas Cotações: Todas RESPONDIDAS",
        resultado,
        f"Total: {cotacoes.count()} | Status: {solicitacao.get_status_display()}"
    )
    
    # CENÁRIO 5.3
    contador += 1
    for cotacao in cotacoes:
        cotacao.status = 'ACEITA'
        cotacao.save()
    solicitacao.atualizar_status_automatico()
    resultado = solicitacao.status in ['AGUARDANDO_PLANEJAMENTO', 'PLANEJADA', 'PARCIALMENTE_PLANEJADA']
    relatorio_cenario(
        contador,
        "Múltiplas Cotações: Todas ACEITAS",
        resultado,
        f"Total: {cotacoes.count()} | Status: {solicitacao.get_status_display()}"
    )
else:
    print("⚠️  Sem solicitações com múltiplas cotações. Pulando seção 5.\n")

# ==============================================================================
# RELATÓRIO FINAL
print("=" * 100)
print("📊 RELATÓRIO FINAL DE TESTES")
print("=" * 100 + "\n")

sucessos = sum(1 for c in stats['cenarios'] if c['resultado'])
falhas = sum(1 for c in stats['cenarios'] if not c['resultado'])
total = len(stats['cenarios'])

print(f"✅ Cenários Bem-Sucedidos: {sucessos}")
print(f"❌ Cenários com Falha: {falhas}")
print(f"📋 Total de Cenários: {total}")

if total > 0:
    taxa = (sucessos / total * 100)
    print(f"📈 Taxa de Sucesso: {taxa:.1f}%\n")
    
    if falhas > 0:
        print("⚠️  FALHAS DETECTADAS:")
        for c in stats['cenarios']:
            if not c['resultado']:
                print(f"   ❌ Cenário {c['num']}: {c['titulo']}")
                print(f"      {c['detalhes']}\n")

print("=" * 100 + "\n")
