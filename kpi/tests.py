from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from kpi.models import Indicador, Medicao


class KpiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('kpi', 'k@x.com', 'x')
        self.client.force_login(self.user)

    def test_fluxo_completo(self):
        r = self.client.post(reverse('kpi:indicador_novo'), {
            'nome': 'Retrabalho', 'area': 'Lab', 'unidade': '%', 'meta': '4', 'sentido': 'menor',
            'periodicidade': 'mensal', 'ativo': 'on'})
        ind = Indicador.objects.get()
        self.assertRedirects(r, reverse('kpi:indicador_detalhe', args=[ind.pk]))
        url = reverse('kpi:indicador_detalhe', args=[ind.pk])
        self.client.post(url, {'periodo': '2026-10-01', 'valor': '2.85', 'observacao': ''})
        self.client.post(url, {'periodo': '2026-10-01', 'valor': '5', 'observacao': ''})
        self.assertEqual(Medicao.objects.count(), 1)
        self.assertFalse(ind.atingiu(Decimal('5')))
        self.assertTrue(ind.atingiu(Decimal('3')))
        for name in ('kpi:painel', 'kpi:indicadores'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(reverse('kpi:medicao_excluir', args=[Medicao.objects.get().pk]))
        self.assertEqual(Medicao.objects.count(), 0)

    def test_parcial(self):
        ind = Indicador.objects.create(nome='SR', meta=95, acompanhamento='semanal')
        url = reverse('kpi:indicador_detalhe', args=[ind.pk])
        self.client.post(url, {'periodo': '2026-10-12', 'valor': '90', 'parcial': 'on'})
        self.client.post(url, {'periodo': '2026-10-05', 'valor': '96'})
        self.assertEqual(Medicao.objects.filter(indicador=ind, parcial=True).count(), 1)
        self.assertEqual(Medicao.objects.filter(indicador=ind, parcial=False).count(), 1)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertContains(self.client.get(reverse('kpi:painel')), 'Parcial 12/10')
        sem = Indicador.objects.create(nome='X', meta=1)
        self.client.post(reverse('kpi:indicador_detalhe', args=[sem.pk]), {'periodo': '2026-10-05', 'valor': '1', 'parcial': 'on'})
        self.assertFalse(Medicao.objects.get(indicador=sem).parcial)
