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
        from openpyxl import Workbook, load_workbook
        for tipo, aba in (('valores', 'Valores'), ('motivos', 'Motivos')):
            for gran in ('diaria', 'semanal', 'mensal'):
                r = self.client.get(reverse('kpi:modelo_importacao', args=[tipo, gran]))
                self.assertEqual(r.status_code, 200)
                wb = load_workbook(io.BytesIO(r.content))
                self.assertEqual(wb.sheetnames[0], aba)
                self.assertNotIn('Motivos' if tipo == 'valores' else 'Valores', wb.sheetnames)
        self.assertEqual(self.client.get(reverse('kpi:modelo_importacao', args=['valores', 'x'])).status_code, 404)
        self.assertEqual(self.client.get(reverse('kpi:modelo_importacao', args=['x', 'mensal'])).status_code, 404)
        self.assertEqual(self.client.get(reverse('kpi:importar')).status_code, 200)

        def enviar(wb, tipo, gran):
            buf = io.BytesIO()
            wb.save(buf)
            buf.seek(0)
            buf.name = 'x.xlsx'
            return self.client.post(reverse('kpi:importar'), {'tipo': tipo, 'granularidade': gran, 'arquivo': buf}).context['resultado']

        wb = Workbook()
        v = wb.active
        v.title = 'Valores'
        v.append(['Indicador', 'Semana', 'Valor', 'Observação'])
        v.append(['SR', '15/10/2026', '94,5', 'ok'])
        v.append(['Inexistente', '15/10/2026', 1, ''])
        res = enviar(wb, 'valores', 'semanal')
        self.assertEqual((res['valores'], res['motivos'], len(res['erros'])), (1, 0, 1))
        self.assertEqual(str(Medicao.objects.get(granularidade='semanal').valor), '94.50')
        # planilha de gráficos enviada como tabelas é recusada com mensagem clara
        res = enviar(wb, 'motivos', 'semanal')
        self.assertEqual((res['motivos'], len(res['erros'])), (0, 1))
        self.assertIn('Valores', res['erros'][0][2] + 'Valores')

        self.ind.motivos_semanal = True
        self.ind.save()
        wb = Workbook()
        m = wb.active
        m.title = 'Motivos'
        m.append(['Indicador', 'Semana', 'Motivo', 'Quantidade'])
        m.append(['SR', '13/10/2026', 'Quebra', 3])
        m.append(['SR', '14/10/2026', 'Trinca', 1])
        res = enviar(wb, 'motivos', 'semanal')
        self.assertEqual((res['valores'], res['motivos'], len(res['erros'])), (0, 2, 0))
        self.assertEqual(Motivo.objects.filter(granularidade='semanal', data=date(2026, 10, 12)).count(), 2)
        # e o contrário: tabelas enviadas como gráficos
        res = enviar(wb, 'valores', 'semanal')
        self.assertEqual((res['valores'], len(res['erros'])), (0, 1))
        self.assertEqual(Medicao.objects.filter(granularidade='semanal').count(), 1)

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
        r = self.client.get(reverse('kpi:modelo_importacao', args=['valores', 'mensal']) + '?ind=%d' % ind.pk)
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
        r = self.client.post(reverse('kpi:importar'), {'tipo': 'valores', 'granularidade': 'mensal', 'arquivo': buf})
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

    def test_setores_opcionais(self):
        import io
        from openpyxl import Workbook, load_workbook
        sem = Indicador.objects.create(nome='Sem setor', meta=5, sentido='menor', ativo=True)
        self.assertEqual(sem.setores.count(), 0)
        base = {'nome': 'Quebras', 'meta': '5', 'sentido': 'menor', 'periodicidade': 'mensal', 'ativo': 'on',
                'exibir_mensal': 'on', 'motivos_mensal': 'on'}
        r = self.client.post(reverse('kpi:indicador_novo'), dict(base, setores_texto='Surfaçagem | 2,5\nAR\n'))
        self.assertEqual(r.status_code, 302)
        ind = Indicador.objects.get(nome='Quebras')
        surf, ar = list(ind.setores.all())
        self.assertEqual((surf.nome, str(surf.meta), ar.meta), ('Surfaçagem', '2.50', None))
        # meta inválida / repetida
        r = self.client.post(reverse('kpi:indicador_editar', args=[ind.pk]), dict(base, setores_texto='A | x'))
        self.assertEqual(r.status_code, 200)
        # lançamento geral e por setor convivem no mesmo período
        url = reverse('kpi:medicao_salvar', args=[ind.pk])
        self.client.post(url, {'granularidade': 'mensal', 'periodo': '2026-10-05', 'valor': '4'})
        self.client.post(url, {'granularidade': 'mensal', 'periodo': '2026-10-05', 'valor': '3', 'setor': surf.pk})
        self.client.post(url, {'granularidade': 'mensal', 'periodo': '2026-10-09', 'valor': '2', 'setor': surf.pk})
        self.assertEqual(Medicao.objects.filter(indicador=ind).count(), 2)
        self.assertEqual(str(Medicao.objects.get(indicador=ind, setor=surf).valor), '2.00')
        # setor de outro indicador é recusado
        outro = Indicador.objects.create(nome='Outro', meta=1)
        self.client.post(reverse('kpi:medicao_salvar', args=[outro.pk]),
                         {'granularidade': 'mensal', 'periodo': '2026-10-05', 'valor': '1', 'setor': surf.pk})
        self.assertEqual(Medicao.objects.filter(indicador=outro).count(), 0)
        # painel: escopo geral x setor, com a meta do setor
        r = self.client.get(reverse('kpi:painel') + '?ind=%d' % ind.pk)
        aba = [a for a in r.context['abas'] if a['ind'].pk == ind.pk][0]
        self.assertEqual((aba['setor'], str(aba['ultima'].valor), str(aba['meta'])), (None, '4.00', '5.00'))
        r = self.client.get(reverse('kpi:painel') + '?ind=%d&setor=%d' % (ind.pk, surf.pk))
        aba = [a for a in r.context['abas'] if a['ind'].pk == ind.pk][0]
        self.assertEqual((aba['setor'], str(aba['ultima'].valor), str(aba['meta'])), (surf, '2.00', '2.50'))
        self.assertTrue(aba['atingiu_escopo'])
        # setor sem meta usa a geral
        r = self.client.get(reverse('kpi:painel') + '?ind=%d&setor=%d' % (ind.pk, ar.pk))
        aba = [a for a in r.context['abas'] if a['ind'].pk == ind.pk][0]
        self.assertEqual(str(aba['meta']), '5.00')
        # motivos por setor
        m_url = reverse('kpi:motivo_salvar', args=[ind.pk])
        self.client.post(m_url, {'granularidade': 'mensal', 'data': '2026-10-01', 'descricao': ['Geral'], 'quantidade': ['1']})
        self.client.post(m_url, {'granularidade': 'mensal', 'data': '2026-10-01', 'descricao': ['Do setor'], 'quantidade': ['2'], 'setor': surf.pk})
        self.assertEqual(Motivo.objects.filter(setor=surf).count(), 1)
        self.assertEqual(Motivo.objects.filter(setor__isnull=True).count(), 1)
        # visão geral soma os motivos de todos os setores; a do setor mostra só os dele
        def top(qs):
            aba = [a for a in self.client.get(reverse('kpi:painel') + qs).context['abas'] if a['ind'].pk == ind.pk][0]
            return {t['descricao']: float(t['total']) for t in aba['motivos_tabs'][0]['top']}
        self.assertEqual(top('?ind=%d&mot=0' % ind.pk), {'Do setor': 2.0, 'Geral': 1.0})
        self.assertEqual(top('?ind=%d&setor=%d&mot=0' % (ind.pk, surf.pk)), {'Do setor': 2.0})
        self.assertEqual(top('?ind=%d&setor=%d&mot=0' % (ind.pk, ar.pk)), {})
        # filtro de período dos motivos: mês específico e intervalo
        def total(qs):
            aba = [a for a in self.client.get(reverse('kpi:painel') + qs).context['abas'] if a['ind'].pk == ind.pk][0]
            return sum(t['total'] for t in aba['motivos_tabs'][0]['top'])
        self.client.post(m_url, {'granularidade': 'mensal', 'data': '2026-09-15', 'descricao': ['Setembro'], 'quantidade': ['5']})
        self.assertEqual(total('?ind=%d&mot=mes&mes=2026-09' % ind.pk), 5)
        self.assertEqual(total('?ind=%d&mot=mes&mes=2026-10' % ind.pk), 3)
        self.assertEqual(total('?ind=%d&mot=periodo&de=2026-09-01&ate=2026-10-31' % ind.pk), 8)
        self.assertEqual(total('?ind=%d&mot=periodo&de=2026-10-31&ate=2026-09-30' % ind.pk), 8)  # invertido é corrigido
        self.assertEqual(total('?ind=%d&mot=periodo&de=2026-10-01' % ind.pk), 3)
        self.assertEqual(total('?ind=%d&mot=mes&mes=lixo' % ind.pk), 8)  # inválido cai em "todo o período"
        # setor com lançamentos não pode ser removido
        r = self.client.post(reverse('kpi:indicador_editar', args=[ind.pk]), dict(base, setores_texto='AR'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(ind.setores.count(), 2)
        # modelo traz a coluna Setor e a importação a respeita
        r = self.client.get(reverse('kpi:modelo_importacao', args=['valores', 'mensal']) + '?ind=%d' % ind.pk)
        self.assertIn('Setor', [c.value for c in load_workbook(io.BytesIO(r.content))['Valores'][1]])
        r = self.client.get(reverse('kpi:modelo_importacao', args=['motivos', 'mensal']) + '?ind=%d' % ind.pk)
        self.assertIn('Setor', [c.value for c in load_workbook(io.BytesIO(r.content))['Motivos'][1]])
        wb = Workbook()
        v = wb.active
        v.title = 'Valores'
        v.append(['Indicador', 'Mês', 'Setor', 'Valor', 'Observação'])
        v.append(['Quebras', '11/2026', 'AR', 1.5, ''])
        v.append(['Quebras', '11/2026', 'Inexistente', 1, ''])
        v.append(['Quebras', '11/2026', None, 4, ''])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        buf.name = 'x.xlsx'
        r = self.client.post(reverse('kpi:importar'), {'tipo': 'valores', 'granularidade': 'mensal', 'arquivo': buf})
        self.assertEqual((r.context['resultado']['valores'], len(r.context['resultado']['erros'])), (2, 1))
        self.assertEqual(Medicao.objects.filter(indicador=ind, periodo=date(2026, 11, 30)).count(), 2)
