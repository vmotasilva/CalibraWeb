from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from kpi import indicadores_insumo as eng
from kpi.models import (HierCategoria, HierCodigo, HierConsumo, HierItem, HierMovimento, HierSetor, HierSubcategoria,
                        Indicador, IndicadorInsumo, KpiHierarquico, Medicao, SetorIndicador)

HOJE = date(2026, 10, 28)  # quarta-feira


class InsBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('ins', 'i@x.com', 'x')
        self.client.force_login(self.user)
        kpi = KpiHierarquico.objects.create(nome='Insumos teste')
        setor = HierSetor.objects.create(kpi=kpi, nome='Surfaçagem')
        cat = HierCategoria.objects.create(setor=setor, nome='Polidoras')
        sub = HierSubcategoria.objects.create(categoria=cat, nome='PAD DLP')
        self.pad = HierItem.objects.create(subcategoria=sub, nome='Pad', unidade='un')
        self.cod = HierCodigo.objects.create(codigo=2821, item=self.pad)
        # KPI principal que traz a produção
        self.prod = Indicador.objects.create(nome='Produção', meta=0, campos='Lentes produzidas\nLentes perdidas')
        self.setor_prod = SetorIndicador.objects.create(indicador=self.prod, nome='Surfaçagem')
        self.ind = IndicadorInsumo.objects.create(
            nome='Pad', item=self.pad, modo='rendimento', producao_indicador=self.prod, producao_variavel='Lentes produzidas',
            producao_setor=self.setor_prod, participacao=Decimal(70), unidade='lentes/und', meta=Decimal(250), casas=0)

    def medicao(self, gran, periodo, produzidas, setor=True):
        return Medicao.objects.create(indicador=self.prod, setor=self.setor_prod if setor else None, periodo=periodo,
                                      granularidade=gran, valor=0, dados={'Lentes produzidas': str(produzidas)})

    def mov(self, dia, qtd, tipo='UTILIZACOES', cod=None):
        return HierMovimento.objects.create(codigo=cod or self.cod, data=dia, quantidade=Decimal(qtd), tipo=tipo)


class PeriodosTests(TestCase):
    def test_semana_8_semanas_segunda_a_domingo_ate_a_semana_de_hoje(self):
        p = eng.periodos('semana', date(2026, 10, 31), HOJE)
        self.assertEqual(len(p), 8)
        self.assertEqual((p[-1].ini, p[-1].fim), (date(2026, 10, 26), date(2026, 11, 1)))
        self.assertEqual(p[-1].rotulo, 'SEM 44')
        self.assertTrue(all(x.ini.weekday() == 0 for x in p))

    def test_mes_12_meses_e_dia_do_mes(self):
        m = eng.periodos('mes', date(2026, 10, 31), HOJE)
        self.assertEqual((len(m), m[0].rotulo, m[-1].rotulo), (12, 'nov/25', 'out/26'))
        d = eng.periodos('dia', date(2026, 10, 31), HOJE)
        self.assertEqual((len(d), d[0].rotulo, d[-1].rotulo), (31, '01', '31'))

    def test_periodos_de_varios_meses_alinhados_ao_calendario(self):
        t = eng.periodos('trimestre', date(2026, 11, 30), HOJE)
        self.assertEqual((len(t), t[-1].ini, t[-1].fim, t[-1].rotulo), (4, date(2026, 10, 1), date(2026, 12, 31), '4º tri/26'))
        b = eng.periodos('bimestre', date(2026, 10, 31), HOJE)
        self.assertEqual((b[-1].ini, b[-1].fim, b[0].rotulo), (date(2026, 9, 1), date(2026, 10, 31), '6º bim/25'))
        self.assertEqual(eng.periodos('ano', date(2026, 10, 31), HOJE)[-1].rotulo, '2026')
        self.assertEqual(eng.periodos('semestre', date(2026, 10, 31), HOJE)[-1].fim, date(2026, 12, 31))
        self.assertEqual(eng.periodos('quadrimestre', date(2026, 10, 31), HOJE)[-1].ini, date(2026, 9, 1))

    def test_mes_param(self):
        self.assertEqual(eng.mes_param('2026-02'), date(2026, 2, 28))
        self.assertEqual(eng.mes_param('lixo', HOJE), date(2026, 10, 31))


