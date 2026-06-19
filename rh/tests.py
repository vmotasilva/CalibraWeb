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
        
    def test_form_validation_valid_datetimes(self):
        """Test form clean validation with valid datetime-local strings and tipo"""
        from datetime import timedelta
        from rh.forms import PlanejamentoHoraExtraForm
        form = PlanejamentoHoraExtraForm(data={
            'tipo': 'HORA_EXTRA',
            'data_hora_inicio': '2026-06-18T08:00',
            'data_hora_fim': '2026-06-18T10:30',
            'motivo': 'Inventário',
            'colaboradores': [self.colab_subordinado.id]
        })
        self.assertTrue(form.is_valid(), form.errors)
        
        # Test default choices validation and custom planned off type
        form2 = PlanejamentoHoraExtraForm(data={
            'tipo': 'FOLGA',
            'data_hora_inicio': '2026-06-18T08:00',
            'data_hora_fim': '2026-06-18T17:00',
            'motivo': 'Folga Compensatória',
            'colaboradores': [self.colab_subordinado.id]
        })
        self.assertTrue(form2.is_valid(), form2.errors)

    def test_form_validation_invalid_chronology(self):
        """Test form clean validation fails if end is before or equal to start"""
        from rh.forms import PlanejamentoHoraExtraForm
        # End datetime before start datetime
        form = PlanejamentoHoraExtraForm(data={
            'tipo': 'HORA_EXTRA',
            'data_hora_inicio': '2026-06-18T10:00',
            'data_hora_fim': '2026-06-18T08:00',
            'motivo': 'Inventário',
            'colaboradores': [self.colab_subordinado.id]
        })
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)
        self.assertEqual(form.errors['__all__'][0], "A data/hora de fim deve ser posterior à data/hora de início.")

    def test_form_colaboradores_queryset_filtering(self):
        """Test that form filters accessible collaborators depending on user and active/away status"""
        from rh.forms import PlanejamentoHoraExtraForm
        from rh.models import Colaborador
        
        # Create inactive and away collaborators
        colab_inativo = Colaborador.objects.create(
            matricula="MAT-INA",
            nome_completo="Inativo Teste",
            setor=self.setor,
            is_active=False
        )
        colab_afastado = Colaborador.objects.create(
            matricula="MAT-AFA",
            nome_completo="Afastado Teste",
            setor=self.setor,
            is_active=True,
            afastado=True
        )

        # User lider can only see self and subordinado
        form_lider = PlanejamentoHoraExtraForm(usuario_logado=self.user_lider)
        colabs_queryset = form_lider.fields['colaboradores'].queryset
        self.assertIn(self.colab_subordinado, colabs_queryset)
        self.assertIn(self.lider, colabs_queryset)
        self.assertNotIn(self.colab_independente, colabs_queryset)
        self.assertNotIn(colab_inativo, colabs_queryset)
        self.assertNotIn(colab_afastado, colabs_queryset)
        
        # Superuser can see all active and non-away
        form_super = PlanejamentoHoraExtraForm(usuario_logado=self.superuser)
        colabs_super_queryset = form_super.fields['colaboradores'].queryset
        self.assertIn(self.colab_subordinado, colabs_super_queryset)
        self.assertIn(self.colab_independente, colabs_super_queryset)
        self.assertNotIn(colab_inativo, colabs_super_queryset)
        self.assertNotIn(colab_afastado, colabs_super_queryset)

    def test_form_validation_multiple_motivos(self):
        """Test form clean validation with multiple motives selected"""
        from rh.forms import PlanejamentoHoraExtraForm
        from rh.models import MotivoPlanejamento
        m1 = MotivoPlanejamento.objects.create(nome="Temp1", tipo="HORA_EXTRA")
        m2 = MotivoPlanejamento.objects.create(nome="Temp2", tipo="AMBOS")
        form = PlanejamentoHoraExtraForm(data={
            'tipo': 'HORA_EXTRA',
            'data_hora_inicio': '2026-06-18T08:00',
            'data_hora_fim': '2026-06-18T10:30',
            'motivos': [m1.id, m2.id],
            'motivo': 'Descrição livre de justificativa',
            'colaboradores': [self.colab_subordinado.id]
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(len(form.cleaned_data['motivos']), 2)

    def test_weekly_filtering_view(self):
        """Test the list view week filters correctly filter by week"""
        from datetime import date, timedelta, datetime, time
        from django.utils import timezone
        from django.utils.timezone import is_aware, make_aware
        from rh.models import PlanejamentoHoraExtra
        self.client.login(username='super_user', password='password123')
        
        today = date.today()
        # Segunda-feira da semana atual
        monday = today - timedelta(days=today.weekday())
        
        def make_dt(d, h, m):
            dt = datetime.combine(d, time(h, m))
            return make_aware(dt) if is_aware(timezone.now()) else dt

        # Planejamento na semana passada
        p_passada = PlanejamentoHoraExtra.objects.create(
            tipo='HORA_EXTRA',
            data_hora_inicio=make_dt(monday - timedelta(days=3), 8, 0),
            data_hora_fim=make_dt(monday - timedelta(days=3), 10, 0),
            motivo='Semana Passada Reg',
        )
        p_passada.colaboradores.add(self.colab_subordinado)
        p_passada.save()
        
        # Planejamento na semana atual
        p_atual = PlanejamentoHoraExtra.objects.create(
            tipo='HORA_EXTRA',
            data_hora_inicio=make_dt(monday + timedelta(days=1), 8, 0),
            data_hora_fim=make_dt(monday + timedelta(days=1), 10, 0),
            motivo='Esta Semana Reg',
        )
        p_atual.colaboradores.add(self.colab_subordinado)
        p_atual.save()

        # Planejamento na próxima semana
        p_proxima = PlanejamentoHoraExtra.objects.create(
            tipo='FOLGA',
            data_hora_inicio=make_dt(monday + timedelta(days=8), 8, 0),
            data_hora_fim=make_dt(monday + timedelta(days=8), 10, 0),
            motivo='Proxima Semana Reg',
        )
        p_proxima.colaboradores.add(self.colab_subordinado)
        p_proxima.save()
        
        list_url = reverse('rh:planejamento_hora_extra_list')
        
        # Test semana passada
        response = self.client.get(f"{list_url}?semana=passada")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Semana Passada Reg')
        self.assertNotContains(response, 'Esta Semana Reg')
        self.assertNotContains(response, 'Proxima Semana Reg')
        
        # Test esta semana
        response = self.client.get(f"{list_url}?semana=atual")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Semana Passada Reg')
        self.assertContains(response, 'Esta Semana Reg')
        self.assertNotContains(response, 'Proxima Semana Reg')
        
        # Test proxima semana
        response = self.client.get(f"{list_url}?semana=proxima")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Semana Passada Reg')
        self.assertNotContains(response, 'Esta Semana Reg')
        self.assertContains(response, 'Proxima Semana Reg')

    def test_crud_views(self):
        """Test listing, creating, updating and deleting planning via views"""
        from datetime import timedelta, date
        from rh.models import PlanejamentoHoraExtra, MotivoPlanejamento
        self.client.login(username='super_user', password='password123')
        
        # Create a categorized reason
        m_extra = MotivoPlanejamento.objects.create(nome="Manutenção", tipo="HORA_EXTRA")
        
        # 1. Create planning
        create_url = reverse('rh:planejamento_hora_extra_create')
        post_data = {
            'tipo': 'HORA_EXTRA',
            'data_hora_inicio': '2026-06-18T08:00',
            'data_hora_fim': '2026-06-18T10:00',
            'motivos': [m_extra.id],
            'motivo': 'Fechamento Mensal',
            'colaboradores': [self.colab_subordinado.id, self.colab_independente.id]
        }
        response = self.client.post(create_url, post_data)
        self.assertEqual(response.status_code, 302) # Redirects to listing
        
        # Verify created model in DB
        planning = PlanejamentoHoraExtra.objects.get(motivo='Fechamento Mensal')
        self.assertEqual(planning.tipo, 'HORA_EXTRA')
        self.assertEqual(planning.horas_extras, timedelta(hours=2))
        self.assertEqual(planning.data, date(2026, 6, 18))
        self.assertEqual(planning.colaboradores.count(), 2)
        self.assertEqual(planning.motivos.first(), m_extra)
        
        # 2. List planning
        list_url = reverse('rh:planejamento_hora_extra_list')
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Fechamento Mensal')
        self.assertContains(response, '02:00:00')
        self.assertContains(response, 'Manutenção')
        
        # 3. Update planning
        m_folga = MotivoPlanejamento.objects.create(nome="Compensação", tipo="FOLGA")
        edit_url = reverse('rh:planejamento_hora_extra_edit', args=[planning.id])
        update_data = {
            'tipo': 'FOLGA',
            'data_hora_inicio': '2026-06-19T08:00',
            'data_hora_fim': '2026-06-19T11:15',
            'motivos': [m_folga.id],
            'motivo': 'Fechamento Mensal Ajustado',
            'colaboradores': [self.colab_subordinado.id]
        }
        response = self.client.post(edit_url, update_data)
        self.assertEqual(response.status_code, 302)
        
        planning.refresh_from_db()
        self.assertEqual(planning.tipo, 'FOLGA')
        self.assertEqual(planning.motivo, 'Fechamento Mensal Ajustado')
        self.assertEqual(planning.data, date(2026, 6, 19))
        self.assertEqual(planning.horas_extras, timedelta(hours=3, minutes=15))
        self.assertEqual(planning.colaboradores.count(), 1)
        self.assertEqual(planning.motivos.first(), m_folga)
        
        # 4. Delete planning
        delete_url = reverse('rh:planejamento_hora_extra_delete', args=[planning.id])
        response = self.client.post(delete_url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlanejamentoHoraExtra.objects.filter(id=planning.id).exists())


class MotivoPlanejamentoCRUDTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        from rh.models import Colaborador
        from organization.models import Setor
        self.client = Client()
        self.setor = Setor.objects.create(nome="Produção", responsavel="Admin")
        self.superuser = User.objects.create_superuser(username='super_user', password='password123')
        
    def test_motivo_crud_views(self):
        """Test listing, creating, updating and deleting motives via views"""
        self.client.login(username='super_user', password='password123')
        from rh.models import MotivoPlanejamento
        
        # 1. Create Motive
        create_url = reverse('rh:motivo_planejamento_create')
        response = self.client.post(create_url, {
            'nome': 'Treinamento Especial',
            'tipo': 'HORA_EXTRA'
        })
        self.assertEqual(response.status_code, 302)
        
        motivo = MotivoPlanejamento.objects.get(nome='Treinamento Especial')
        self.assertEqual(motivo.tipo, 'HORA_EXTRA')
        
        # 2. List Motives
        list_url = reverse('rh:motivo_planejamento_list')
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Treinamento Especial')
        
        # 3. Update Motive
        edit_url = reverse('rh:motivo_planejamento_edit', args=[motivo.id])
        response = self.client.post(edit_url, {
            'nome': 'Treinamento Especial Atualizado',
            'tipo': 'AMBOS'
        })
        self.assertEqual(response.status_code, 302)
        motivo.refresh_from_db()
        self.assertEqual(motivo.nome, 'Treinamento Especial Atualizado')
        self.assertEqual(motivo.tipo, 'AMBOS')
        
        # 4. Delete Motive
        delete_url = reverse('rh:motivo_planejamento_delete', args=[motivo.id])
        response = self.client.post(delete_url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(MotivoPlanejamento.objects.filter(id=motivo.id).exists())

    def test_api_create_motivo_ajax(self):
        """Test dynamic inline creation of motives via AJAX JSON endpoint"""
        import json
        self.client.login(username='super_user', password='password123')
        from rh.models import MotivoPlanejamento
        
        api_url = reverse('rh:api_create_motivo')
        
        # 1. Successful AJAX creation
        post_data = {
            'nome': 'Hora de Ouro',
            'tipo': 'HORA_EXTRA'
        }
        response = self.client.post(
            api_url, 
            data=json.dumps(post_data), 
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        res_json = response.json()
        self.assertTrue(res_json['success'])
        self.assertEqual(res_json['nome'], 'Hora de Ouro')
        self.assertEqual(res_json['tipo'], 'HORA_EXTRA')
        
        # Verify db record
        self.assertTrue(MotivoPlanejamento.objects.filter(nome='Hora de Ouro').exists())
        
        # 2. Duplicate error case
        response_dup = self.client.post(
            api_url, 
            data=json.dumps(post_data), 
            content_type='application/json'
        )
        self.assertEqual(response_dup.status_code, 400)
        res_dup_json = response_dup.json()
        self.assertFalse(res_dup_json['success'])
        self.assertIn('Já existe um motivo cadastrado com este nome', res_dup_json['error'])


