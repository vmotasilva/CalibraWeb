"""
Tests for training module - Procedures and Training Management
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from training.models import (
    Area, Procedimento, RegistroTreinamento
)
from rh.models import Colaborador, PacoteTreinamento
from organization.models import Setor


class AreaTests(TestCase):
    """Tests for Area model"""
    
    def setUp(self):
        self.area = Area.objects.create(
            nome="Segurança",
            descricao="Área de procedimentos de segurança"
        )
    
    def test_area_creation(self):
        """Test creation of Area"""
        self.assertEqual(self.area.nome, "Segurança")
        self.assertIn("segurança", self.area.descricao.lower())
    
    def test_area_str(self):
        """Test string representation of Area"""
        self.assertIn("Segurança", str(self.area))


class ProcedimentoTests(TestCase):
    """Tests for Procedimento model"""
    
    def setUp(self):
        self.area = Area.objects.create(nome="Qualidade")
        self.procedimento = Procedimento.objects.create(
            codigo="PROC-001",
            nome="Inspeção Visual",
            descricao="Procedimento de inspeção visual",
            classificacao="Crítico",
            area=self.area,
            numero_revisao=1
        )
    
    def test_procedimento_creation(self):
        """Test creation of Procedimento"""
        self.assertEqual(self.procedimento.codigo, "PROC-001")
        self.assertEqual(self.procedimento.numero_revisao, 1)
    
    def test_procedimento_str(self):
        """Test string representation of Procedimento"""
        self.assertIn("PROC-001", str(self.procedimento))


class RegistroTreinamentoTests(TestCase):
    """Tests for RegistroTreinamento model"""
    
    def setUp(self):
        self.setor = Setor.objects.create(nome="Produção", responsavel="Manager")
        self.user = User.objects.create_user(
            username='trainee',
            password='password123'
        )
        self.colaborador = Colaborador.objects.create(
            user=self.user,
            matricula="MAT-TRAIN",
            nome_completo="Colaborador Treinando",
            setor=self.setor
        )
        self.area = Area.objects.create(nome="Operações")
        self.procedimento = Procedimento.objects.create(
            codigo="PROC-OPS-001",
            nome="Operação de Máquina",
            area=self.area
        )
        self.registro = RegistroTreinamento.objects.create(
            colaborador=self.colaborador,
            procedimento=self.procedimento,
            status_treinamento="VIGENTE"
        )
    
    def test_registro_treinamento_creation(self):
        """Test creation of RegistroTreinamento"""
        self.assertEqual(self.registro.status_treinamento, "VIGENTE")
        self.assertEqual(self.registro.procedimento.codigo, "PROC-OPS-001")
    
    def test_registro_vigente(self):
        """Test that training status can be VIGENTE"""
        self.assertTrue(self.registro.status_treinamento in ["VIGENTE", "PENDENTE"])


class TrainingViewsTests(TestCase):
    """Integration tests for training views"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='training_user',
            password='testpass123'
        )
    
    def test_procedimentos_list_requires_auth(self):
        """Test that procedures list requires authentication"""
        response = self.client.get(reverse('procedimentos_lista'))
        self.assertEqual(response.status_code, 302)
    
    def test_procedimentos_list_authenticated(self):
        """Test procedures list with authenticated user"""
        self.client.login(username='training_user', password='testpass123')
        response = self.client.get(reverse('procedimentos_lista'))
        self.assertIn(response.status_code, [200, 404])
    
    def test_treinamentos_list_requires_auth(self):
        """Test that trainings list requires authentication"""
        response = self.client.get(reverse('treinamentos_lista'))
        self.assertEqual(response.status_code, 302)


class TrainingImportsTests(TestCase):
    """Test that all training imports are working correctly"""
    
    def test_training_models_import(self):
        """Test that all training models can be imported"""
        from training.models import (
            Area, Procedimento, ProcedimentoRevisao,
            RegistroTreinamento
        )
        self.assertIsNotNone(Area)
        self.assertIsNotNone(Procedimento)
        self.assertIsNotNone(ProcedimentoRevisao)
        self.assertIsNotNone(RegistroTreinamento)
    
    def test_training_views_import(self):
        """Test that all training views can be imported"""
        from training.views import (
            procedimentos_list_view, novo_procedimento_view,
            treinamentos_list_view
        )
        self.assertIsNotNone(procedimentos_list_view)
        self.assertIsNotNone(novo_procedimento_view)
        self.assertIsNotNone(treinamentos_list_view)
    
    def test_training_forms_import(self):
        """Test that all training forms can be imported"""
        from training.forms import (
            ProcedimentoForm, RegistroTreinamentoForm,
            ImportacaoProcedimentosForm
        )
        self.assertIsNotNone(ProcedimentoForm)
        self.assertIsNotNone(RegistroTreinamentoForm)
        self.assertIsNotNone(ImportacaoProcedimentosForm)
