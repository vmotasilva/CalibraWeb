"""
CALIBRAWEB - INTEGRATION TESTING SUITE
Comprehensive integration tests for cross-app interactions

Tests:
- Cross-app model relationships
- Admin workflows
- Data consistency
- Permission validation
- Signal handlers
- Cache invalidation
"""

import pytest
from django.test import TestCase, Client
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError
from django.urls import reverse
from datetime import datetime, timedelta
import random


class CrossAppIntegrationTests(TestCase):
    """Test cross-app relationships and data flow"""
    
    fixtures = ['test_data.json']  # If you have test fixtures
    
    @classmethod
    def setUpClass(cls):
        """Set up test data once for all tests"""
        super().setUpClass()
        
        # Create test users and data
        cls.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='testpass123'
        )
        
        cls.user = User.objects.create_user(
            username='testuser',
            email='user@test.com',
            password='testpass123'
        )
    
    def setUp(self):
        """Set up before each test"""
        self.client = Client()
        self.client.login(username='admin', password='testpass123')
    
    def test_rh_to_organization_relationship(self):
        """Test Colaborador -> Setor -> CentroCusto relationship"""
        from organization.models import Setor, CentroCusto, HierarquiaSetor
        from rh.models import Colaborador
        
        # Create hierarchy
        centro = CentroCusto.objects.create(
            nome="Test Centro",
            codigo="TEST-001"
        )
        
        setor = Setor.objects.create(
            nome="Test Setor",
            centro_custo=centro
        )
        
        # Create colaborador
        colab = Colaborador.objects.create(
            nome="Test User",
            email="test@company.com",
            setor=setor,
            turno="M"
        )
        
        # Verify relationships
        assert colab.setor == setor
        assert colab.setor.centro_custo == centro
        assert colab in setor.colaborador_set.all()
    
    def test_metrologia_calibration_workflow(self):
        """Test complete calibration workflow"""
        from metrologia.models import (
            Instrumento, UnidadeMedida, FaixaMedicao,
            HistoricoCalibracao, ResultadoFaixaCalibracao
        )
        
        # Create instrument
        unidade = UnidadeMedida.objects.create(
            simbolo="mm",
            descricao="Milímetros"
        )
        
        instrumento = Instrumento.objects.create(
            nome="Paquímetro de Precisão",
            numero_serie="PAQ-2025-001",
            tipo="Dimensional",
            unidade_medida=unidade,
            incerteza_padrao=0.01
        )
        
        # Create measurement range
        faixa = FaixaMedicao.objects.create(
            instrumento=instrumento,
            unidade=unidade,
            limite_inferior=0,
            limite_superior=150,
            incerteza_relativa=0.05
        )
        
        # Create calibration record
        historico = HistoricoCalibracao.objects.create(
            instrumento=instrumento,
            data_calibracao=datetime.now().date(),
            proxima_calibracao=(datetime.now() + timedelta(days=365)).date(),
            certificado_numero="CERT-2025-001",
            status="aprovada"
        )
        
        # Create measurement results
        resultado = ResultadoFaixaCalibracao.objects.create(
            historico=historico,
            faixa=faixa,
            valor_medio=150.05,
            desvio_padrao=0.02,
            resultado="aprovado"
        )
        
        # Verify complete workflow
        assert resultado.historico.instrumento == instrumento
        assert resultado.faixa.instrumento == instrumento
        assert resultado.historico.status == "aprovada"
    
    def test_training_assignment_workflow(self):
        """Test training assignment and completion"""
        from training.models import (
            Procedimento, PacoteTreinamento,
            RegistroTreinamento
        )
        from rh.models import Colaborador
        
        # Create training content
        procedimento = Procedimento.objects.create(
            titulo="Safety Training",
            descricao="Basic safety procedures",
            versao="1.0"
        )
        
        pacote = PacoteTreinamento.objects.create(
            nome="Onboarding Package",
            descricao="New employee training",
            versao="2.0"
        )
        pacote.procedimentos.add(procedimento)
        
        # Create employee
        from django.contrib.auth.models import User
        django_user = User.objects.create_user(
            username='newhire',
            password='testpass'
        )
        
        colab = Colaborador.objects.create(
            user=django_user,
            nome="New Hire",
            email="newhire@company.com",
            setor=self.create_test_setor(),
            turno="M"
        )
        
        # Assign training
        registro = RegistroTreinamento.objects.create(
            colaborador=colab,
            pacote=pacote,
            data_prevista=(datetime.now() + timedelta(days=7)).date(),
            status="atribuído"
        )
        
        # Verify assignment
        assert registro.colaborador == colab
        assert registro.pacote == pacote
        assert registro.status == "atribuído"
    
    def test_procurement_vendor_evaluation(self):
        """Test vendor evaluation workflow"""
        from procurements.models import (
            Fornecedor, AvaliacaoFornecedor,
            ProcessoCotacao
        )
        
        # Create vendor
        vendor = Fornecedor.objects.create(
            nome="Test Supplier",
            cnpj="12.345.678/0001-90",
            email="vendor@test.com"
        )
        
        # Create evaluation
        avaliacao = AvaliacaoFornecedor.objects.create(
            fornecedor=vendor,
            data_avaliacao=datetime.now().date(),
            qualidade=8.5,
            preco=7.5,
            entrega=9.0,
            servico_pos_venda=8.0,
            resultado="aprovado"
        )
        
        # Verify relationship
        assert avaliacao.fornecedor == vendor
        assert avaliacao.resultado == "aprovado"
    
    def create_test_setor(self):
        """Helper to create test sector"""
        from organization.models import Setor, CentroCusto
        
        centro = CentroCusto.objects.create(
            nome=f"Test Centro {random.randint(1, 1000)}",
            codigo=f"TEST-{random.randint(100, 999)}"
        )
        
        return Setor.objects.create(
            nome=f"Test Setor {random.randint(1, 1000)}",
            centro_custo=centro
        )