class CalculoTests(InsBase):
    def linha(self, visao, rotulo, ind=None, ref=date(2026, 10, 31)):
        s = eng.serie(ind or self.ind, visao, ref, HOJE)
        return next(l for l in s['linhas'] if l['rotulo'] == rotulo)

    def test_rendimento_semanal_usa_participacao_e_producao_da_semana(self):
        self.medicao('semanal', date(2026, 10, 19), 1000)
        self.mov(date(2026, 10, 20), 1)
        self.mov(date(2026, 10, 22), 1)
        l = self.linha('semana', 'SEM 43')
        self.assertEqual((l['producao'], l['consumo']), (Decimal(1000), Decimal(2)))
        self.assertEqual(l['valor'], Decimal('350'))  # 1000 × 70% ÷ 2
        self.assertTrue(l['ok'])  # meta 250, quanto maior melhor

    def test_sem_lancamento_da_semana_soma_os_dias_e_so_conta_utilizacoes_e_perdas(self):
        for d, v in ((date(2026, 10, 19), 300), (date(2026, 10, 20), 200)):
            self.medicao('diaria', d, v)
        self.mov(date(2026, 10, 20), 1)
        self.mov(date(2026, 10, 21), 5, tipo='DEVOLUCAO')  # não é consumo
        l = self.linha('semana', 'SEM 43')
        self.assertEqual(l['producao'], Decimal(500))
        self.assertEqual(l['consumo'], Decimal(1))
        self.assertEqual(l['valor'], Decimal('350'))

    def test_fator_do_codigo_converte_o_consumo_como_a_fita_de_35_metros(self):
        self.cod.fator = Decimal(35)
        self.cod.save()
        fita = IndicadorInsumo.objects.create(
            nome='Fita', item=self.pad, modo='rendimento', producao_indicador=self.prod, producao_variavel='Lentes produzidas',
            producao_setor=self.setor_prod, participacao=Decimal(100), meta=Decimal(9), casas=2)
        self.medicao('semanal', date(2026, 10, 19), 630)
        self.mov(date(2026, 10, 21), 2)  # 2 rolos × 35 m = 70 m
        l = self.linha('semana', 'SEM 43', fita)
        self.assertEqual(l['consumo'], Decimal(70))
        self.assertEqual(l['valor'], Decimal('9.00'))  # 630 ÷ 70

    def test_consumo_especifico_gramas_por_lente(self):
        aloy = IndicadorInsumo.objects.create(
            nome='Aloy', item=self.pad, modo='consumo', sentido='menor', producao_indicador=self.prod,
            producao_variavel='Lentes produzidas', producao_setor=self.setor_prod, meta=Decimal('0.12'), casas=3)
        self.medicao('mensal', date(2026, 9, 30), 10000)
        HierConsumo.objects.create(item=self.pad, periodo=date(2026, 9, 30), valor=Decimal(900))
        l = self.linha('mes', 'set/26', aloy)
        self.assertEqual(l['valor'], Decimal('0.090'))  # 900 ÷ 10000
        self.assertTrue(l['ok'])  # menor que 0,12

    def test_mes_usa_consumo_do_mes_e_manual_prevalece_sobre_movimentos(self):
        self.medicao('mensal', date(2026, 9, 30), 1000)
        self.mov(date(2026, 9, 10), 5)
        self.assertEqual(self.linha('mes', 'set/26')['consumo'], Decimal(5))
        HierConsumo.objects.create(item=self.pad, periodo=date(2026, 9, 30), valor=Decimal(10), origem='manual')
        l = self.linha('mes', 'set/26')
        self.assertEqual((l['consumo'], l['valor']), (Decimal(10), Decimal('70')))

    def test_sem_consumo_o_rendimento_nao_calcula_e_futuro_fica_vazio(self):
        self.medicao('semanal', date(2026, 10, 19), 1000)
        l = self.linha('semana', 'SEM 43')
        self.assertEqual((l['consumo'], l['valor'], l['ok']), (Decimal(0), None, None))
        futuro = self.linha('mes', 'nov/26', ref=date(2026, 11, 30))  # mês que ainda não começou
        self.assertEqual((futuro['consumo'], futuro['valor']), (None, None))

    def test_sem_producao_nao_calcula(self):
        self.mov(date(2026, 10, 20), 1)
        l = self.linha('semana', 'SEM 43')
        self.assertEqual((l['producao'], l['valor']), (None, None))

    def test_uso_nao_precisa_de_producao_e_meta_semanal_proporcional_ou_propria(self):
        filtro = IndicadorInsumo.objects.create(nome='Filtro', item=self.pad, modo='uso', meta=Decimal(45), casas=0)
        self.mov(date(2026, 10, 20), 3)
        l = self.linha('semana', 'SEM 43', filtro)
        self.assertEqual(l['valor'], Decimal(3))
        self.assertAlmostEqual(float(l['meta']), 45 * 7 / 31, places=3)
        filtro.meta_semanal = Decimal(10)
        self.assertEqual(self.linha('semana', 'SEM 43', filtro)['meta'], Decimal(10))
        self.assertEqual(self.linha('mes', 'out/26', filtro)['meta'], Decimal(45))

    def test_variavel_vazia_usa_o_valor_do_indicador(self):
        self.ind.producao_variavel = ''
        Medicao.objects.create(indicador=self.prod, setor=self.setor_prod, periodo=date(2026, 10, 19),
                               granularidade='semanal', valor=Decimal(800))
        self.mov(date(2026, 10, 20), 1)
        self.assertEqual(self.linha('semana', 'SEM 43')['producao'], Decimal(800))

    def test_producao_sem_setor_so_olha_lancamentos_gerais(self):
        self.ind.producao_setor = None
        self.medicao('semanal', date(2026, 10, 19), 111, setor=True)   # do setor: ignorado
        self.medicao('semanal', date(2026, 10, 12), 222, setor=False)  # geral
        self.assertIsNone(self.linha('semana', 'SEM 43')['producao'])
        self.assertEqual(self.linha('semana', 'SEM 42')['producao'], Decimal(222))


