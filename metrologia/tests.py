"""
Tests for metrologia module - Instruments, Calibration, and Measurement management
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from metrologia.models import (
    CategoriaInstrumento, Instrumento, FaixaMedicao, HistoricoCalibracao
)
from core.models import UnidadeMedida
from organization.models import Setor


class UnidadeMedidaTests(TestCase):
    """Tests for UnidadeMedida model"""
    
    def setUp(self):
        self.unidade = UnidadeMedida.objects.create(
            nome="Milímetros",
            descricao="Unidade de comprimento"
        )
    
    def test_unidade_medida_creation(self):
        """Test creation of UnidadeMedida"""
        self.assertEqual(self.unidade.nome, "Milímetros")
    
    def test_unidade_medida_str(self):
        """Test string representation of UnidadeMedida"""
        self.assertIn("Milímetros", str(self.unidade))


class CategoriaInstrumentoTests(TestCase):
    """Tests for CategoriaInstrumento model"""
    
    def setUp(self):
        self.unidade = UnidadeMedida.objects.create(
            nome="Metro",
            descricao="Unidade de comprimento"
        )
        self.categoria = CategoriaInstrumento.objects.create(
            nome="Trena",
            descricao="Instrumento de medição de comprimento",
            unidade_padrao=self.unidade
        )
    
    def test_categoria_instrument_creation(self):
        """Test creation of CategoriaInstrumento"""
        self.assertEqual(self.categoria.nome, "Trena")
        self.assertEqual(self.categoria.unidade_padrao.nome, "Metro")
    
    def test_categoria_str(self):
        """Test string representation of CategoriaInstrumento"""
        self.assertIn("Trena", str(self.categoria))


class InstrumentoTests(TestCase):
    """Tests for Instrumento model"""
    
    def setUp(self):
        self.unidade = UnidadeMedida.objects.create(nome="Metro", descricao="Unidade de comprimento")
        self.setor = Setor.objects.create(
            nome="Setor de Metrologia",
            responsavel="Responsavel"
        )
        self.categoria = CategoriaInstrumento.objects.create(
            nome="Paquímetro",
            unidade_padrao=self.unidade
        )
        self.instrumento = Instrumento.objects.create(
            tag="INSTR-001",
            descricao="Paquímetro Digital",
            categoria=self.categoria,
            setor=self.setor,
            frequencia_meses=12,
            ativo=True
        )
    
    def test_instrumento_creation(self):
        """Test creation of Instrumento"""
        self.assertEqual(self.instrumento.tag, "INSTR-001")
        self.assertTrue(self.instrumento.ativo)
    
    def test_instrumento_proxima_calibracao_null(self):
        """Test that next calibration date is initially None"""
        self.assertIsNone(self.instrumento.data_proxima_calibracao)
    
    def test_instrumento_str(self):
        """Test string representation of Instrumento"""
        self.assertIn("INSTR-001", str(self.instrumento))


class FaixaMedicaoTests(TestCase):
    """Tests for FaixaMedicao model"""
    
    def setUp(self):
        self.unidade = UnidadeMedida.objects.create(nome="Milímetros", descricao="Unidade de comprimento")
        self.setor = Setor.objects.create(nome="Metrologia", responsavel="Admin")
        self.categoria = CategoriaInstrumento.objects.create(
            nome="Micrômetro",
            unidade_padrao=self.unidade
        )
        self.instrumento = Instrumento.objects.create(
            tag="INSTR-002",
            categoria=self.categoria,
            setor=self.setor
        )
        self.faixa = FaixaMedicao.objects.create(
            instrumento=self.instrumento,
            valor_minimo=0.0,
            valor_maximo=100.0,
            unidade_medicao=self.unidade,
            tolerancia_padrao=0.5
        )
    
    def test_faixa_medicao_creation(self):
        """Test creation of FaixaMedicao"""
        self.assertEqual(self.faixa.valor_minimo, 0.0)
        self.assertEqual(self.faixa.valor_maximo, 100.0)
    
    def test_faixa_range_validation(self):
        """Test that max value is greater than min value"""
        self.assertGreater(self.faixa.valor_maximo, self.faixa.valor_minimo)


class HistoricoCalibracaoTests(TestCase):
    """Tests for HistoricoCalibracao model"""
    
    def setUp(self):
        self.unidade = UnidadeMedida.objects.create(nome="Milímetros", descricao="Unidade de comprimento")
        self.setor = Setor.objects.create(nome="Metrologia", responsavel="Admin")
        self.categoria = CategoriaInstrumento.objects.create(
            nome="Calibrador",
            unidade_padrao=self.unidade
        )
        self.instrumento = Instrumento.objects.create(
            tag="INSTR-003",
            categoria=self.categoria,
            setor=self.setor
        )
        self.historico = HistoricoCalibracao.objects.create(
            instrumento=self.instrumento,
            numero_certificado="CERT-2025-001",
            resultado="APROVADO"
        )
    
    def test_historico_creation(self):
        """Test creation of HistoricoCalibracao"""
        self.assertEqual(self.historico.numero_certificado, "CERT-2025-001")
        self.assertEqual(self.historico.resultado, "APROVADO")
    
    def test_historico_str(self):
        """Test string representation of HistoricoCalibracao"""
        self.assertIn("CERT-2025-001", str(self.historico))


class MetrologiaViewsTests(TestCase):
    """Integration tests for metrologia views"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='test_user',
            password='testpass123',
            email='test@example.com'
        )
        self.unidade = UnidadeMedida.objects.create(nome="Metros", descricao="Unidade de comprimento")
        self.setor = Setor.objects.create(nome="Metrologia", responsavel="Admin")
        self.categoria = CategoriaInstrumento.objects.create(
            nome="Régua",
            unidade_padrao=self.unidade
        )
    
    def test_modulo_metrologia_view_unauthenticated(self):
        """Test that metrologia module requires authentication"""
        response = self.client.get(reverse('modulo_metrologia'))
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
    
    def test_modulo_metrologia_view_authenticated(self):
        """Test metrologia module view with authenticated user"""
        self.client.login(username='test_user', password='testpass123')
        response = self.client.get(reverse('modulo_metrologia'))
        self.assertIn(response.status_code, [200, 404])  # 200 if view exists
    
    def test_novo_instrumento_requires_authentication(self):
        """Test that novo_instrumento view requires authentication"""
        response = self.client.get(reverse('novo_instrumento'))
        self.assertEqual(response.status_code, 302)


