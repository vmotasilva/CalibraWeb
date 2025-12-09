# -*- coding: utf-8 -*-
"""
Tests for new views: listar_instrumentos_view and estatisticas_calibracao_view
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from datetime import date, timedelta

from metrologia.models import (
    Instrumento, 
    CategoriaInstrumento, 
    HistoricoCalibracao,
    FaixaMedicao,
)
from organization.models import Setor


class ListarInstrumentosViewTest(TestCase):
    """Test cases for instrument listing view with filters"""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data once for all test methods"""
        # Create user
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Create test data
        cls.setor = Setor.objects.create(nome='Laboratório')
        cls.categoria = CategoriaInstrumento.objects.create(
            nome='Paquímetro',
            descricao='Medidor de dimensões'
        )
        
        today = date.today()
        
        # Create test instruments
        cls.instrument_vigente = Instrumento.objects.create(
            tag='INSTR-001',
            descricao='Paquímetro Digital',
            categoria=cls.categoria,
            setor=cls.setor,
            ativo=True,
            data_proxima_calibracao=today + timedelta(days=60)
        )
        
        cls.instrument_vencido = Instrumento.objects.create(
            tag='INSTR-002',
            descricao='Termômetro Analógico',
            categoria=cls.categoria,
            setor=cls.setor,
            ativo=True,
            data_proxima_calibracao=today - timedelta(days=10)
        )
        
        cls.instrument_avencer = Instrumento.objects.create(
            tag='INSTR-003',
            descricao='Micrômetro',
            categoria=cls.categoria,
            setor=cls.setor,
            ativo=True,
            data_proxima_calibracao=today + timedelta(days=15)
        )
        
        cls.instrument_inativo = Instrumento.objects.create(
            tag='INSTR-004',
            descricao='Instrumento Desativado',
            categoria=cls.categoria,
            setor=cls.setor,
            ativo=False,
            data_proxima_calibracao=today + timedelta(days=30)
        )
    
    def setUp(self):
        """Set up test client and login"""
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def test_list_view_page_loads(self):
        """Test that listing page loads successfully"""
        response = self.client.get(reverse('listar_instrumentos'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'metrologia/instrumentos_lista.html')
    
    def test_list_view_displays_all_instruments(self):
        """Test that all instruments are displayed in listing"""
        response = self.client.get(reverse('listar_instrumentos'))
        self.assertEqual(len(response.context['instrumentos']), 4)
    
    def test_filter_by_status_vigentes(self):
        """Test filtering instruments by vigentes status"""
        response = self.client.get(
            reverse('listar_instrumentos'),
            {'status': 'vigentes'}
        )
        self.assertEqual(len(response.context['instrumentos']), 2)
        tags = [i.tag for i in response.context['instrumentos']]
        self.assertIn('INSTR-001', tags)
        self.assertIn('INSTR-003', tags)
    
    def test_filter_by_status_vencidos(self):
        """Test filtering instruments by vencidos status"""
        response = self.client.get(
            reverse('listar_instrumentos'),
            {'status': 'vencidos'}
        )
        self.assertEqual(len(response.context['instrumentos']), 1)
        self.assertEqual(response.context['instrumentos'][0].tag, 'INSTR-002')
    
    def test_filter_by_status_avencer(self):
        """Test filtering instruments by a vencer status"""
        response = self.client.get(
            reverse('listar_instrumentos'),
            {'status': 'avencer'}
        )
        self.assertEqual(len(response.context['instrumentos']), 1)
        self.assertEqual(response.context['instrumentos'][0].tag, 'INSTR-003')
    
    def test_filter_by_ativo(self):
        """Test filtering by active status"""
        response = self.client.get(
            reverse('listar_instrumentos'),
            {'ativo': 'ativos'}
        )
        self.assertEqual(len(response.context['instrumentos']), 3)
        
        response = self.client.get(
            reverse('listar_instrumentos'),
            {'ativo': 'inativos'}
        )
        self.assertEqual(len(response.context['instrumentos']), 1)
    
    def test_filter_by_categoria(self):
        """Test filtering by category"""
        response = self.client.get(
            reverse('listar_instrumentos'),
            {'categoria': self.categoria.id}
        )
        self.assertEqual(len(response.context['instrumentos']), 4)
    
    def test_search_by_tag(self):
        """Test search functionality by tag"""
        response = self.client.get(
            reverse('listar_instrumentos'),
            {'q': 'INSTR-001'}
        )
        self.assertEqual(len(response.context['instrumentos']), 1)
        self.assertEqual(response.context['instrumentos'][0].tag, 'INSTR-001')
    
    def test_search_by_description(self):
        """Test search functionality by description"""
        response = self.client.get(
            reverse('listar_instrumentos'),
            {'q': 'Paquímetro'}
        )
        self.assertEqual(len(response.context['instrumentos']), 1)
        self.assertEqual(response.context['instrumentos'][0].tag, 'INSTR-001')
    
    def test_pagination(self):
        """Test pagination functionality"""
        response = self.client.get(reverse('listar_instrumentos'))
        self.assertIn('page_obj', response.context)
        self.assertEqual(response.context['paginator'].per_page, 20)
    
    def test_requires_login(self):
        """Test that view requires login"""
        self.client.logout()
        response = self.client.get(reverse('listar_instrumentos'))
        self.assertEqual(response.status_code, 302)  # Redirect to login


class EstatisticasCalibracaoViewTest(TestCase):
    """Test cases for calibration statistics view"""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data for statistics"""
        # Create user
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Create test data
        cls.setor = Setor.objects.create(nome='Laboratório')
        cls.categoria = CategoriaInstrumento.objects.create(
            nome='Paquímetro',
            descricao='Medidor'
        )
        
        today = date.today()
        
        # Create instruments
        cls.instr1 = Instrumento.objects.create(
            tag='INSTR-001',
            descricao='Instrument 1',
            categoria=cls.categoria,
            setor=cls.setor,
            ativo=True,
            data_proxima_calibracao=today + timedelta(days=60)
        )
        
        cls.instr2 = Instrumento.objects.create(
            tag='INSTR-002',
            descricao='Instrument 2',
            categoria=cls.categoria,
            setor=cls.setor,
            ativo=True,
            data_proxima_calibracao=today - timedelta(days=10)
        )
        
        # Create calibration history
        HistoricoCalibracao.objects.create(
            instrumento=cls.instr1,
            data_calibracao=today,
            resultado='APROVADO_SEM_CORRECAO'
        )
        
        HistoricoCalibracao.objects.create(
            instrumento=cls.instr2,
            data_calibracao=today,
            resultado='APROVADO_COM_CORRECAO'
        )
    
    def setUp(self):
        """Set up test client and login"""
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def test_statistics_page_loads(self):
        """Test that statistics page loads successfully"""
        response = self.client.get(reverse('estatisticas_calibracao'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'metrologia/estatisticas_calibracao.html')
    
    def test_statistics_context_data(self):
        """Test that statistics context contains required data"""
        response = self.client.get(reverse('estatisticas_calibracao'))
        context = response.context
        
        self.assertIn('total_instrumentos', context)
        self.assertIn('total_vencidos', context)
        self.assertIn('vencer_30_dias', context)
        self.assertIn('total_vigentes', context)
        self.assertIn('total_historicos', context)
        self.assertIn('aprovados', context)
        self.assertIn('com_correcao', context)
        self.assertIn('reprovados', context)
        self.assertIn('por_categoria', context)
        self.assertIn('por_setor', context)
    
    def test_statistics_calculations(self):
        """Test that statistics are calculated correctly"""
        response = self.client.get(reverse('estatisticas_calibracao'))
        context = response.context
        
        self.assertEqual(context['total_instrumentos'], 2)
        self.assertEqual(context['total_vencidos'], 1)
        self.assertEqual(context['total_historicos'], 2)
        self.assertEqual(context['aprovados'], 1)
        self.assertEqual(context['com_correcao'], 1)
    
    def test_requires_login(self):
        """Test that view requires login"""
        self.client.logout()
        response = self.client.get(reverse('estatisticas_calibracao'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
