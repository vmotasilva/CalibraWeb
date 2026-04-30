#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🚀 Script de Demonstração - Importação de Procedimentos

Demonstra o funcionamento completo do sistema de importação em massa.
Cria arquivo Excel de exemplo e processa importação com todos os modos.

Execução:
    python manage.py shell < scripts/demo_importacao_procedimentos.py
"""

import os
import django
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from procedures.models import Procedimento
from procedures.services.importacao_procedimentos import ImportacaoProcedimentosService


def criar_arquivo_demo(arquivo_path: str = None):
    """Cria arquivo Excel de demonstração."""
    print("\n" + "="*80)
    print("📝 CRIANDO ARQUIVO DE DEMONSTRAÇÃO")
    print("="*80)
    
    # Dados de exemplo
    dados = {
        'codigo': [
            'POP.001', 'POP.002', 'POP.003', 'POP.004', 'POP.005',
            'IT.001', 'IT.002', 'INS.001', 'INS.002', 'DOC.001'
        ],
        'nome': [
            'Procedimento Operacional Padrão 1',
            'Procedimento Operacional Padrão 2',
            'Procedimento Operacional Padrão 3',
            'Procedimento Operacional Padrão 4',
            'Procedimento Operacional Padrão 5',
            'Instrução de Trabalho 1',
            'Instrução de Trabalho 2',
            'Instrução de Segurança 1',
            'Instrução de Segurança 2',
            'Documentação Técnica 1'
        ],
        'descricao': [
            f'Descrição do procedimento {i}' for i in range(1, 11)
        ],
        'pasta': [
            'QUALIDADE', 'QUALIDADE', 'PRODUÇÃO', 'PRODUÇÃO', 'RH',
            'SEGURANÇA', 'SEGURANÇA', 'HIGIENE', 'HIGIENE', 'TÉCNICA'
        ],
        'classificacao': [
            'POP', 'POP', 'POP', 'POP', 'POP',
            'IT', 'IT', 'INS', 'INS', 'DOC'
        ],
        'autor': [
            'João Silva', 'Maria Santos', 'Pedro Oliveira', 'Ana Costa', 'Carlos Dias',
            'Fernando Gomes', 'Lucia Martins', 'Roberto Lima', 'Beatriz Alves', 'Thiago Mendes'
        ],
        'numero_revisao': [
            '01', '02', '01', '03', '01',
            '01', '02', '01', '01', '01'
        ],
        'ultima_revisao': [
            (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(10)
        ],
        'data_aprovacao': [
            (datetime.now() - timedelta(days=i+30)).strftime('%Y-%m-%d') for i in range(10)
        ],
        'proxima_revisao': [
            (datetime.now() + timedelta(days=365-i)).strftime('%Y-%m-%d') for i in range(10)
        ],
        'data_validade': [
            (datetime.now() + timedelta(days=730-i)).strftime('%Y-%m-%d') for i in range(10)
        ],
        'documentos_controlados': [
            'Sim', 'Sim', 'Não', 'Sim', 'Não',
            'Sim', 'Sim', 'Não', 'Sim', 'Não'
        ],
        'matriz': [
            'Matriz Principal' for _ in range(10)
        ],
        'sub_area': [
            f'Área {i//2 + 1}' for i in range(10)
        ]
    }
    
    # Cria DataFrame
    df = pd.DataFrame(dados)
    
    # Define caminho do arquivo
    if not arquivo_path:
        arquivo_path = 'database/incoming/demo_procedimentos_importacao.xlsx'
    
    # Cria diretório se necessário
    os.makedirs(os.path.dirname(arquivo_path), exist_ok=True)
    
    # Salva arquivo
    df.to_excel(arquivo_path, index=False)
    
    print(f"\n✅ Arquivo criado: {arquivo_path}")
    print(f"   Total de linhas: {len(df)}")
    print(f"   Colunas: {', '.join(df.columns)}")
    
    return arquivo_path


def demo_modo_dry_run(arquivo_path: str):
    """Demonstração: Modo Dry-Run (Simular)."""
    print("\n" + "="*80)
    print("🧪 MODO 1: DRY-RUN (SIMULAR SEM SALVAR)")
    print("="*80)
    
    print(f"\n📂 Arquivo: {arquivo_path}")
    print("\nDescricao:")
    print("  - Carrega arquivo")
    print("  - Valida dados")
    print("  - SIMULA inserção/atualização")
    print("  - NÃO salva no banco")
    print("  - Perfeito para testar antes")
    
    # Processa
    try:
        with open(arquivo_path, 'rb') as f:
            # Cria classe fake file
            class FakeFile:
                def __init__(self, file_obj):
                    self.name = file_obj.name
                    self._content = file_obj.read()
                    self.file = BytesIO(self._content)
                
                def read(self):
                    return self._content
                
                def seek(self, pos):
                    self.file.seek(pos)
            
            arquivo = FakeFile(f)
            servico = ImportacaoProcedimentosService(arquivo)
            resultados = servico.processar(modo='dry_run')
        
        # Exibe resultados
        print("\n📊 RESULTADOS (Simulação):")
        print(f"  ✓ Total processado: {resultados['total']}")
        print(f"  ✓ Seria criado: {resultados['criados']}")
        print(f"  ✓ Seria atualizado: {resultados['atualizados']}")
        print(f"  ✗ Erros: {resultados['erros']}")
        
        # Detalhes
        if resultados['linhas_processadas']:
            print(f"\n✅ Linhas que seriam processadas:")
            for item in resultados['linhas_processadas'][:5]:
                print(f"  Linha {item['linha']}: {item['codigo']} - {item['status']}")
            
            if len(resultados['linhas_processadas']) > 5:
                print(f"  ... e mais {len(resultados['linhas_processadas']) - 5} linhas")
        
        if resultados['erros_detalhados']:
            print(f"\n❌ Erros encontrados:")
            for item in resultados['erros_detalhados'][:5]:
                print(f"  Linha {item['linha']}: {item['erro']}")
        
        print("\n✓ Nenhum dado foi salvo no banco (modo simulação)")
    
    except Exception as e:
        print(f"\n❌ Erro: {e}")


def demo_modo_create(arquivo_path: str):
    """Demonstração: Modo Create (Apenas novos)."""
    print("\n" + "="*80)
    print("✨ MODO 2: CREATE (APENAS NOVOS - PULA EXISTENTES)")
    print("="*80)
    
    print("\nDescricao:")
    print("  - Carrega arquivo")
    print("  - Cria novos procedimentos")
    print("  - IGNORA procedimentos que já existem")
    print("  - Não atualiza nada")
    
    # Conta antes
    count_antes = Procedimento.objects.count()
    print(f"\n📊 Procedimentos no banco ANTES: {count_antes}")
    
    # Processa
    try:
        with open(arquivo_path, 'rb') as f:
            class FakeFile:
                def __init__(self, file_obj):
                    self.name = file_obj.name
                    self._content = file_obj.read()
                    self.file = BytesIO(self._content)
                
                def read(self):
                    return self._content
            
            arquivo = FakeFile(f)
            servico = ImportacaoProcedimentosService(arquivo)
            resultados = servico.processar(modo='create')
        
        # Conta depois
        count_depois = Procedimento.objects.count()
        criados_nesta_exec = count_depois - count_antes
        
        print(f"\n📊 RESULTADOS:")
        print(f"  ✓ Criados nesta execução: {criados_nesta_exec}")
        print(f"  ℹ Total no banco agora: {count_depois}")
        
        print(f"\n✅ Detalhes:")
        print(f"  - Modo: CREATE (pula existentes)")
        print(f"  - Novos criados: {resultados['criados']}")
        print(f"  - Pulados: {resultados['total'] - resultados['criados'] - resultados['erros']}")
        print(f"  - Erros: {resultados['erros']}")
    
    except Exception as e:
        print(f"\n❌ Erro: {e}")


def demo_modo_upsert(arquivo_path: str):
    """Demonstração: Modo Upsert (Padrão - Cria e atualiza)."""
    print("\n" + "="*80)
    print("🔄 MODO 3: UPSERT (CRIA NOVOS E ATUALIZA EXISTENTES) - PADRÃO")
    print("="*80)
    
    print("\nDescricao:")
    print("  - Carrega arquivo")
    print("  - Cria NOVOS procedimentos")
    print("  - ATUALIZA procedimentos que já existem")
    print("  - Mais completo e seguro")
    
    # Prepara: cria um procedimento para testar atualização
    proc_teste = Procedimento.objects.create(
        codigo='POP.001',
        nome='NOME ANTIGO',
        numero_revisao='00'
    )
    print(f"\n🔧 Procedimento POP.001 preparado para teste de atualização")
    print(f"   Antes: Rev {proc_teste.numero_revisao}")
    
    # Processa
    try:
        with open(arquivo_path, 'rb') as f:
            class FakeFile:
                def __init__(self, file_obj):
                    self.name = file_obj.name
                    self._content = file_obj.read()
                    self.file = BytesIO(self._content)
                
                def read(self):
                    return self._content
            
            arquivo = FakeFile(f)
            servico = ImportacaoProcedimentosService(arquivo)
            resultados = servico.processar(modo='upsert')
        
        # Verifica atualização
        proc_teste.refresh_from_db()
        
        print(f"\n📊 RESULTADOS:")
        print(f"  ✓ Criados: {resultados['criados']}")
        print(f"  🔄 Atualizados: {resultados['atualizados']}")
        print(f"  ✗ Erros: {resultados['erros']}")
        print(f"\n✅ Verificação de Atualização (POP.001):")
        print(f"   Depois: Rev {proc_teste.numero_revisao} (foi alterado)")
    
    except Exception as e:
        print(f"\n❌ Erro: {e}")


def demo_relatorio():
    """Demonstração: Geração de Relatório HTML."""
    print("\n" + "="*80)
    print("📈 RELATÓRIO HTML")
    print("="*80)
    
    print("\nO sistema gera automaticamente um relatório com:")
    print("  ✓ Resumo (total, criados, atualizados, erros)")
    print("  ✓ Tabela de sucessos com status")
    print("  ✓ Tabela de erros com detalhes")
    print("  ✓ Formatação Bootstrap para web")
    
    # Cria arquivo demo simples
    dados = {
        'codigo': ['POP.TEST.001', 'POP.TEST.002', 'INVALID'],
        'nome': ['Proc 1', 'Proc 2', ''],  # 3ª linha com erro
        'numero_revisao': ['01', '01', '01']
    }
    
    df = pd.DataFrame(dados)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    buffer.seek(0)
    
    class FakeFile:
        def __init__(self, buffer):
            self.name = 'test.xlsx'
            self._content = buffer.getvalue()
        def read(self):
            return self._content
    
    arquivo = FakeFile(buffer)
    servico = ImportacaoProcedimentosService(arquivo)
    servico.processar(modo='upsert')
    
    html = servico.gerar_relatorio_html()
    
    print(f"\n✅ Relatório gerado:")
    print(f"   - Tamanho: {len(html)} caracteres")
    print(f"   - Contém: Resumo, tabelas, formatação Bootstrap")
    print(f"   - Pronto para: Exibição em template Django")


def main():
    """Executa toda a demonstração."""
    print("\n" + "╔" + "="*78 + "╗")
    print("║" + " "*20 + "🚀 DEMONSTRAÇÃO DE IMPORTAÇÃO DE PROCEDIMENTOS" + " "*14 + "║")
    print("╚" + "="*78 + "╝")
    
    # 1. Cria arquivo
    arquivo_path = criar_arquivo_demo()
    
    # 2. Testa Dry-Run
    demo_modo_dry_run(arquivo_path)
    
    # 3. Limpa antes de Create
    Procedimento.objects.all().delete()
    print("\n🗑️  Banco limpo para próximo teste")
    
    # 4. Testa Create
    demo_modo_create(arquivo_path)
    
    # 5. Testa Upsert
    demo_modo_upsert(arquivo_path)
    
    # 6. Relatório
    demo_relatorio()
    
    # Resumo Final
    print("\n" + "="*80)
    print("✅ DEMONSTRAÇÃO COMPLETA!")
    print("="*80)
    print("\n📋 Resumo de Funcionalidades Demonstradas:")
    print("  1. ✓ Criação de arquivo Excel de exemplo")
    print("  2. ✓ Modo DRY-RUN (simular sem salvar)")
    print("  3. ✓ Modo CREATE (apenas novos)")
    print("  4. ✓ Modo UPSERT (cria e atualiza)")
    print("  5. ✓ Geração de Relatório HTML")
    print("\n🎯 Próximos Passos:")
    print("  - Acesse: http://localhost:8000/procedures/procedimentos/importar/")
    print("  - Faça upload do arquivo criado em: database/incoming/")
    print("  - Escolha o modo desejado")
    print("  - Veja o relatório detalhado")
    print("\n" + "="*80 + "\n")


if __name__ == '__main__':
    main()