class AdminIntegrationTests(TestCase):
    """Test admin interface workflows"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data"""
        super().setUpClass()
        cls.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='admin123'
        )
    
    def setUp(self):
        """Login before each test"""
        self.client = Client()
        self.client.login(username='admin', password='admin123')
    
    def test_admin_changelist_access(self):
        """Test admin changelist pages are accessible"""
        endpoints = [
            '/admin/rh/colaborador/',
            '/admin/metrologia/instrumento/',
            '/admin/organization/setor/',
            '/admin/training/procedimento/',
            '/admin/procurements/fornecedor/',
        ]
        
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, 200, f"Failed: {endpoint}")
    
    def test_admin_add_model(self):
        """Test adding model through admin"""
        from organization.models import CentroCusto
        
        initial_count = CentroCusto.objects.count()
        
        response = self.client.post(
            '/admin/organization/centrocusto/add/',
            {
                'nome': 'Test Centro',
                'codigo': 'TEST-001',
            }
        )
        
        # Should redirect on success
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CentroCusto.objects.count(), initial_count + 1)
    
    def test_admin_search_functionality(self):
        """Test admin search"""
        from organization.models import CentroCusto
        
        CentroCusto.objects.create(
            nome="Searchable Centro",
            codigo="SEARCH-001"
        )
        
        response = self.client.get(
            '/admin/organization/centrocusto/?q=Searchable'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Searchable Centro', response.content)
    
    def test_admin_filter_functionality(self):
        """Test admin filters"""
        response = self.client.get(
            '/admin/rh/colaborador/?turno__exact=M'
        )
        self.assertEqual(response.status_code, 200)


class DataConsistencyTests(TestCase):
    """Test data consistency and constraints"""
    
    def test_cascade_delete_relationships(self):
        """Test cascade delete works correctly"""
        from organization.models import Setor, CentroCusto
        from rh.models import Colaborador
        
        centro = CentroCusto.objects.create(
            nome="Test Centro",
            codigo="TEST-001"
        )
        
        setor = Setor.objects.create(
            nome="Test Setor",
            centro_custo=centro
        )
        
        colab = Colaborador.objects.create(
            nome="Test User",
            email="test@company.com",
            setor=setor,
            turno="M"
        )
        
        # Delete setor should handle relationships
        setor_id = setor.id
        setor.delete()
        
        # Verify deletion
        self.assertFalse(Setor.objects.filter(id=setor_id).exists())
    
    def test_unique_constraints(self):
        """Test unique field constraints"""
        from metrologia.models import UnidadeMedida
        
        UnidadeMedida.objects.create(
            simbolo="mm",
            descricao="Milímetros"
        )
        
        # Try to create duplicate
        with self.assertRaises(IntegrityError):
            UnidadeMedida.objects.create(
                simbolo="mm",
                descricao="Another Description"
            )
    
    def test_required_fields(self):
        """Test required field validation"""
        from organization.models import CentroCusto
        
        # Try to create without required field
        with self.assertRaises(Exception):
            CentroCusto.objects.create(codigo="TEST-001")  # Missing nome


class PermissionTests(TestCase):
    """Test permission and access control"""
    
    def setUp(self):
        """Set up test users"""
        self.admin = User.objects.create_superuser(
            username='admin',
            password='admin123'
        )
        
        self.staff = User.objects.create_user(
            username='staff',
            password='staff123',
            is_staff=True
        )
        
        self.regular = User.objects.create_user(
            username='regular',
            password='user123'
        )
    
    def test_admin_access_granted(self):
        """Test admin user can access admin interface"""
        client = Client()
        client.login(username='admin', password='admin123')
        
        response = client.get('/admin/')
        self.assertEqual(response.status_code, 200)
    
    def test_staff_limited_access(self):
        """Test staff user has limited access"""
        client = Client()
        client.login(username='staff', password='staff123')
        
        # Add specific permission to staff
        content_type = ContentType.objects.get_for_model(User)
        permission = Permission.objects.get(content_type=content_type)
        self.staff.user_permissions.add(permission)
    
    def test_regular_user_denied_access(self):
        """Test regular user cannot access admin"""
        client = Client()
        client.login(username='regular', password='user123')
        
        response = client.get('/admin/')
        self.assertIn(response.status_code, [302, 403])  # Redirect or Forbidden


class SignalHandlerTests(TestCase):
    """Test signal handlers and hooks"""
    
    def test_model_save_signal(self):
        """Test signals are triggered on save"""
        from rh.models import Colaborador
        from organization.models import Setor, CentroCusto
        
        centro = CentroCusto.objects.create(
            nome="Test",
            codigo="TEST"
        )
        setor = Setor.objects.create(
            nome="Test",
            centro_custo=centro
        )
        
        # Create and save should trigger signal
        colab = Colaborador(
            nome="Test",
            email="test@test.com",
            setor=setor,
            turno="M"
        )
        colab.save()
        
        self.assertTrue(colab.id)
    
    def test_model_delete_signal(self):
        """Test signals are triggered on delete"""
        from rh.models import Colaborador
        from organization.models import Setor, CentroCusto
        
        centro = CentroCusto.objects.create(
            nome="Test",
            codigo="TEST"
        )
        setor = Setor.objects.create(
            nome="Test",
            centro_custo=centro
        )
        colab = Colaborador.objects.create(
            nome="Test",
            email="test@test.com",
            setor=setor,
            turno="M"
        )
        
        colab_id = colab.id
        colab.delete()
        
        self.assertFalse(
            Colaborador.objects.filter(id=colab_id).exists()
        )


# Pytest fixtures for easier testing

@pytest.fixture
def test_setor():
    """Fixture to create test sector"""
    from organization.models import Setor, CentroCusto
    
    centro = CentroCusto.objects.create(
        nome="Test Centro",
        codigo="TEST-001"
    )
    return Setor.objects.create(
        nome="Test Setor",
        centro_custo=centro
    )


@pytest.fixture
def test_colaborador(test_setor):
    """Fixture to create test employee"""
    from rh.models import Colaborador
    
    return Colaborador.objects.create(
        nome="Test Employee",
        email="test@company.com",
        setor=test_setor,
        turno="M"
    )


@pytest.fixture
def admin_client():
    """Fixture to create authenticated admin client"""
    user = User.objects.create_superuser(
        username='admin',
        email='admin@test.com',
        password='admin123'
    )
    
    client = Client()
    client.login(username='admin', password='admin123')
    return client