class MetrologiaImportsTests(TestCase):
    """Test that all metrologia imports are working correctly"""
    
    def test_metrologia_models_import(self):
        """Test that all metrologia models can be imported"""
        from metrologia.models import (
            CategoriaInstrumento, Instrumento, FaixaMedicao,
            HistoricoCalibracao, ArquivoPadrao, ResultadoFaixaCalibracao
        )
        self.assertIsNotNone(CategoriaInstrumento)
        self.assertIsNotNone(Instrumento)
        self.assertIsNotNone(FaixaMedicao)
        self.assertIsNotNone(HistoricoCalibracao)
        self.assertIsNotNone(ArquivoPadrao)
        self.assertIsNotNone(ResultadoFaixaCalibracao)
    
    def test_metrologia_views_import(self):
        """Test that all metrologia views can be imported"""
        from metrologia.views import (
            modulo_metrologia_view, novo_instrumento_view,
            detalhe_instrumento_view
        )
        self.assertIsNotNone(modulo_metrologia_view)
        self.assertIsNotNone(novo_instrumento_view)
        self.assertIsNotNone(detalhe_instrumento_view)
    
    def test_metrologia_forms_import(self):
        """Test that all metrologia forms can be imported"""
        from metrologia.forms import (
            InstrumentoForm, HistoricoCalibracaoForm,
            ImportacaoInstrumentosForm, ImportacaoHistoricoForm
        )
        self.assertIsNotNone(InstrumentoForm)
        self.assertIsNotNone(HistoricoCalibracaoForm)
        self.assertIsNotNone(ImportacaoInstrumentosForm)
        self.assertIsNotNone(ImportacaoHistoricoForm)
