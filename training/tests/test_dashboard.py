from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from datetime import date

from procedures.models import RegistroTreinamento, Procedimento
from rh.models import Colaborador

class TestDashboardFilters(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='tester', password='pass')
        # Criar colaborador e procedimento
        self.col = Colaborador.objects.create(matricula='2000', nome_completo='Colab Teste')
        self.proc = Procedimento.objects.create(codigo='PROCX', nome='Proc X', numero_revisao='01')

        # Registro vigente (data + revisao bate)
        RegistroTreinamento.objects.create(colaborador=self.col, procedimento=self.proc, data_treinamento=date.today(), revisao_treinada='01', tipo='PROCEDIMENTO')
        # Registro pendente (sem data)
        RegistroTreinamento.objects.create(colaborador=self.col, procedimento=self.proc, data_treinamento=None, revisao_treinada='00', tipo='PROCEDIMENTO')

    def test_filtered_status_vigente(self):
        client = self.client
        client.force_login(self.user)
        url = reverse('training:dashboard_filtered') + '?status=vigente'
        resp = client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # Should only count the vigente record
        self.assertEqual(data['status_distribuicao']['vigente'], 1)
        self.assertGreaterEqual(data['total_treinamentos'], 0)
        self.assertTrue(all(r['data'] != 'Pendente' for r in data['dados_tabela']))

    def test_filtered_status_pendente(self):
        client = self.client
        client.force_login(self.user)
        url = reverse('training:dashboard_filtered') + '?status=pendente'
        resp = client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # Should only count the pendente record
        self.assertEqual(data['status_distribuicao']['pendente'], 1)
        self.assertTrue(any(r['data'] == 'Pendente' for r in data['dados_tabela']))
