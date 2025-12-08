"""
Tests for procurements module - Supplier and Procurement Management
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from procurements.models import Fornecedor, AvaliacaoFornecedor


class FornecedorTests(TestCase):
    """Tests for Fornecedor model"""
    
    def setUp(self):
        self.fornecedor = Fornecedor.objects.create(
            nome="Fornecedor XYZ",
            cnpj="12345678000199",
            email="contato@fornecedor.com",
            telefone="1133334444",
            ativo=True
        )
    
    def test_fornecedor_creation(self):
        """Test creation of Fornecedor"""
        self.assertEqual(self.fornecedor.nome, "Fornecedor XYZ")
        self.assertTrue(self.fornecedor.ativo)
    
    def test_fornecedor_str(self):
        """Test string representation of Fornecedor"""
        self.assertIn("Fornecedor XYZ", str(self.fornecedor))
    
    def test_fornecedor_email_valid(self):
        """Test that fornecedor has valid email"""
        self.assertIn("@", self.fornecedor.email)


class AvaliacaoFornecedorTests(TestCase):
    """Tests for AvaliacaoFornecedor model"""
    
    def setUp(self):
        self.fornecedor = Fornecedor.objects.create(
            nome="Supplier ABC",
            cnpj="98765432000111"
        )
        self.avaliacao = AvaliacaoFornecedor.objects.create(
            fornecedor=self.fornecedor,
            data_avaliacao="2025-01-01",
            qualidade=8,
            prazo=9,
            preco=7,
            observacao="Bom fornecedor"
        )
    
    def test_avaliacao_creation(self):
        """Test creation of AvaliacaoFornecedor"""
        self.assertEqual(self.avaliacao.qualidade, 8)
        self.assertEqual(self.avaliacao.fornecedor.nome, "Supplier ABC")
    
    def test_avaliacao_score_range(self):
        """Test that evaluation scores are in valid range"""
        self.assertGreaterEqual(self.avaliacao.qualidade, 0)
        self.assertLessEqual(self.avaliacao.qualidade, 10)


class ProcurementsViewsTests(TestCase):
    """Integration tests for procurements views"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='procurement_user',
            password='testpass123'
        )
    
    def test_nova_solicitacao_requires_authentication(self):
        """Test that nova_solicitacao view requires authentication"""
        response = self.client.get(reverse('nova_solicitacao'))
        self.assertEqual(response.status_code, 302)


class ProcurementsImportsTests(TestCase):
    """Test that all procurements imports are working correctly"""
    
    def test_procurements_models_import(self):
        """Test that procurements models can be imported"""
        from procurements.models import (
            Fornecedor, AvaliacaoFornecedor,
            ProcessoCotacao, Orcamento
        )
        self.assertIsNotNone(Fornecedor)
        self.assertIsNotNone(AvaliacaoFornecedor)
        self.assertIsNotNone(ProcessoCotacao)
        self.assertIsNotNone(Orcamento)
    
    def test_procurements_views_import(self):
        """Test that procurements views can be imported"""
        from procurements.views import nova_solicitacao
        self.assertIsNotNone(nova_solicitacao)
    
    def test_procurements_forms_import(self):
        """Test that procurements forms can be imported"""
        from procurements.forms import (
            SolicitacaoForm, ImportacaoPadroesForm
        )
        self.assertIsNotNone(SolicitacaoForm)
        self.assertIsNotNone(ImportacaoPadroesForm)
