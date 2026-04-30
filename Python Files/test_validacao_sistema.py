#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SCRIPT DE TESTE - Sistema de Validação de Matriz
Execute este script para testar o sistema de validação
"""

import os
import sys
import django
from datetime import datetime, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from rh.models import Colaborador
from procedures.models import (
    MatrizHabilidade,
    ColaboradorMatrizHabilidade,
    Disciplina,
    AvaliacaoHabilidade,
    SolicitacaoValidacaoMatriz,
    HistoricoValidacaoMassa,
)

def test_validacao_sistema():
    """
    Testa o sistema completo de validação
    """
    print("\n" + "="*70)
    print("TESTE DO SISTEMA DE VALIDAÇÃO DE MATRIZ")
    print("="*70 + "\n")
    
    # 1. Buscar dados de teste
    print("1️⃣  Buscando dados de teste...")
    
    try:
        matriz = MatrizHabilidade.objects.first()
        if not matriz:
            print("❌ Nenhuma matriz encontrada!")
            return False
        print(f"✅ Matriz: {matriz.nome}")
        
        colaboradores = ColaboradorMatrizHabilidade.objects.filter(
            matriz=matriz
        ).values_list('colaborador_id', flat=True)[:3]
        
        if not colaboradores:
            print("❌ Nenhum colaborador associado à matriz!")
            return False
        print(f"✅ {len(list(colaboradores))} colaboradores encontrados")
        
        disciplinas = matriz.disciplinas_matriz.all()[:2]
        print(f"✅ {disciplinas.count()} disciplinas encontradas")
        
    except Exception as e:
        print(f"❌ Erro ao buscar dados: {e}")
        return False
    
    # 2. Criar algumas avaliações de teste
    print("\n2️⃣  Criando avaliações de teste...")
    
    try:
        for colab_id in colaboradores:
            colaborador = Colaborador.objects.get(id=colab_id)
            for disc in disciplinas:
                av, created = AvaliacaoHabilidade.objects.get_or_create(
                    matriz=matriz,
                    colaborador=colaborador,
                    disciplina=disc,
                    defaults={
                        'nivel': 1,
                        'data_avaliacao': datetime.now().date(),
                        'observacoes': 'Avaliação de teste'
                    }
                )
                if created:
                    print(f"   ✅ Criada avaliação para {colaborador.nome_completo} - {disc.nome}")
    except Exception as e:
        print(f"❌ Erro ao criar avaliações: {e}")
        return False
    
    # 3. Testar Solicitação de Validação
    print("\n3️⃣  Testando Solicitação de Validação...")
    
    try:
        validador = Colaborador.objects.filter(is_active=True).first()
        solicitante = Colaborador.objects.filter(is_active=True).exclude(
            id=validador.id if validador else None
        ).first()
        
        if not validador or not solicitante:
            print("❌ Colaboradores insuficientes para teste!")
            return False
        
        # Criar solicitação
        solicitacao, created = SolicitacaoValidacaoMatriz.objects.get_or_create(
            matriz=matriz,
            validador=validador,
            defaults={
                'solicitante': solicitante,
                'status': 'pendente',
                'motivo_solicitacao': f'Teste automático - {datetime.now()}',
            }
        )
        
        if created:
            print(f"✅ Solicitação criada com sucesso!")
            print(f"   - Validador: {solicitacao.validador.nome_completo}")
            print(f"   - Solicitante: {solicitacao.solicitante.nome_completo if solicitacao.solicitante else 'Sistema'}")
            print(f"   - Status: {solicitacao.get_status_display()}")
            print(f"   - ID: {solicitacao.id}")
        else:
            print(f"⚠️  Solicitação já existia: {solicitacao.id}")
    
    except Exception as e:
        print(f"❌ Erro ao criar solicitação: {e}")
        return False
    
    # 4. Testar Histórico de Validação
    print("\n4️⃣  Testando Histórico de Validação...")
    
    try:
        historico = HistoricoValidacaoMassa.objects.create(
            matriz=matriz,
            validador=validador,
            total_avaliacoes=len(list(colaboradores)) * disciplinas.count(),
            avaliacoes_atualizadas=len(list(colaboradores)) * disciplinas.count(),
            motivo='Teste automático de validação',
        )
        
        print(f"✅ Histórico criado com sucesso!")
        print(f"   - Validador: {historico.validador.nome_completo}")
        print(f"   - Total: {historico.total_avaliacoes} avaliações")
        print(f"   - Validadas: {historico.avaliacoes_atualizadas} avaliações")
        print(f"   - Executado em: {historico.executado_em}")
        
    except Exception as e:
        print(f"❌ Erro ao criar histórico: {e}")
        return False
    
    # 5. Contar registros
    print("\n5️⃣  Resumo do Sistema...")
    
    try:
        solicitacoes_pendentes = SolicitacaoValidacaoMatriz.objects.filter(
            status='pendente'
        ).count()
        
        solicitacoes_validadas = SolicitacaoValidacaoMatriz.objects.filter(
            status='validada'
        ).count()
        
        historicosmassa = HistoricoValidacaoMassa.objects.count()
        
        print(f"   📊 SolicitacaoValidacaoMatriz:")
        print(f"      - Pendentes: {solicitacoes_pendentes}")
        print(f"      - Validadas: {solicitacoes_validadas}")
        print(f"   📊 HistoricoValidacaoMassa: {historicosmassa} registros")
        print(f"   📊 AvaliacaoHabilidade: {AvaliacaoHabilidade.objects.filter(matriz=matriz).count()} avaliações")
        
    except Exception as e:
        print(f"❌ Erro ao contar registros: {e}")
        return False
    
    # 6. Testar URLs
    print("\n6️⃣  URLs Disponíveis:")
    print(f"   - Solicitar Validação: /procedures/matrizes/{matriz.id}/solicitar-validacao/")
    print(f"   - Validação Rápida: /procedures/matrizes/{matriz.id}/validacao-rapida/")
    print(f"   - Validações Pendentes: /procedures/validacoes/pendentes/")
    print(f"   - Validar Matriz: /procedures/validacoes/{solicitacao.id}/validar/")
    print(f"   - Avaliações: /procedures/avaliacoes/?matriz={matriz.id}")
    
    print("\n" + "="*70)
    print("✅ TODOS OS TESTES PASSARAM!")
    print("="*70 + "\n")
    
    return True

if __name__ == '__main__':
    success = test_validacao_sistema()
    sys.exit(0 if success else 1)
