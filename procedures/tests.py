# -*- coding: utf-8 -*-
"""
Tests para o módulo Procedures
"""

from django.test import TestCase
from .models import Procedimento, Fornecedor, ProcessoCotacao


class ProcedimentoModelTest(TestCase):
    """Testes do modelo Procedimento."""
    
    def setUp(self):
        self.proc = Procedimento.objects.create(
            codigo='POP.001',
            nome='Procedimento Teste',
            numero_revisao='01'
        )
    
    def test_procedimento_creation(self):
        self.assertEqual(self.proc.codigo, 'POP.001')
        self.assertTrue(str(self.proc).startswith('POP.001'))


class FornecedorModelTest(TestCase):
    """Testes do modelo Fornecedor."""
    
    def setUp(self):
        self.fornecedor = Fornecedor.objects.create(
            nome_fantasia='Empresa Teste',
            cnpj='12345678000190',
            contato='João Silva',
            email='joao@empresa.com',
            telefone='11999999999',
            escopo_servico='Serviço Teste'
        )
    
    def test_fornecedor_creation(self):
        self.assertEqual(self.fornecedor.nome_fantasia, 'Empresa Teste')
        self.assertEqual(self.fornecedor.status, 'EM_ANALISE')


class ProcessoCotacaoModelTest(TestCase):
    """Testes do modelo ProcessoCotacao."""
    
    def setUp(self):
        self.cotacao = ProcessoCotacao.objects.create(
            titulo='Cotação Teste',
            prazo_limite='2025-12-31'
        )
    
    def test_cotacao_creation(self):
        self.assertEqual(self.cotacao.titulo, 'Cotação Teste')
        self.assertEqual(self.cotacao.status, 'ABERTO')