class TelasInsumoTests(InsBase):
    def dados(self, **extra):
        d = {'nome': 'Novo', 'item': self.pad.pk, 'modo': 'rendimento', 'producao_indicador': self.prod.pk,
             'producao_variavel': 'Lentes produzidas', 'producao_setor': self.setor_prod.pk, 'participacao': '70',
             'multiplicador': '1', 'unidade': 'lentes/und', 'casas': '0', 'sentido': 'maior', 'meta': '250,5', 'ativo': 'on'}
        d.update(extra)
        return d

    def test_painel_vazio_e_com_indicadores(self):
        IndicadorInsumo.objects.all().delete()
        r = self.client.get(reverse('kpi:ins_painel'))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context['sem_indicadores'])
        r = self.client.get(reverse('kpi:ins_painel'), {'visao': 'semana', 'mes': '2026-10'})
        self.assertEqual(r.status_code, 200)

    def test_painel_visoes_filtro_de_setor_e_area_atualizavel(self):
        for visao in ('dia', 'semana', 'mes'):
            r = self.client.get(reverse('kpi:ins_painel'), {'visao': visao, 'mes': '2026-10'})
            self.assertEqual(r.status_code, 200, visao)
            self.assertContains(r, 'id="resultado"')
            self.assertEqual(len(r.context['cards']), 1)
            self.assertIn('id="dados-ins-', r.content.decode())
        # o filtro de Setor só oferece setores que têm indicador
        kpi = self.pad.subcategoria.categoria.setor.kpi
        hmc = HierSetor.objects.create(kpi=kpi, nome='HMC')
        item2 = HierItem.objects.create(subcategoria=HierSubcategoria.objects.create(
            categoria=HierCategoria.objects.create(setor=hmc, nome='Orbit'), nome='Orbit 2.0'), nome='Diamante')
        IndicadorInsumo.objects.create(nome='Diamante', item=item2, modo='uso', meta=Decimal(3))
        r = self.client.get(reverse('kpi:ins_painel'), {'setor': hmc.pk})
        self.assertEqual([c['ind'].nome for c in r.context['cards']], ['Diamante'])
        r = self.client.get(reverse('kpi:ins_painel'), {'setor': self.ind.item.subcategoria.categoria.setor_id})
        self.assertEqual([c['ind'].nome for c in r.context['cards']], ['Pad'])
        self.assertEqual(len(self.client.get(reverse('kpi:ins_painel')).context['cards']), 2)
        self.assertEqual(self.client.get(reverse('kpi:ins_painel'), {'visao': 'lixo'}).context['visao'], '')

    def test_formulario_novo_e_editar_abrem(self):
        self.assertEqual(self.client.get(reverse('kpi:ins_novo')).status_code, 200)
        r = self.client.get(reverse('kpi:ins_editar', args=[self.ind.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['valores']['participacao'], '70')
        self.assertEqual(r.context['valores']['meta'], '250')  # sem notação científica nem zeros à toa
        novo = self.client.get(reverse('kpi:ins_novo')).context['valores']
        self.assertEqual((novo['participacao'], novo['multiplicador']), ('100', '1'))

    def test_previa_calcula_sem_gravar_e_avisa_quando_falta_item(self):
        self.medicao('mensal', date(2026, 9, 30), 1000)
        HierConsumo.objects.create(item=self.pad, periodo=date(2026, 9, 30), valor=Decimal(2))
        r = self.client.get(reverse('kpi:ins_preview'), self.dados(visao='mes', mes='2026-10', meta='250'))
        j = r.json()
        self.assertEqual(j['erro'], '')
        self.assertEqual(j['grafico']['labels'][-2], 'set/26')
        self.assertEqual(j['grafico']['valores'][-2], 350.0)
        self.assertEqual(IndicadorInsumo.objects.count(), 1)
        j = self.client.get(reverse('kpi:ins_preview'), {'nome': 'x'}).json()
        self.assertIn('Escolha o item', j['erro'])

    def test_salvar_cria_edita_valida_e_exclui(self):
        r = self.client.post(reverse('kpi:ins_salvar'), self.dados())
        self.assertRedirects(r, reverse('kpi:ins_painel'))
        novo = IndicadorInsumo.objects.get(nome='Novo')
        self.assertEqual((novo.meta, novo.participacao, novo.producao_setor, novo.criado_por), (Decimal('250.5'), Decimal(70), self.setor_prod, self.user))
        sem_ativo = self.dados(pk=novo.pk, nome='Renomeado')
        del sem_ativo['ativo']
        self.client.post(reverse('kpi:ins_salvar'), sem_ativo)  # checkbox desmarcado não vem no POST: fica inativo
        novo.refresh_from_db()
        self.assertEqual((novo.nome, novo.ativo), ('Renomeado', False))
        # inválidos
        antes = IndicadorInsumo.objects.count()
        for ruim in (self.dados(item=''), self.dados(nome=''), self.dados(participacao='0'), self.dados(participacao='150'),
                     self.dados(producao_indicador=''), self.dados(producao_variavel='Nao existe')):
            self.client.post(reverse('kpi:ins_salvar'), ruim)
        self.assertEqual(IndicadorInsumo.objects.count(), antes)
        # "uso" dispensa produção
        self.client.post(reverse('kpi:ins_salvar'), self.dados(nome='Filtro', modo='uso', producao_indicador=''))
        self.assertTrue(IndicadorInsumo.objects.filter(nome='Filtro', modo='uso').exists())
        self.client.post(reverse('kpi:ins_excluir', args=[novo.pk]))
        self.assertFalse(IndicadorInsumo.objects.filter(pk=novo.pk).exists())

    def test_modelos_da_planilha_sao_validos(self):
        from kpi.views_ins import MODELOS
        self.assertEqual({m['chave'] for m in MODELOS}, {'pad', 'membrana', 'fita', 'polidor', 'diamante', 'quartz', 'zirconio', 'aloy', 'dsx', 'filtro'})
        for m in MODELOS:
            self.assertIn(m['modo'], dict(IndicadorInsumo.MODOS))
            self.assertIn(m['sentido'], ('maior', 'menor'))
