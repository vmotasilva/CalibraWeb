# -*- coding: utf-8 -*-
"""
Testes para exportação de dados - Fase 5
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from datetime import date, timedelta
from io import BytesIO

from metrologia.models import (
    Instrumento,
    CategoriaInstrumento,
    HistoricoCalibracao,
)
from organization.models import Setor
from metrologia.exportadores import ExportadorInstrumentos, ExportadorEstatisticas


class ExportadorInstrumentosTest(TestCase):
    """Testes para exportador de instrumentos"""
    
    @classmethod
    def setUpTestData(cls):
        """Setup test data"""
        cls.setor = Setor.objects.create(nome='Laboratório')
        cls.categoria = CategoriaInstrumento.objects.create(
            nome='Paquímetro',
            descricao='Medidor'
        )
        
        today = date.today()
        
        cls.instrumento1 = Instrumento.objects.create(
            tag='INSTR-001',
            descricao='Paquímetro Digital',
            categoria=cls.categoria,
            setor=cls.setor,
            ativo=True,
            data_proxima_calibracao=today + timedelta(days=60)
        )
        
        cls.instrumento2 = Instrumento.objects.create(
            tag='INSTR-002',
            descricao='Termômetro',
            categoria=cls.categoria,
            setor=cls.setor,
            ativo=True,
            data_proxima_calibracao=today - timedelta(days=10)
        )
    
    def test_exportador_inicializacao(self):
        """Test exporter initialization"""
        queryset = Instrumento.objects.all()
        exportador = ExportadorInstrumentos(queryset)
        self.assertEqual(exportador.queryset.count(), 2)
    
    def test_exportador_excel_criacao(self):
        """Test Excel export creation"""
        queryset = Instrumento.objects.all()
        exportador = ExportadorInstrumentos(queryset)
        
        try:
            response = exportador.exportar_excel()
            self.assertEqual(response.status_code, 200)
            self.assertIn('attachment', response['Content-Disposition'])
            self.assertIn('.xlsx', response['Content-Disposition'])
        except ImportError:
            self.skipTest("openpyxl não está instalado")
    
    def test_exportador_csv_criacao(self):
        """Test CSV export creation"""
        queryset = Instrumento.objects.all()
        exportador = ExportadorInstrumentos(queryset)
        
        response = exportador.exportar_csv()
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('.csv', response['Content-Disposition'])
    
    def test_exportador_pdf_criacao(self):
        """Test PDF export creation"""
        queryset = Instrumento.objects.all()
        exportador = ExportadorInstrumentos(queryset)
        
        try:
            response = exportador.exportar_pdf()
            self.assertEqual(response.status_code, 200)
            self.assertIn('attachment', response['Content-Disposition'])
            self.assertIn('.pdf', response['Content-Disposition'])
        except ImportError:
            self.skipTest("reportlab não está instalado")
    
    def test_status_text_vencido(self):
        """Test status text for expired instrument"""
        exportador = ExportadorInstrumentos(Instrumento.objects.none())
        status = exportador._get_status_text(self.instrumento2)
        self.assertEqual(status, "Vencido")
    
    def test_status_text_vigente(self):
        """Test status text for valid instrument"""
        exportador = ExportadorInstrumentos(Instrumento.objects.none())
        status = exportador._get_status_text(self.instrumento1)
        self.assertEqual(status, "Vigente")


class ExportadorEstatisticasTest(TestCase):
    """Testes para exportador de estatísticas"""
    
    @classmethod
    def setUpTestData(cls):
        """Setup test data"""
        cls.setor = Setor.objects.create(nome='Laboratório')
        cls.categoria = CategoriaInstrumento.objects.create(
            nome='Paquímetro',
            descricao='Medidor'
        )
        
        today = date.today()
        
        cls.instrumento = Instrumento.objects.create(
            tag='INSTR-001',
            descricao='Test',
            categoria=cls.categoria,
            setor=cls.setor,
            ativo=True,
            data_proxima_calibracao=today + timedelta(days=60)
        )
        
        HistoricoCalibracao.objects.create(
            instrumento=cls.instrumento,
            data_calibracao=today,
            resultado='APROVADO_SEM_CORRECAO'
        )
    
    def test_exportador_inicializacao(self):
        """Test exporter initialization"""
        data = {
            'total_instrumentos': 1,
            'total_vencidos': 0,
            'vencer_30_dias': 0,
            'total_vigentes': 1,
            'total_historicos': 1,
            'aprovados': 1,
            'com_correcao': 0,
            'reprovados': 0,
            'por_categoria': [],
            'por_setor': [],
            'percentage_vencidos': 0.0,
            'percentage_aprovados': 100.0,
        }
        
        exportador = ExportadorEstatisticas(data)
        self.assertEqual(exportador.data['total_instrumentos'], 1)
    
    def test_exportador_excel_criacao(self):
        """Test Excel export creation"""
        data = {
            'total_instrumentos': 1,
            'total_vencidos': 0,
            'vencer_30_dias': 0,
            'total_vigentes': 1,
            'total_historicos': 1,
            'aprovados': 1,
            'com_correcao': 0,
            'reprovados': 0,
            'por_categoria': [],
            'por_setor': [],
            'percentage_vencidos': 0.0,
            'percentage_aprovados': 100.0,
        }
        
        exportador = ExportadorEstatisticas(data)
        
        try:
            response = exportador.exportar_excel()
            self.assertEqual(response.status_code, 200)
            self.assertIn('attachment', response['Content-Disposition'])
        except ImportError:
            self.skipTest("openpyxl não está instalado")
    
    def test_exportador_pdf_criacao(self):
        """Test PDF export creation"""
        data = {
            'total_instrumentos': 1,
            'total_vencidos': 0,
            'vencer_30_dias': 0,
            'total_vigentes': 1,
            'total_historicos': 1,
            'aprovados': 1,
            'com_correcao': 0,
            'reprovados': 0,
            'por_categoria': [],
            'por_setor': [],
            'percentage_vencidos': 0.0,
            'percentage_aprovados': 100.0,
        }
        
        exportador = ExportadorEstatisticas(data)
        
        try:
            response = exportador.exportar_pdf()
            self.assertEqual(response.status_code, 200)
            self.assertIn('attachment', response['Content-Disposition'])
        except ImportError:
            self.skipTest("reportlab não está instalado")


class ExportViewsTest(TestCase):
    """Testes para views de exportação"""
    
    @classmethod
    def setUpTestData(cls):
        """Setup test data"""
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        cls.setor = Setor.objects.create(nome='Laboratório')
        cls.categoria = CategoriaInstrumento.objects.create(
            nome='Paquímetro',
            descricao='Medidor'
        )
        
        today = date.today()
        
        cls.instrumento = Instrumento.objects.create(
            tag='INSTR-001',
            descricao='Test Instrument',
            categoria=cls.categoria,
            setor=cls.setor,
            ativo=True,
            data_proxima_calibracao=today + timedelta(days=60)
        )
    
    def setUp(self):
        """Setup test client"""
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def test_exportar_instrumentos_excel(self):
        """Test export instruments as Excel"""
        response = self.client.get(
            reverse('exportar_instrumentos'),
            {'formato': 'excel'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('spreadsheet', response['Content-Type'])
    
    def test_exportar_instrumentos_csv(self):
        """Test export instruments as CSV"""
        response = self.client.get(
            reverse('exportar_instrumentos'),
            {'formato': 'csv'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('csv', response['Content-Type'])
    
    def test_exportar_instrumentos_com_filtro(self):
        """Test export with filters"""
        response = self.client.get(
            reverse('exportar_instrumentos'),
            {'formato': 'csv', 'status': 'vigentes'}
        )
        self.assertEqual(response.status_code, 200)
    
    def test_exportar_estatisticas_excel(self):
        """Test export statistics as Excel"""
        response = self.client.get(
            reverse('exportar_estatisticas'),
            {'formato': 'excel'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('spreadsheet', response['Content-Type'])
    
    def test_relatorio_vencidos(self):
        """Test expired instruments report"""
        response = self.client.get(
            reverse('relatorio_vencidos'),
            {'formato': 'csv'}
        )
        self.assertEqual(response.status_code, 200)
    
    def test_exportar_requer_login(self):
        """Test that export requires login"""
        self.client.logout()
        response = self.client.get(reverse('exportar_instrumentos'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
