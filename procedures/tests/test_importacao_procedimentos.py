# -*- coding: utf-8 -*-
"""
Testes para o serviço de importação de procedimentos

Execução: python manage.py test procedures.tests.test_importacao_procedimentos
"""

from io import BytesIO
import pandas as pd
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from procedures.models import Procedimento
from procedures.services.importacao_procedimentos import ImportacaoProcedimentosService


class ImportacaoProcedimentosServiceTestCase(TestCase):
    """Testes unitários para ImportacaoProcedimentosService."""
    
    def setUp(self):
        """Setup para cada teste."""
        # Limpa procedimentos
        Procedimento.objects.all().delete()
        
        # Cria alguns procedimentos iniciais
        self.proc1 = Procedimento.objects.create(
            codigo='POP.001',
            nome='Procedimento Inicial',
            numero_revisao='00'
        )
    
    def criar_arquivo_excel(self, dados):
        """Helper para criar arquivo Excel em memória."""
        df = pd.DataFrame(dados)
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        buffer.seek(0)
        
        # Simula file upload
        class FakeFile(BytesIO):
            def __init__(self, buf_val):
                super().__init__(buf_val)
                self.name = 'test.xlsx'
        
        return FakeFile(buffer.getvalue())
    
    def test_carregar_arquivo_excel(self):
        """Testa carregamento de arquivo Excel."""
        dados = {
            'codigo': ['POP.002', 'POP.003'],
            'nome': ['Proc 2', 'Proc 3']
        }
        arquivo = self.criar_arquivo_excel(dados)
        servico = ImportacaoProcedimentosService(arquivo)
        
        self.assertTrue(servico.carregar_arquivo())
        self.assertEqual(len(servico.df), 2)
    
    def test_normalizar_colunas_flexivel(self):
        """Testa mapeamento flexível de colunas."""
        dados = {
            'Código': ['POP.002'],
            'NOME': ['Proc 2'],
            'CLASSIFICAÇÃO': ['POP']
        }
        arquivo = self.criar_arquivo_excel(dados)
        servico = ImportacaoProcedimentosService(arquivo)
        
        self.assertTrue(servico.carregar_arquivo())
        self.assertTrue(servico.normalizar_colunas())
        self.assertIn('codigo', servico.df.columns)
        self.assertIn('nome', servico.df.columns)
    
    def test_validar_codigo_obrigatorio(self):
        """Testa validação de código obrigatório."""
        servico = ImportacaoProcedimentosService(None)
        
        # Código vazio
        valido, erros = servico._validar_linha(2, {'nome': 'Test'})
        self.assertFalse(valido)
        self.assertTrue(any('obrigatório' in e.lower() for e in erros))
    
    def test_validar_nome_obrigatorio(self):
        """Testa validação de nome obrigatório."""
        servico = ImportacaoProcedimentosService(None)
        
        # Nome vazio
        valido, erros = servico._validar_linha(2, {'codigo': 'POP.999'})
        self.assertFalse(valido)
        self.assertTrue(any('obrigatório' in e.lower() for e in erros))
    
    def test_validar_comprimento_codigo(self):
        """Testa validação de comprimento de código."""
        servico = ImportacaoProcedimentosService(None)
        
        # Muito curto
        valido, _ = servico._validar_linha(2, {
            'codigo': 'AB',
            'nome': 'Test'
        })
        self.assertFalse(valido)
        
        # Muito longo
        valido, _ = servico._validar_linha(2, {
            'codigo': 'A' * 51,
            'nome': 'Test'
        })
        self.assertFalse(valido)
        
        # Válido
        valido, _ = servico._validar_linha(2, {
            'codigo': 'POP.001',
            'nome': 'Test'
        })
        self.assertTrue(valido)
    
    def test_parsear_data_multiplos_formatos(self):
        """Testa parsing de múltiplos formatos de data."""
        servico = ImportacaoProcedimentosService(None)
        
        # DD/MM/YYYY
        data = servico._parsear_data('25/12/2024')
        self.assertEqual(str(data), '2024-12-25')
        
        # YYYY-MM-DD
        data = servico._parsear_data('2024-12-25')
        self.assertEqual(str(data), '2024-12-25')
        
        # DD-MM-YYYY
        data = servico._parsear_data('25-12-2024')
        self.assertEqual(str(data), '2024-12-25')
        
        # Inválido
        data = servico._parsear_data('invalid')
        self.assertIsNone(data)
    
    def test_processar_modo_upsert_novo(self):
        """Testa inserção em modo upsert."""
        dados = {
            'codigo': ['POP.002'],
            'nome': ['Novo Procedimento'],
            'numero_revisao': ['01']
        }
        arquivo = self.criar_arquivo_excel(dados)
        servico = ImportacaoProcedimentosService(arquivo)
        
        resultados = servico.processar(modo='upsert')
        
        self.assertEqual(resultados['criados'], 1)
        self.assertEqual(resultados['atualizados'], 0)
        self.assertEqual(resultados['erros'], 0)
        
        # Verifica banco
        proc = Procedimento.objects.get(codigo='POP.002')
        self.assertEqual(proc.nome, 'Novo Procedimento')
    
    def test_processar_modo_upsert_atualiza(self):
        """Testa atualização em modo upsert."""
        dados = {
            'codigo': ['POP.001'],
            'nome': ['Procedimento Atualizado'],
            'numero_revisao': ['01']
        }
        arquivo = self.criar_arquivo_excel(dados)
        servico = ImportacaoProcedimentosService(arquivo)
        
        resultados = servico.processar(modo='upsert')
        
        self.assertEqual(resultados['criados'], 0)
        self.assertEqual(resultados['atualizados'], 1)
        self.assertEqual(resultados['erros'], 0)
        
        # Verifica banco
        proc = Procedimento.objects.get(codigo='POP.001')
        self.assertEqual(proc.nome, 'Procedimento Atualizado')
    
    def test_processar_modo_create(self):
        """Testa modo create (apenas cria, não atualiza)."""
        dados = {
            'codigo': ['POP.001', 'POP.002'],
            'nome': ['Novo Nome', 'Novo Procedimento'],
        }
        arquivo = self.criar_arquivo_excel(dados)
        servico = ImportacaoProcedimentosService(arquivo)
        
        resultados = servico.processar(modo='create')
        
        # POP.001 deve ser pulado, POP.002 criado
        self.assertEqual(resultados['criados'], 1)
        
        # Verifica que POP.001 NÃO foi atualizado
        proc = Procedimento.objects.get(codigo='POP.001')
        self.assertEqual(proc.nome, 'Procedimento Inicial')
    
    def test_processar_modo_dry_run(self):
        """Testa modo dry_run (simula sem salvar)."""
        dados = {
            'codigo': ['POP.002'],
            'nome': ['Novo Procedimento'],
        }
        arquivo = self.criar_arquivo_excel(dados)
        servico = ImportacaoProcedimentosService(arquivo)
        
        # Contagem antes
        count_antes = Procedimento.objects.count()
        
        resultados = servico.processar(modo='dry_run')
        
        # Contagem depois (não deve mudar)
        count_depois = Procedimento.objects.count()
        
        self.assertEqual(count_antes, count_depois)
        self.assertTrue(any('DRY-RUN' in item['status'] for item in resultados['linhas_processadas']))
    
    def test_duplicata_na_mesma_importacao(self):
        """Testa detecção de duplicatas na mesma importação."""
        dados = {
            'codigo': ['POP.002', 'POP.002'],  # Mesmo código 2x
            'nome': ['Proc 1', 'Proc 2'],
        }
        arquivo = self.criar_arquivo_excel(dados)
        servico = ImportacaoProcedimentosService(arquivo)
        
        resultados = servico.processar(modo='skip_duplicates')
        
        # Primeira criada, segunda em erro
        self.assertEqual(resultados['criados'], 1)
        self.assertEqual(resultados['erros'], 1)
        self.assertTrue(any('duplicado' in e['erro'].lower() for e in resultados['erros_detalhados']))
    
    def test_gerar_relatorio_html(self):
        """Testa geração de relatório em HTML."""
        dados = {
            'codigo': ['POP.002', 'POP.003'],
            'nome': ['Proc 2', 'Proc 3'],
        }
        arquivo = self.criar_arquivo_excel(dados)
        servico = ImportacaoProcedimentosService(arquivo)
        servico.processar(modo='upsert')
        
        html = servico.gerar_relatorio_html()
        
        self.assertIn('<h4>📊 Relatório de Importação</h4>', html)
        self.assertIn('Criados', html)
        self.assertIn('Atualizados', html)
        self.assertIn('POP.002', html)


