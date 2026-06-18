"""
Tests for rh (Human Resources) module
"""
from django.test import TestCase, Client, RequestFactory
from django.contrib.auth.models import User
from django.urls import reverse
from datetime import date

from rh.models import Colaborador, Ferias
from organization.models import HierarquiaSetor, Setor


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
            user_django=self.user,
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
            user_django=self.user,
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
            dias_solicitados=14,
            descricao="Férias programadas"
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
            user_django=self.user_lider,
            matricula="MAT-100",
            nome_completo="Líder",
            setor=self.setor
        )
        
        self.user_supervisor = User.objects.create_user(username='supervisor', password='pass')
        self.supervisor = Colaborador.objects.create(
            user_django=self.user_supervisor,
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
        self.factory = RequestFactory()
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


class RHAtualizarLiderancasEmMassaTests(TestCase):
    """Tests for bulk leadership updates by sector and shift."""

    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='rh_bulk_user',
            password='testpass123'
        )
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save(update_fields=['is_staff', 'is_superuser'])
        self.setor = Setor.objects.create(nome='Metrologia', responsavel='Gestor Metrologia')

        self.novo_lider = Colaborador.objects.create(
            matricula='LID-001',
            nome_completo='Novo Lider',
            grupo='ADMINISTRATIVO',
            setor=self.setor,
            turno='ADM',
            is_active=True
        )

        self.colab_em_ferias = Colaborador.objects.create(
            matricula='COL-001',
            nome_completo='Colaborador Ferias',
            grupo='PRODUCAO',
            setor=self.setor,
            turno='ADM',
            em_ferias=True,
            is_active=True
        )
        self.colab_afastado = Colaborador.objects.create(
            matricula='COL-002',
            nome_completo='Colaborador Afastado',
            grupo='PRODUCAO',
            setor=self.setor,
            turno='ADM',
            afastado=True,
            is_active=True
        )
        self.colab_desligado = Colaborador.objects.create(
            matricula='COL-003',
            nome_completo='Colaborador Desligado',
            grupo='PRODUCAO',
            setor=self.setor,
            turno='ADM',
            is_active=False
        )

        self.colab_outro_turno = Colaborador.objects.create(
            matricula='COL-004',
            nome_completo='Colaborador Outro Turno',
            grupo='PRODUCAO',
            setor=self.setor,
            turno='1T',
            is_active=True
        )

    def test_atualiza_tambem_colaboradores_ferias_afastado_desligado(self):
        """Bulk update must include vacation, leave and inactive collaborators."""
        from rh.views.views import atualizar_liderancas_em_massa

        request = self.factory.post(
            '/rh/atualizar-liderancas/',
            {
                'setor_id': self.setor.id,
                'turno': 'ADM',
                'lider_id': self.novo_lider.id,
                'confirmar': 'sim',
            }
        )
        request.user = self.user

        response = atualizar_liderancas_em_massa(request)
        self.assertEqual(response.status_code, 200)

        self.colab_em_ferias.refresh_from_db()
        self.colab_afastado.refresh_from_db()
        self.colab_desligado.refresh_from_db()
        self.colab_outro_turno.refresh_from_db()

        self.assertEqual(self.colab_em_ferias.lider_id, self.novo_lider.id)
        self.assertEqual(self.colab_afastado.lider_id, self.novo_lider.id)
        self.assertEqual(self.colab_desligado.lider_id, self.novo_lider.id)
        self.assertIsNone(self.colab_outro_turno.lider_id)


class RHImportsTests(TestCase):
    """Test that all RH imports are working correctly"""
    
    def test_rh_models_import(self):
        """Test that all RH models can be imported"""
        from procedures.models import PacoteTreinamento
        from rh.models import Colaborador, DocumentoPessoal, Ferias

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


class PlanejamentoHoraExtraTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        from rh.models import Colaborador
        from organization.models import Setor
        self.client = Client()
        self.setor = Setor.objects.create(nome="Produção", responsavel="Admin")
        
        # Usuário Líder
        self.user_lider = User.objects.create_user(username='lider_user', password='password123')
        self.lider = Colaborador.objects.create(
            user_django=self.user_lider,
            matricula="MAT-LID",
            nome_completo="Líder Teste",
            setor=self.setor,
            is_active=True
        )
        
        # Colaborador subordinado (liderado pelo Líder)
        self.colab_subordinado = Colaborador.objects.create(
            matricula="MAT-SUB",
            nome_completo="Subordinado Teste",
            setor=self.setor,
            lider=self.lider,
            is_active=True
        )
        
        # Colaborador independente
        self.colab_independente = Colaborador.objects.create(
            matricula="MAT-IND",
            nome_completo="Independente Teste",
            setor=self.setor,
            is_active=True
        )
        
        # Superuser
        self.superuser = User.objects.create_superuser(username='super_user', password='password123')
        
    def test_form_validation_valid_formats(self):
        """Test form clean validation with valid time formats"""
        from datetime import timedelta
        from rh.forms import PlanejamentoHoraExtraForm
        # Formato hh:mm:ss
        form = PlanejamentoHoraExtraForm(data={
            'data': '2026-06-18',
            'motivo': 'Inventário',
            'horas_extras_str': '02:30:00',
            'colaboradores': [self.colab_subordinado.id]
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['horas_extras_str'], timedelta(hours=2, minutes=30))
        
        # Formato hh:mm
        form2 = PlanejamentoHoraExtraForm(data={
            'data': '2026-06-18',
            'motivo': 'Inventário',
            'horas_extras_str': '01:45',
            'colaboradores': [self.colab_subordinado.id]
        })
        self.assertTrue(form2.is_valid(), form2.errors)
        self.assertEqual(form2.cleaned_data['horas_extras_str'], timedelta(hours=1, minutes=45))

    def test_form_validation_invalid_formats(self):
        """Test form clean validation with invalid time formats"""
        from rh.forms import PlanejamentoHoraExtraForm
        form = PlanejamentoHoraExtraForm(data={
            'data': '2026-06-18',
            'motivo': 'Inventário',
            'horas_extras_str': 'invalid-time',
            'colaboradores': [self.colab_subordinado.id]
        })
        self.assertFalse(form.is_valid())
        self.assertIn('horas_extras_str', form.errors)

    def test_form_colaboradores_queryset_filtering(self):
        """Test that form filters accessible collaborators depending on user"""
        from rh.forms import PlanejamentoHoraExtraForm
        # User lider can only see self and subordinado
        form_lider = PlanejamentoHoraExtraForm(usuario_logado=self.user_lider)
        colabs_queryset = form_lider.fields['colaboradores'].queryset
        self.assertIn(self.colab_subordinado, colabs_queryset)
        self.assertIn(self.lider, colabs_queryset)
        self.assertNotIn(self.colab_independente, colabs_queryset)
        
        # Superuser can see all
        form_super = PlanejamentoHoraExtraForm(usuario_logado=self.superuser)
        colabs_super_queryset = form_super.fields['colaboradores'].queryset
        self.assertIn(self.colab_subordinado, colabs_super_queryset)
        self.assertIn(self.colab_independente, colabs_super_queryset)

    def test_crud_views(self):
        """Test listing, creating, updating and deleting planning via views"""
        from datetime import timedelta
        from rh.models import PlanejamentoHoraExtra
        self.client.login(username='super_user', password='password123')
        
        # 1. Create planning
        create_url = reverse('rh:planejamento_hora_extra_create')
        post_data = {
            'data': '2026-06-18',
            'motivo': 'Fechamento Mensal',
            'horas_extras_str': '02:00:00',
            'colaboradores': [self.colab_subordinado.id, self.colab_independente.id]
        }
        response = self.client.post(create_url, post_data)
        self.assertEqual(response.status_code, 302) # Redireciona para listagem
        
        # Verify created model in DB
        planning = PlanejamentoHoraExtra.objects.get(motivo='Fechamento Mensal')
        self.assertEqual(planning.horas_extras, timedelta(hours=2))
        self.assertEqual(planning.colaboradores.count(), 2)
        
        # 2. List planning
        list_url = reverse('rh:planejamento_hora_extra_list')
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Fechamento Mensal')
        self.assertContains(response, '02:00:00')
        
        # 3. Update planning
        edit_url = reverse('rh:planejamento_hora_extra_edit', args=[planning.id])
        update_data = {
            'data': '2026-06-19',
            'motivo': 'Fechamento Mensal Ajustado',
            'horas_extras_str': '03:15:00',
            'colaboradores': [self.colab_subordinado.id]
        }
        response = self.client.post(edit_url, update_data)
        self.assertEqual(response.status_code, 302)
        
        planning.refresh_from_db()
        self.assertEqual(planning.motivo, 'Fechamento Mensal Ajustado')
        self.assertEqual(planning.data, date(2026, 6, 19))
        self.assertEqual(planning.horas_extras, timedelta(hours=3, minutes=15))
        self.assertEqual(planning.colaboradores.count(), 1)
        
        # 4. Delete planning
        delete_url = reverse('rh:planejamento_hora_extra_delete', args=[planning.id])
        response = self.client.post(delete_url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlanejamentoHoraExtra.objects.filter(id=planning.id).exists())

