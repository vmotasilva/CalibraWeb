from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from kpi.models import Indicador, Medicao, Motivo


class KpiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('kpi', 'k@x.com', 'x')
        self.client.force_login(self.user)
        self.ind = Indicador.objects.create(nome='SR', meta=95, acompanhamento_detalhado=True)

    def salvar(self, gran, periodo, valor):
        return self.client.post(reverse('kpi:medicao_salvar', args=[self.ind.pk]),
                                {'granularidade': gran, 'periodo': periodo, 'valor': valor, 'observacao': ''})

    def test_cria_indicador(self):
        r = self.client.post(reverse('kpi:indicador_novo'), {
            'nome': 'Retrabalho', 'unidade': '%', 'meta': '4', 'sentido': 'menor',
            'periodicidade': 'mensal', 'acompanhamento_detalhado': 'on', 'ativo': 'on'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Indicador.objects.get(nome='Retrabalho').acompanhamento_detalhado)

    def test_normaliza_e_atualiza(self):
        self.salvar('mensal', '2026-10-05', '90')
        self.salvar('mensal', '2026-10-20', '96')
        m = Medicao.objects.get(granularidade='mensal')
        self.assertEqual(m.periodo, date(2026, 10, 31))
        self.assertEqual(str(m.valor), '96.00')
        self.salvar('semanal', '2026-10-15', '91')  # quinta -> segunda 12/10
        self.salvar('semanal', '2026-10-13', '92')
        s = Medicao.objects.get(granularidade='semanal')
        self.assertEqual(s.periodo, date(2026, 10, 12))
        self.salvar('diaria', '2026-10-15', '93')
        self.assertEqual(Medicao.objects.count(), 3)

    def test_sem_acompanhamento_bloqueia_semanal(self):
        self.ind.acompanhamento_detalhado = False
        self.ind.save()
        self.salvar('semanal', '2026-10-15', '91')
        self.assertEqual(Medicao.objects.count(), 0)

    def test_painel_motivos_e_exclusao(self):
        self.salvar('mensal', '2026-10-05', '90')
        url = reverse('kpi:motivo_salvar', args=[self.ind.pk])
        hoje = date.today().isoformat()
        self.client.post(url, {'data': hoje, 'descricao': 'Quebra', 'quantidade': '3'})
        self.client.post(url, {'data': hoje, 'descricao': 'quebra ', 'quantidade': '2'})
        self.client.post(url, {'data': hoje, 'descricao': 'Trinca', 'quantidade': '1'})
        r = self.client.get(reverse('kpi:painel') + '?ind=%d' % self.ind.pk)
        self.assertEqual(r.status_code, 200)
        top = r.context['abas'][0]['top']
        self.assertEqual([t['descricao'] for t in top], ['Quebra', 'Trinca'])
        self.assertEqual(float(top[0]['total']), 5.0)
        mot = Motivo.objects.first()
        self.client.post(url, {'motivo_id': mot.pk, 'data': hoje, 'descricao': 'Editado', 'quantidade': '9'})
        mot.refresh_from_db()
        self.assertEqual(mot.descricao, 'Editado')
        self.client.post(reverse('kpi:motivo_excluir', args=[mot.pk]))
        self.assertEqual(Motivo.objects.count(), 2)
        self.client.post(reverse('kpi:medicao_excluir', args=[Medicao.objects.get().pk]))
        self.assertEqual(Medicao.objects.count(), 0)
        self.assertEqual(self.client.get(reverse('kpi:indicadores')).status_code, 200)
