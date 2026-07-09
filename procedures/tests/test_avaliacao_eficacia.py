# -*- coding: utf-8 -*-
from datetime import date, timedelta
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from procedures.models import RegistroTreinamento, Procedimento, ColaboradorPerfil, PerfilTreinamento, GrupoTreinamento, SubGrupoTreinamento, MatrizProcedimento
from rh.models import Colaborador
from organization.models import Setor

User = get_user_model()

class AvaliacaoEficaciaTestCase(TestCase):
    def setUp(self):
        # Create user
        self.user = User.objects.create_superuser(username='admin', email='admin@test.com', password='password')
        self.client.login(username='admin', password='password')

        # Create Sector
        self.setor = Setor.objects.create(nome="Produção")

        # Create Collaborators
        self.lider = Colaborador.objects.create(nome_completo="Lider da Producao", matricula="001", setor=self.setor, is_active=True)
        self.colab1 = Colaborador.objects.create(nome_completo="Colaborador Teste 1", matricula="002", setor=self.setor, lider=self.lider, is_active=True)
        self.colab2 = Colaborador.objects.create(nome_completo="Colaborador Teste 2", matricula="003", setor=self.setor, lider=self.lider, is_active=True)

        # Create matrices
        self.mat1 = MatrizProcedimento.objects.create(nome="Matriz Qualidade", ativo=True)
        self.mat2 = MatrizProcedimento.objects.create(nome="Matriz Produção", ativo=True)

        # Create critical procedures
        self.proc1 = Procedimento.objects.create(codigo="PSQ.001", nome="Procedimento Crítico 1", criticidade="CRITICO", matriz="Matriz Qualidade")
        self.proc2 = Procedimento.objects.create(codigo="PSQ.002", nome="Procedimento Crítico 2", criticidade="CRITICO", matriz="Matriz Produção")

        # Create Profile
        self.perfil = PerfilTreinamento.objects.create(nome="Operador", descricao="Perfil de Operador")
        self.grupo = GrupoTreinamento.objects.create(nome="Grupo 1", perfil=self.perfil)
        self.subgrupo = SubGrupoTreinamento.objects.create(nome="Subgrupo 1", grupo=self.grupo)
        
        # Link proc1 to the profile/subgroup
        self.proc1.subgrupos_treinamento.add(self.subgrupo)
        
        # Associate colab1 with profile (so proc1 is required, but proc2 is NOT)
        self.colab_perfil = ColaboradorPerfil.objects.create(
            colaborador=self.colab1,
            perfil=self.perfil,
            data_atribuicao=date.today(),
            ativo=True
        )

        # Create training registrations
        # t1: colab1, proc1, 40 days ago (eligible, with profile link, no posterior pending)
        self.t1 = RegistroTreinamento.objects.create(
            colaborador=self.colab1,
            procedimento=self.proc1,
            data_treinamento=date.today() - timedelta(days=40),
            tipo="PROCEDIMENTO"
        )
        # t2: colab1, proc2, 45 days ago (eligible, NO profile link, has posterior pending!)
        self.t2 = RegistroTreinamento.objects.create(
            colaborador=self.colab1,
            procedimento=self.proc2,
            data_treinamento=date.today() - timedelta(days=45),
            tipo="PROCEDIMENTO"
        )
        # t3: colab1, proc2, 10 days ago (posterior pending session! in grace period)
        self.t3 = RegistroTreinamento.objects.create(
            colaborador=self.colab1,
            procedimento=self.proc2,
            data_treinamento=date.today() - timedelta(days=10),
            tipo="PROCEDIMENTO"
        )

    def test_list_view_displays_registrations(self):
        url = reverse('procedures:avaliacao_eficacia_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Objects in context
        page_obj = response.context['page_obj']
        object_ids = [obj.id for obj in page_obj.object_list]
        self.assertIn(self.t1.id, object_ids)
        self.assertIn(self.t2.id, object_ids)
        self.assertIn(self.t3.id, object_ids)

    def test_filter_by_days(self):
        url = reverse('procedures:avaliacao_eficacia_list')
        
        # Filter for grace period (< 30 days) -> should find t3 only
        response = self.client.get(url, {'dias_decorridos': 'menos_30'})
        object_ids = [obj.id for obj in response.context['page_obj'].object_list]
        self.assertEqual(len(object_ids), 1)
        self.assertIn(self.t3.id, object_ids)

        # Filter for 30-60 days -> should find t1 and t2
        response = self.client.get(url, {'dias_decorridos': '30_60'})
        object_ids = [obj.id for obj in response.context['page_obj'].object_list]
        self.assertEqual(len(object_ids), 2)
        self.assertIn(self.t1.id, object_ids)
        self.assertIn(self.t2.id, object_ids)

    def test_filter_by_profile_link(self):
        url = reverse('procedures:avaliacao_eficacia_list')
        
        # Filter for "COM_VINCULO" (Only t1 is linked to colab1's operator profile)
        response = self.client.get(url, {'vinculo': 'COM_VINCULO'})
        object_ids = [obj.id for obj in response.context['page_obj'].object_list]
        self.assertIn(self.t1.id, object_ids)
        self.assertNotIn(self.t2.id, object_ids)
        
        # Filter for "SEM_VINCULO" (t2 and t3 are not linked to colab1's Operator profile)
        response = self.client.get(url, {'vinculo': 'SEM_VINCULO'})
        object_ids = [obj.id for obj in response.context['page_obj'].object_list]
        self.assertNotIn(self.t1.id, object_ids)
        self.assertIn(self.t2.id, object_ids)
        self.assertIn(self.t3.id, object_ids)

    def test_filter_by_posterior_pending(self):
        url = reverse('procedures:avaliacao_eficacia_list')
        
        # Filter for "COM_POSTERIOR" (t2 has t3 as a posterior pending session)
        response = self.client.get(url, {'posterior': 'COM_POSTERIOR'})
        object_ids = [obj.id for obj in response.context['page_obj'].object_list]
        self.assertIn(self.t2.id, object_ids)
        self.assertNotIn(self.t1.id, object_ids)
        self.assertNotIn(self.t3.id, object_ids)

    def test_register_evaluation_not_applicable_requires_justification(self):
        url = reverse('procedures:avaliacao_eficacia_registrar', args=[self.t1.id])
        
        # Attempt to submit status NAO_APLICA with empty justification
        response = self.client.post(url, {
            'status': 'NAO_APLICA',
            'data_avaliacao': date.today().strftime('%Y-%m-%d'),
            'resultado_avaliacao': ''
        })
        self.t1.refresh_from_db()
        self.assertEqual(self.t1.avaliacao_eficacia_status, 'PENDENTE') # Did not change because it failed validation
        
        # Submit with valid justification
        response = self.client.post(url, {
            'status': 'NAO_APLICA',
            'data_avaliacao': date.today().strftime('%Y-%m-%d'),
            'resultado_avaliacao': 'Colaborador mudou de setor temporariamente.'
        })
        self.t1.refresh_from_db()
        self.assertEqual(self.t1.avaliacao_eficacia_status, 'NAO_APLICA')
        self.assertEqual(self.t1.resultado_avaliacao, 'Colaborador mudou de setor temporariamente.')

    def test_mass_evaluation_success(self):
        url = reverse('procedures:avaliacao_eficacia_registrar_massa')
        
        # Post to evaluate t1 and t2 together (t3 is ignored because it is in grace period)
        response = self.client.post(url, {
            'treinamento_ids': [self.t1.id, self.t2.id, self.t3.id],
            'status': 'EFICAZ',
            'data_avaliacao': date.today().strftime('%Y-%m-%d'),
            'resultado_avaliacao': 'Demonstrou conhecimento prático.'
        })
        
        self.t1.refresh_from_db()
        self.t2.refresh_from_db()
        self.t3.refresh_from_db()
        
        self.assertEqual(self.t1.avaliacao_eficacia_status, 'EFICAZ')
        self.assertEqual(self.t2.avaliacao_eficacia_status, 'EFICAZ')
        # t3 remains PENDENTE because it is in grace period (<30 days since training)
        self.assertEqual(self.t3.avaliacao_eficacia_status, 'PENDENTE')

    def test_filter_by_matriz(self):
        url = reverse('procedures:avaliacao_eficacia_list')
        
        # Filter for "Matriz Qualidade" -> should find t1 only
        response = self.client.get(url, {'matriz': 'Matriz Qualidade'})
        object_ids = [obj.id for obj in response.context['page_obj'].object_list]
        self.assertIn(self.t1.id, object_ids)
        self.assertNotIn(self.t2.id, object_ids)
        
        # Filter for "Matriz Produção" -> should find t2 and t3
        response = self.client.get(url, {'matriz': 'Matriz Produção'})
        object_ids = [obj.id for obj in response.context['page_obj'].object_list]
        self.assertNotIn(self.t1.id, object_ids)
        self.assertIn(self.t2.id, object_ids)
        self.assertIn(self.t3.id, object_ids)
