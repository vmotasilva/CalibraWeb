from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from kpi.models import Indicador, Medicao, Motivo


class KpiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('kpi', 'k@x.com', 'x')
        self.client.force_login(self.user)
        self.ind = Indicador.objects.create(nome='SR', meta=95, exibir_semanal=True, exibir_diario=True, motivos_diario=True, motivos_semanal=True, motivos_mensal=True)

    def salvar(self, gran, periodo, valor):
        return self.client.post(reverse('kpi:medicao_salvar', args=[self.ind.pk]),
                                {'granularidade': gran, 'periodo': periodo, 'valor': valor, 'observacao': ''})

    def test_cria_indicador(self):
        r = self.client.post(reverse('kpi:indicador_novo'), {
            'nome': 'Retrabalho', 'unidade': '%', 'meta': '4', 'sentido': 'menor',
            'periodicidade': 'mensal', 'ativo': 'on', 'exibir_mensal': 'on'})
        self.assertEqual(r.status_code, 302)
        novo = Indicador.objects.get(nome='Retrabalho')
        self.assertTrue(novo.exibir_mensal)
        self.assertFalse(novo.exibir_semanal or novo.motivos_diario)

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
        self.ind.exibir_semanal = False
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

    def test_modelos_e_importacao(self):
        import io
        from openpyxl import load_workbook
        for gran in ('diaria', 'semanal', 'mensal'):
            r = self.client.get(reverse('kpi:modelo_importacao', args=[gran]))
            self.assertEqual(r.status_code, 200)
            wb = load_workbook(io.BytesIO(r.content))
            self.assertEqual(wb.sheetnames[:2], ['Valores', 'Motivos'])
        self.assertEqual(self.client.get(reverse('kpi:modelo_importacao', args=['x'])).status_code, 404)
        self.assertEqual(self.client.get(reverse('kpi:importar')).status_code, 200)

        from openpyxl import Workbook
        wb = Workbook()
        v = wb.active
        v.title = 'Valores'
        v.append(['Indicador', 'Semana', 'Valor', 'Observação'])
        v.append(['SR', '15/10/2026', '94,5', 'ok'])
        v.append(['Inexistente', '15/10/2026', 1, ''])
        m = wb.create_sheet('Motivos')
        m.append(['Indicador', 'Semana', 'Motivo', 'Quantidade'])
        m.append(['SR', '13/10/2026', 'Quebra', 3])
        m.append(['SR', '14/10/2026', 'Trinca', 1])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        buf.name = 'x.xlsx'
        r = self.client.post(reverse('kpi:importar'), {'granularidade': 'semanal', 'arquivo': buf})
        res = r.context['resultado']
        self.assertEqual((res['valores'], res['motivos'], len(res['erros'])), (1, 2, 1))
        self.assertEqual(str(Medicao.objects.get(granularidade='semanal').valor), '94.50')
        self.assertEqual(Motivo.objects.filter(granularidade='semanal', data=date(2026, 10, 12)).count(), 2)

    def test_campos_formula_e_modelo_por_indicador(self):
        import io
        from openpyxl import Workbook, load_workbook
        ind = Indicador.objects.create(
            nome='Quebras', meta=5, sentido='menor', campos='Lentes produzidas\nLentes perdidas',
            formula='[Lentes perdidas] / [Lentes produzidas] * 100')
        # pop-up: calcula o valor pela fórmula quando vazio
        self.client.post(reverse('kpi:medicao_salvar', args=[ind.pk]), {
            'granularidade': 'mensal', 'periodo': '2026-10-10', 'valor': '', 'campo_0': '200', 'campo_1': '10', 'observacao': ''})
        m = Medicao.objects.get(indicador=ind)
        self.assertEqual(str(m.valor), '5.00')
        self.assertEqual(m.dados['Lentes perdidas'], '10')
        # fórmula inválida no cadastro
        r = self.client.post(reverse('kpi:indicador_editar', args=[ind.pk]), {
            'nome': 'Quebras', 'meta': '5', 'sentido': 'menor', 'periodicidade': 'mensal',
            'campos': 'A', 'formula': '[B] / 2'})
        self.assertEqual(r.status_code, 200)
        # modelo específico traz as colunas dos campos
        r = self.client.get(reverse('kpi:modelo_importacao', args=['mensal']) + '?ind=%d' % ind.pk)
        wb = load_workbook(io.BytesIO(r.content))
        cab = [c.value for c in wb['Valores'][1]]
        self.assertEqual(cab[:4], ['Indicador', 'Mês', 'Lentes produzidas', 'Lentes perdidas'])
        # importação lê os campos pelo cabeçalho e calcula o valor
        wb = Workbook()
        v = wb.active
        v.title = 'Valores'
        v.append(['Indicador', 'Mês', 'Lentes produzidas', 'Lentes perdidas', 'Valor (opcional)', 'Observação'])
        v.append(['Quebras', '11/2026', 400, 8, None, ''])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        buf.name = 'x.xlsx'
        r = self.client.post(reverse('kpi:importar'), {'granularidade': 'mensal', 'arquivo': buf})
        self.assertEqual(len(r.context['resultado']['erros']), 0)
        novo = Medicao.objects.get(indicador=ind, periodo=date(2026, 11, 30))
        self.assertEqual(str(novo.valor), '2.00')
        self.assertEqual(novo.dados['Lentes produzidas'], '400')

    def test_flags_de_exibicao(self):
        base = {'nome': 'Flags', 'meta': '1', 'sentido': 'maior', 'periodicidade': 'mensal'}
        self.client.post(reverse('kpi:indicador_novo'), dict(base, ativo='on', exibir_mensal='on', exibir_diario='on', motivos_semanal='on'))
        ind = Indicador.objects.get(nome='Flags')
        self.assertEqual(ind.graficos(), ['mensal', 'diaria'])
        self.assertTrue(ind.permite_motivos('semanal') and not ind.permite_motivos('diaria'))
        r = self.client.get(reverse('kpi:painel') + '?ind=%d' % ind.pk)
        html = r.content.decode()
        pk = ind.pk
        self.assertIn('kpi-chart-%d-mensal' % pk, html)
        self.assertIn('kpi-chart-%d-diaria' % pk, html)
        self.assertNotIn('kpi-chart-%d-semanal' % pk, html)
        aba = [a for a in r.context['abas'] if a['ind'].pk == pk][0]
        self.assertEqual([t['gran'] for t in aba['motivos_tabs']], ['semanal'])
        # motivos de período não habilitado são recusados
        url = reverse('kpi:motivo_salvar', args=[pk])
        self.client.post(url, {'granularidade': 'diaria', 'data': '2026-10-15', 'descricao': ['X'], 'quantidade': ['1']})
        self.assertEqual(Motivo.objects.count(), 0)
        self.client.post(url, {'granularidade': 'semanal', 'data': '2026-10-15', 'descricao': ['X'], 'quantidade': ['1']})
        self.assertEqual(Motivo.objects.count(), 1)
