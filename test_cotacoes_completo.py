#!/usr/bin/env python
"""
Script de Simulação Completa: Testes de Cenários de Cotações
Simula diferentes circunstâncias e testa cada aspecto do fluxo de cotações
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
print("SIMULAÇÃO COMPLETA: CENÁRIOS DE COTAÇÕES EM DIFERENTES CIRCUNSTÂNCIAS")
print("="*100 + "\n")

# Estatísticas
stats = {
    'cenarios_testados': 0,
    'sucessos': 0,
    'falhas': 0,
    'detalhes': []
}

def log_cenario(titulo, descricao, resultado, detalhes=""):
    """Log formatado de um cenário testado"""
    stats['cenarios_testados'] += 1
    if resultado:
        stats['sucessos'] += 1
        status_icon = "✅"
    else:
        stats['falhas'] += 1
        status_icon = "❌"
    
    stats['detalhes'].append({
        'titulo': titulo,
        'resultado': resultado,
        'detalhes': detalhes
    })
    
    print(f"\n{status_icon} CENÁRIO {stats['cenarios_testados']}: {titulo}")
    print(f"   Descrição: {descricao}")
    if detalhes:
        print(f"   {detalhes}")
    print(f"   Resultado: {'PASSOU' if resultado else 'FALHOU'}")

def testar_status_transicoes():
    """Testa todas as transições de status possíveis"""
    print("\n" + "-"*100)
    print("📋 TESTE 1: TRANSIÇÕES DE STATUS")
    print("-"*100)
    
    try:
        # Buscar uma solicitação existente ou criar uma
        solicitacao = SolicitacaoCotacao.objects.filter(itens__isnull=False).first()
        
        if not solicitacao:
            print("⚠️  Nenhuma solicitação com itens encontrada. Pulando...")
            return
        
        status_inicial = solicitacao.status
        
        # Teste 1: ABERTA
        solicitacao.itens.all().delete()
        solicitacao.atualizar_status_automatico()
        resultado1 = solicitacao.status == 'ABERTA'
        log_cenario(
            "Sem Itens → ABERTA",
            "Remover todos os itens deve resultadar em status ABERTA",
            resultado1,
            f"Status obtido: {solicitacao.get_status_display()}"
        )
        
    except Exception as e:
        log_cenario("Transição de Status", "Erro ao testar transições", False, str(e))

def testar_cenario_comprar_novo():
    """Testa cenário específico: COMPRAR_NOVO com múltiplos atendimentos"""
    print("\n" + "-"*100)
    print("📋 TESTE 2: CENÁRIO 'COMPRAR_NOVO' (Compra de Novos Instrumentos)")
    print("-"*100)
    
    try:
        # Buscar solicitação com atendimentos do tipo COMPRAR_NOVO
        atendimentos = AtendimentoSolicitacao.objects.filter(
            item_cotacao__local_atendimento='COMPRAR_NOVO'
        ).select_related('solicitacao')
        
        if not atendimentos.exists():
            print("⚠️  Nenhum atendimento COMPRAR_NOVO encontrado. Pulando...")
            return
        
        solicitacao = atendimentos.first().solicitacao
        atendimentos_sol = solicitacao.atendimentos.filter(
            item_cotacao__local_atendimento='COMPRAR_NOVO'
        )
        
        total = atendimentos_sol.count()
        
        # Cenário 2.1: Nenhum chegou
        for atend in atendimentos_sol:
            atend.data_chegada = None
            atend.save()
        
        solicitacao.atualizar_status_automatico()
        resultado1 = solicitacao.status == 'PLANEJADA'
        log_cenario(
            "COMPRAR_NOVO - Nenhum Chegou",
            "Todos planejados mas nenhum com data_chegada preenchida",
            resultado1,
            f"Total: {total} | Status: {solicitacao.get_status_display()}"
        )
        
        # Cenário 2.2: Alguns chegaram
        atendimentos_sol[0].data_chegada = date.today()
        atendimentos_sol[0].save()
        
        solicitacao.atualizar_status_automatico()
        resultado2 = solicitacao.status == 'PARCIALMENTE_REALIZADO'
        log_cenario(
            "COMPRAR_NOVO - Parcialmente Realizado",
            "1 de múltiplos instrumentos chegaram",
            resultado2,
            f"Concluídos: 1/{total} | Status: {solicitacao.get_status_display()}"
        )
        
        # Cenário 2.3: Todos chegaram
        for atend in atendimentos_sol:
            atend.data_chegada = date.today()
            atend.save()
        
        solicitacao.atualizar_status_automatico()
        resultado3 = solicitacao.status == 'REALIZADO'
        log_cenario(
            "COMPRAR_NOVO - Todos Realizado",
            "Todos os instrumentos chegaram",
            resultado3,
            f"Concluídos: {total}/{total} | Status: {solicitacao.get_status_display()}"
        )
        
    except Exception as e:
        log_cenario("Cenário COMPRAR_NOVO", "Erro ao testar", False, str(e))

def testar_cenario_no_laboratorio():
    """Testa cenário: NO_LABORATORIO com envio e retorno"""
    print("\n" + "-"*100)
    print("📋 TESTE 3: CENÁRIO 'NO_LABORATORIO' (Envio para Laboratório)")
    print("-"*100)
    
    try:
        # Buscar solicitação com atendimentos NO_LABORATORIO
        atendimentos = AtendimentoSolicitacao.objects.filter(
            item_cotacao__local_atendimento='NO_LABORATORIO'
        ).select_related('solicitacao')
        
        if not atendimentos.exists():
            print("⚠️  Nenhum atendimento NO_LABORATORIO encontrado. Pulando...")
            return
        
        solicitacao = atendimentos.first().solicitacao
        atendimentos_sol = solicitacao.atendimentos.filter(
            item_cotacao__local_atendimento='NO_LABORATORIO'
        )
        
        total = atendimentos_sol.count()
        
        # Cenário 3.1: Nenhum retornou
        for atend in atendimentos_sol:
            atend.data_envio = None
            atend.data_retorno = None
            atend.save()
        
        solicitacao.atualizar_status_automatico()
        resultado1 = solicitacao.status == 'PLANEJADA'
        log_cenario(
            "NO_LABORATORIO - Nenhum Enviado",
            "Planejado mas sem envio/retorno",
            resultado1,
            f"Total: {total} | Status: {solicitacao.get_status_display()}"
        )
        
        # Cenário 3.2: Alguns enviados e retornados
        atendimentos_sol[0].data_envio = date.today() - timedelta(days=5)
        atendimentos_sol[0].data_retorno = date.today()
        atendimentos_sol[0].save()
        
        solicitacao.atualizar_status_automatico()
        resultado2 = solicitacao.status == 'PARCIALMENTE_REALIZADO'
        log_cenario(
            "NO_LABORATORIO - Parcialmente Realizado",
            "1 de múltiplos retornou do laboratório",
            resultado2,
            f"Retornados: 1/{total} | Status: {solicitacao.get_status_display()}"
        )
        
        # Cenário 3.3: Todos retornaram
        for atend in atendimentos_sol:
            atend.data_envio = date.today() - timedelta(days=5)
            atend.data_retorno = date.today()
            atend.save()
        
        solicitacao.atualizar_status_automatico()
        resultado3 = solicitacao.status == 'REALIZADO'
        log_cenario(
            "NO_LABORATORIO - Todos Realizado",
            "Todos retornaram do laboratório",
            resultado3,
            f"Retornados: {total}/{total} | Status: {solicitacao.get_status_display()}"
        )
        
    except Exception as e:
        log_cenario("Cenário NO_LABORATORIO", "Erro ao testar", False, str(e))

def testar_cenario_no_local():
    """Testa cenário: NO_LOCAL com realização no local do cliente"""
    print("\n" + "-"*100)
    print("📋 TESTE 4: CENÁRIO 'NO_LOCAL' (Realização no Local do Cliente)")
    print("-"*100)
    
    try:
        # Buscar solicitação com atendimentos NO_LOCAL
        atendimentos = AtendimentoSolicitacao.objects.filter(
            item_cotacao__local_atendimento='NO_LOCAL'
        ).select_related('solicitacao')
        
        if not atendimentos.exists():
            print("⚠️  Nenhum atendimento NO_LOCAL encontrado. Pulando...")
            return
        
        solicitacao = atendimentos.first().solicitacao
        atendimentos_sol = solicitacao.atendimentos.filter(
            item_cotacao__local_atendimento='NO_LOCAL'
        )
        
        total = atendimentos_sol.count()
        
        # Cenário 4.1: Nenhum realizado
        for atend in atendimentos_sol:
            atend.data_realizada = None
            atend.tecnico_responsavel = None
            atend.save()
        
        solicitacao.atualizar_status_automatico()
        resultado1 = solicitacao.status == 'PLANEJADA'
        log_cenario(
            "NO_LOCAL - Nenhum Realizado",
            "Planejado mas sem realização",
            resultado1,
            f"Total: {total} | Status: {solicitacao.get_status_display()}"
        )
        
        # Cenário 4.2: Alguns realizados
        atendimentos_sol[0].data_realizada = date.today()
        atendimentos_sol[0].tecnico_responsavel = "João Silva"
        atendimentos_sol[0].save()
        
        solicitacao.atualizar_status_automatico()
        resultado2 = solicitacao.status == 'PARCIALMENTE_REALIZADO'
        log_cenario(
            "NO_LOCAL - Parcialmente Realizado",
            "1 de múltiplos realizados no local",
            resultado2,
            f"Realizados: 1/{total} | Status: {solicitacao.get_status_display()}"
        )
        
        # Cenário 4.3: Todos realizados
        for atend in atendimentos_sol:
            atend.data_realizada = date.today()
            atend.tecnico_responsavel = "Técnico de Calibração"
            atend.save()
        
        solicitacao.atualizar_status_automatico()
        resultado3 = solicitacao.status == 'REALIZADO'
        log_cenario(
            "NO_LOCAL - Todos Realizado",
            "Todos realizados no local do cliente",
            resultado3,
            f"Realizados: {total}/{total} | Status: {solicitacao.get_status_display()}"
        )
        
    except Exception as e:
        log_cenario("Cenário NO_LOCAL", "Erro ao testar", False, str(e))

def testar_cenario_misto():
    """Testa cenário misto: múltiplos locais de atendimento na mesma solicitação"""
    print("\n" + "-"*100)
    print("📋 TESTE 5: CENÁRIO MISTO (Múltiplos Locais de Atendimento)")
    print("-"*100)
    
    try:
        # Buscar solicitação que tenha atendimentos de diferentes tipos
        solicitacao = SolicitacaoCotacao.objects.annotate(
            tipos_distintos=django.db.models.Count(
                'atendimentos__item_cotacao__local_atendimento',
                distinct=True
            )
        ).filter(tipos_distintos__gte=2).first()
        
        if not solicitacao:
            print("⚠️  Nenhuma solicitação com múltiplos tipos de atendimento encontrada. Pulando...")
            return
        
        # Agrupar por tipo
        tipos = {}
        for atend in solicitacao.atendimentos.all():
            local = atend.item_cotacao.local_atendimento
            if local not in tipos:
                tipos[local] = []
            tipos[local].append(atend)
        
        # Cenário 5.1: Limpar todos
        for atend in solicitacao.atendimentos.all():
            atend.data_realizada = None
            atend.data_retorno = None
            atend.data_chegada = None
            atend.save()
        
        solicitacao.atualizar_status_automatico()
        resultado1 = solicitacao.status == 'PLANEJADA'
        log_cenario(
            "Misto - Nenhum Realizado",
            f"Mix de {len(tipos)} tipos de atendimento, nenhum concluído",
            resultado1,
            f"Tipos: {', '.join(tipos.keys())} | Status: {solicitacao.get_status_display()}"
        )
        
        # Cenário 5.2: Completar alguns tipos
        for local, atends in list(tipos.items())[:1]:  # Completar primeiro tipo
            for atend in atends:
                if local == 'NO_LOCAL':
                    atend.data_realizada = date.today()
                elif local == 'NO_LABORATORIO':
                    atend.data_retorno = date.today()
                elif local == 'COMPRAR_NOVO':
                    atend.data_chegada = date.today()
                atend.save()
        
        solicitacao.atualizar_status_automatico()
        resultado2 = solicitacao.status == 'PARCIALMENTE_REALIZADO'
        log_cenario(
            "Misto - Parcialmente Realizado",
            f"Um tipo completo, outros pendentes",
            resultado2,
            f"Completos: 1/{len(tipos)} | Status: {solicitacao.get_status_display()}"
        )
        
        # Cenário 5.3: Completar todos
        for local, atends in tipos.items():
            for atend in atends:
                if local == 'NO_LOCAL':
                    atend.data_realizada = date.today()
                elif local == 'NO_LABORATORIO':
                    atend.data_retorno = date.today()
                elif local == 'COMPRAR_NOVO':
                    atend.data_chegada = date.today()
                atend.save()
        
        solicitacao.atualizar_status_automatico()
        resultado3 = solicitacao.status == 'REALIZADO'
        log_cenario(
            "Misto - Todos Realizado",
            "Todos os tipos de atendimento completos",
            resultado3,
            f"Completos: {len(tipos)}/{len(tipos)} | Status: {solicitacao.get_status_display()}"
        )
        
    except Exception as e:
        log_cenario("Cenário Misto", "Erro ao testar", False, str(e))

def testar_status_manuais():
    """Testa os status manuais: CONCLUIDA e CANCELADA"""
    print("\n" + "-"*100)
    print("📋 TESTE 6: STATUS MANUAIS (CONCLUIDA e CANCELADA)")
    print("-"*100)
    
    try:
        solicitacao = SolicitacaoCotacao.objects.filter(
            atendimentos__isnull=False
        ).distinct().first()
        
        if not solicitacao:
            print("⚠️  Nenhuma solicitação com atendimentos encontrada. Pulando...")
            return
        
        # Teste 6.1: Marcar como concluída
        solicitacao.marcar_concluida()
        resultado1 = solicitacao.status == 'CONCLUIDA'
        log_cenario(
            "Marcar como CONCLUIDA",
            "Status manual de conclusão",
            resultado1,
            f"Status: {solicitacao.get_status_display()}"
        )
        
        # Teste 6.2: Reabrir de CONCLUIDA
        solicitacao.reabrir()
        resultado2 = solicitacao.status in ['PLANEJADA', 'PARCIALMENTE_REALIZADO', 'REALIZADO']
        log_cenario(
            "Reabrir de CONCLUIDA",
            "Reabrir deve voltar ao status automático apropriado",
            resultado2,
            f"Status: {solicitacao.get_status_display()}"
        )
        
        # Teste 6.3: Marcar como cancelada
        solicitacao.marcar_cancelada()
        resultado3 = solicitacao.status == 'CANCELADA'
        log_cenario(
            "Marcar como CANCELADA",
            "Status manual de cancelamento",
            resultado3,
            f"Status: {solicitacao.get_status_display()}"
        )
        
        # Teste 6.4: Reativar de CANCELADA
        solicitacao.reativar()
        resultado4 = solicitacao.status == 'ABERTA'
        log_cenario(
            "Reativar de CANCELADA",
            "Reativar deve voltar para ABERTA",
            resultado4,
            f"Status: {solicitacao.get_status_display()}"
        )
        
    except Exception as e:
        log_cenario("Status Manuais", "Erro ao testar", False, str(e))

def testar_cotacoes_multiplas():
    """Testa comportamento com múltiplas cotações da mesma solicitação"""
    print("\n" + "-"*100)
    print("📋 TESTE 7: MÚLTIPLAS COTAÇÕES (Mesma Solicitação, Fornecedores Diferentes)")
    print("-"*100)
    
    try:
        # Buscar solicitação com múltiplas cotações
        solicitacao = SolicitacaoCotacao.objects.annotate(
            qtd_cotacoes=django.db.models.Count('cotacoes_fornecedores', distinct=True)
        ).filter(qtd_cotacoes__gte=2, atendimentos__isnull=False).distinct().first()
        
        if not solicitacao:
            print("⚠️  Nenhuma solicitação com múltiplas cotações encontrada. Pulando...")
            return
        
        cotacoes = solicitacao.cotacoes_fornecedores.all()
        total_cotacoes = cotacoes.count()
        
        # Teste 7.1: Todas respondidas
        for cotacao in cotacoes:
            cotacao.status = 'RESPONDIDA'
            cotacao.save()
        
        solicitacao.atualizar_status_automatico()
        resultado1 = solicitacao.status == 'COTACAO_SOLICITADA'
        log_cenario(
            "Múltiplas Cotações - Respondidas",
            f"{total_cotacoes} cotações respondidas",
            resultado1,
            f"Status: {solicitacao.get_status_display()}"
        )
        
        # Teste 7.2: Algumas aceitas
        cotacoes[0].status = 'ACEITA'
        cotacoes[0].save()
        
        solicitacao.atualizar_status_automatico()
        resultado2 = solicitacao.status in ['AGUARDANDO_PLANEJAMENTO', 'PLANEJADA', 'PARCIALMENTE_PLANEJADA']
        log_cenario(
            "Múltiplas Cotações - Parcialmente Aceitas",
            f"1 de {total_cotacoes} aceitas",
            resultado2,
            f"Status: {solicitacao.get_status_display()}"
        )
        
        # Teste 7.3: Todas aceitas
        for cotacao in cotacoes:
            cotacao.status = 'ACEITA'
            cotacao.save()
        
        solicitacao.atualizar_status_automatico()
        resultado3 = solicitacao.status in ['AGUARDANDO_PLANEJAMENTO', 'PLANEJADA', 'PARCIALMENTE_PLANEJADA']
        log_cenario(
            "Múltiplas Cotações - Todas Aceitas",
            f"Todas as {total_cotacoes} cotações aceitas",
            resultado3,
            f"Status: {solicitacao.get_status_display()}"
        )
        
    except Exception as e:
        log_cenario("Múltiplas Cotações", "Erro ao testar", False, str(e))

# Executar todos os testes
import django.db.models
testar_status_transicoes()
testar_cenario_comprar_novo()
testar_cenario_no_laboratorio()
testar_cenario_no_local()
testar_cenario_misto()
testar_status_manuais()
testar_cotacoes_multiplas()

# Relatório Final
print("\n" + "="*100)
print("📊 RELATÓRIO FINAL DE TESTES")
print("="*100)
print(f"\n✅ Cenários Bem-Sucedidos: {stats['sucessos']}")
print(f"❌ Cenários com Falha: {stats['falhas']}")
print(f"📋 Total de Cenários: {stats['cenarios_testados']}")

taxa_sucesso = (stats['sucessos'] / stats['cenarios_testados'] * 100) if stats['cenarios_testados'] > 0 else 0
print(f"📈 Taxa de Sucesso: {taxa_sucesso:.1f}%")

if stats['falhas'] > 0:
    print("\n⚠️  FALHAS DETECTADAS:")
    for detalhe in stats['detalhes']:
        if not detalhe['resultado']:
            print(f"   - {detalhe['titulo']}: {detalhe['detalhes']}")

print("\n" + "="*100 + "\n")
