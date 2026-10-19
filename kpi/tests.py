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

    def test_motivos_por_periodo(self):
        self.salvar('mensal', '2026-10-05', '90')
        url = reverse('kpi:motivo_salvar', args=[self.ind.pk])
        hoje = date.today().isoformat()
        self.client.post(url, {'granularidade': 'diaria', 'data': hoje,
                               'descricao': ['Quebra', 'quebra ', 'Trinca', ''], 'quantidade': ['3', '2', '1', '5']})
        self.assertEqual(Motivo.objects.count(), 3)
        r = self.client.get(reverse('kpi:painel') + '?ind=%d&mot=0' % self.ind.pk)
        self.assertEqual(r.status_code, 200)
        diario = r.context['abas'][0]['motivos_tabs'][0]
        self.assertEqual(diario['gran'], 'diaria')
        self.assertEqual([t['descricao'] for t in diario['top']], ['Quebra', 'Trinca'])
        self.assertEqual(float(diario['top'][0]['total']), 5.0)
        # regravar o mesmo período substitui os motivos
        self.client.post(url, {'granularidade': 'diaria', 'data': hoje, 'descricao': ['Editado'], 'quantidade': ['9']})
        self.assertEqual(list(Motivo.objects.values_list('descricao', flat=True)), ['Editado'])
        # semana normaliza para segunda-feira; mês para o último dia
        self.client.post(url, {'granularidade': 'semanal', 'data': '2026-10-15', 'descricao': ['A'], 'quantidade': ['1']})
        self.client.post(url, {'granularidade': 'mensal', 'data': '2026-10-15', 'descricao': ['B'], 'quantidade': ['1']})
        self.assertEqual(Motivo.objects.get(granularidade='semanal').data, date(2026, 10, 12))
        self.assertEqual(Motivo.objects.get(granularidade='mensal').data, date(2026, 10, 31))
        # enviar vazio apaga o período
        self.client.post(url, {'granularidade': 'diaria', 'data': hoje, 'descricao': [''], 'quantidade': ['1']})
        self.assertEqual(Motivo.objects.filter(granularidade='diaria').count(), 0)
        self.client.post(reverse('kpi:medicao_excluir', args=[Medicao.objects.get().pk]))
        self.assertEqual(Medicao.objects.count(), 0)
        self.assertEqual(self.client.get(reverse('kpi:indicadores')).status_code, 200)

    def test_ordem_das_abas(self):
        b = Indicador.objects.create(nome='B', meta=1)
        c = Indicador.objects.create(nome='C', meta=1)
        nomes = lambda: [x.nome for x in Indicador.objects.all()]
        self.client.post(reverse('kpi:indicador_mover', args=[c.pk]), {'dir': 'up'})
        self.client.post(reverse('kpi:indicador_mover', args=[c.pk]), {'dir': 'up'})
        self.assertEqual(nomes()[0], 'C')
        r = self.client.get(reverse('kpi:painel'))
        self.assertEqual(r.context['abas'][0]['ind'].nome, 'C')
        self.assertEqual(self.client.get(reverse('kpi:indicadores')).status_code, 200)
