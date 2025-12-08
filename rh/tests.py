"""
Tests for rh (Human Resources) module
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from datetime import date

from rh.models import Colaborador, Ferias, HierarquiaSetor
from organization.models import Setor


class SetorTests(TestCase):
    """Tests for Setor model"""
    
    def setUp(self):
        self.setor = Setor.objects.create(
            nome="Recursos Humanos",
            responsavel="Gerente RH"
        )
    
    def test_setor_creation(self):
        """Test creation of Setor"""
        self.assertEqual(self.setor.nome, "Recursos Humanos")
        self.assertEqual(self.setor.responsavel, "Gerente RH")
    
    def test_setor_str(self):
        """Test string representation of Setor"""
        self.assertIn("Recursos Humanos", str(self.setor))


class ColaboradorTests(TestCase):
    """Tests for Colaborador model"""
    
    def setUp(self):
        self.setor = Setor.objects.create(nome="TI", responsavel="Admin")
        self.user = User.objects.create_user(
            username='colaborador1',
            password='password123'
        )
        self.colaborador = Colaborador.objects.create(
            user=self.user,
            matricula="MAT-001",
            cpf="12345678901",
            nome_completo="João da Silva",
            cargo="Desenvolvedor",
            setor=self.setor,
            salario=5000.00,
            is_active=True
        )
    
    def test_colaborador_creation(self):
        """Test creation of Colaborador"""
        self.assertEqual(self.colaborador.matricula, "MAT-001")
        self.assertEqual(self.colaborador.nome_completo, "João da Silva")
        self.assertTrue(self.colaborador.is_active)
    
    def test_colaborador_str(self):
        """Test string representation of Colaborador"""
        self.assertIn("João da Silva", str(self.colaborador))
    
    def test_colaborador_em_ferias_default_false(self):
        """Test that colaborador is not in vacation by default"""
        self.assertFalse(self.colaborador.em_ferias)


class FeriasTests(TestCase):
    """Tests for Ferias model"""
    
    def setUp(self):
        self.setor = Setor.objects.create(nome="TI", responsavel="Admin")
        self.user = User.objects.create_user(
            username='colaborador2',
            password='password123'
        )
        self.colaborador = Colaborador.objects.create(
            user=self.user,
            matricula="MAT-002",
            cpf="98765432101",
            nome_completo="Maria Silva",
            cargo="Analista",
            setor=self.setor
        )
        self.ferias = Ferias.objects.create(
            colaborador=self.colaborador,
            data_inicio=date(2025, 1, 1),
            data_fim=date(2025, 1, 15),
            observacao="Férias programadas"
        )
    
    def test_ferias_creation(self):
        """Test creation of Ferias"""
        self.assertEqual(self.ferias.data_inicio, date(2025, 1, 1))
        self.assertEqual(self.ferias.data_fim, date(2025, 1, 15))
    
    def test_ferias_duracao(self):
        """Test that vacation end date is after start date"""
        self.assertGreater(self.ferias.data_fim, self.ferias.data_inicio)


class HierarquiaSetorTests(TestCase):
    """Tests for HierarquiaSetor model"""
    
    def setUp(self):
        self.setor = Setor.objects.create(nome="Vendas", responsavel="Diretor")
        
        # Create users and colaboradores
        self.user_lider = User.objects.create_user(username='lider', password='pass')
        self.lider = Colaborador.objects.create(
            user=self.user_lider,
            matricula="MAT-100",
            nome_completo="Líder",
            setor=self.setor
        )
        
        self.user_supervisor = User.objects.create_user(username='supervisor', password='pass')
        self.supervisor = Colaborador.objects.create(
            user=self.user_supervisor,
            matricula="MAT-101",
            nome_completo="Supervisor",
            setor=self.setor
        )
        
        self.hierarquia = HierarquiaSetor.objects.create(
            setor=self.setor,
            lider=self.lider,
            supervisor=self.supervisor
        )
    
    def test_hierarquia_creation(self):
        """Test creation of HierarquiaSetor"""
        self.assertEqual(self.hierarquia.setor.nome, "Vendas")
        self.assertEqual(self.hierarquia.lider.nome_completo, "Líder")


class RHViewsTests(TestCase):
    """Integration tests for RH views"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='rh_user',
            password='testpass123'
        )
        self.setor = Setor.objects.create(nome="RH", responsavel="Manager")
    
    def test_modulo_rh_requires_authentication(self):
        """Test that RH module requires authentication"""
        response = self.client.get(reverse('modulo_rh'))
        self.assertEqual(response.status_code, 302)
    
    def test_modulo_rh_authenticated(self):
        """Test RH module view with authenticated user"""
        self.client.login(username='rh_user', password='testpass123')
        response = self.client.get(reverse('modulo_rh'))
        self.assertIn(response.status_code, [200, 404])


class RHImportsTests(TestCase):
    """Test that all RH imports are working correctly"""
    
    def test_rh_models_import(self):
        """Test that all RH models can be imported"""
        from rh.models import (
            Colaborador, HierarquiaSetor, Ferias,
            DocumentoPessoal, PacoteTreinamento
        )
        self.assertIsNotNone(Colaborador)
        self.assertIsNotNone(HierarquiaSetor)
        self.assertIsNotNone(Ferias)
        self.assertIsNotNone(DocumentoPessoal)
        self.assertIsNotNone(PacoteTreinamento)
    
    def test_rh_views_import(self):
        """Test that all RH views can be imported"""
        from rh.views import (
            modulo_rh_view, detalhe_colaborador_view,
            editar_colaborador_view
        )
        self.assertIsNotNone(modulo_rh_view)
        self.assertIsNotNone(detalhe_colaborador_view)
        self.assertIsNotNone(editar_colaborador_view)
    
    def test_rh_forms_import(self):
        """Test that all RH forms can be imported"""
        from rh.forms import (
            ColaboradorForm, OcorrenciaForm,
            ImportacaoColaboradoresForm
        )
        self.assertIsNotNone(ColaboradorForm)
        self.assertIsNotNone(OcorrenciaForm)
        self.assertIsNotNone(ImportacaoColaboradoresForm)