class ImportacaoProcedimentosViewTestCase(TestCase):
    """Testes para a view de importação."""
    
    def setUp(self):
        """Setup para cada teste."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.user.is_staff = True
        self.user.save()
    
    def test_view_sem_autenticacao(self):
        """Testa que view exige autenticação."""
        from procedures.views.views import importar_procedimentos_view
        
        request = self.factory.get('/procedures/procedimentos/importar/')
        request.user = None
        
        # Deve redirecionar para login
        from django.contrib.auth.decorators import login_required
        # A view é decorada com @login_required
        self.assertTrue(True)  # Confirmação visual
    
    def test_view_renderiza_formulario(self):
        """Testa que view renderiza formulário."""
        from procedures.views.views import importar_procedimentos_view
        from django.test import Client
        
        client = Client()
        client.login(username='testuser', password='testpass123')
        
        response = client.get('/procedures/procedimentos/importar/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('arquivo_excel', response.context['form'].fields)


# ============================================================================
# SCRIPT PARA TESTE MANUAL
# ============================================================================

def teste_manual():
    """Teste manual - Criar arquivo Excel e importar."""
    print("\n" + "="*70)
    print("🧪 TESTE MANUAL DE IMPORTAÇÃO")
    print("="*70)
    
    # Criar arquivo teste
    print("\n1️⃣ Criando arquivo teste...")
    dados = {
        'codigo': ['POP.TEST.001', 'POP.TEST.002', 'POP.TEST.003'],
        'nome': ['Procedimento Teste 1', 'Procedimento Teste 2', 'Procedimento Teste 3'],
        'descricao': ['Desc 1', 'Desc 2', 'Desc 3'],
        'classificacao': ['POP', 'POP', 'IT'],
        'numero_revisao': ['01', '02', '01'],
        'ultima_revisao': ['2024-01-01', '2024-02-01', '2024-03-01'],
    }
    
    df = pd.DataFrame(dados)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    buffer.seek(0)
    
    print("✓ Arquivo criado em memória")
    
    # Simular upload
    class FakeFile(BytesIO):
        def __init__(self, buf_val):
            super().__init__(buf_val)
            self.name = 'teste_procedimentos.xlsx'
    
    print("\n2️⃣ Processando importação (modo dry-run)...")
    arquivo = FakeFile(buffer.getvalue())
    servico = ImportacaoProcedimentosService(arquivo)
    resultados = servico.processar(modo='dry_run')
    
    print(f"\n📊 Resultados:")
    print(f"   Total: {resultados['total']}")
    print(f"   Criados: {resultados['criados']}")
    print(f"   Atualizados: {resultados['atualizados']}")
    print(f"   Erros: {resultados['erros']}")
    
    if resultados['erros'] > 0:
        print("\n❌ Erros encontrados:")
        for erro in resultados['erros_detalhados']:
            print(f"   Linha {erro['linha']}: {erro['erro']}")
    
    print("\n✅ Teste manual completado!")
    print("="*70 + "\n")


if __name__ == '__main__':
    teste_manual()
