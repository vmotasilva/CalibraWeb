import io
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from openpyxl import Workbook

from kpi import insumos
from kpi.models import (IndicadorInsumo, HierCategoria, HierCodigo, HierConsumo, HierItem, HierMovimento, HierSetor,
                        HierSubcategoria, KpiHierarquico)

SERIAL_2026_10_05 = (date(2026, 10, 5) - date(1899, 12, 30)).days
SERIAL_2026_10_20 = (date(2026, 10, 20) - date(1899, 12, 30)).days
SERIAL_2026_11_02 = (date(2026, 11, 2) - date(1899, 12, 30)).days


def _linha(cod, nome, qtd, tipo, serial, origem='REQUISICAO  ', ident=1):
    return [cod, f'{nome} / REF{cod} / UN', qtd, tipo, serial, 'SAÍDA  ', origem, 'NÃO', ident]


def _xlsx(linhas):
    wb = Workbook()
    ws = wb.active
    for l in linhas:
        ws.append(l)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _formatado(linhas_por_familia):
    """Imita o relatório formatado: cabeçalho, família, código ora na coluna A ora na B, subtotais e rodapé de página."""
    saida = [[None] * 26, [None] * 8 + ['Consulta Movimento em Estoque'], ['Código', 'Material / Referência / UN']]
    for familia, linhas in linhas_por_familia.items():
        saida.append(['Família:', familia])
        for n, l in enumerate(linhas):
            cod, mat, qtd, tipo, data, tipo2, origem, estorno, ident = l
            linha = [None] * 26
            colunas = (0, 1, 12, 13, 15, 18, 20, 23, 25) if n % 2 == 0 else (1, 2, 12, 13, 15, 18, 20, 23, 25)
            for col, v in zip(colunas, l):
                linha[col] = v
            saida.append(linha)
        saida.append([None, 27.0] + [None] * 24)  # subtotal
    saida.append([46330.4, None] + [None] * 22 + ['Página 1 de 1'])
    return saida


class InsumosBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('hier', 'h@x.com', 'x')
        self.client.force_login(self.user)
        self.kpi = KpiHierarquico.objects.get(nome='Insumos')  # semeado pela migração
        self.setor = self.kpi.setores.get(nome='Surfaçagem')
        self.cat = HierCategoria.objects.create(setor=self.setor, nome='Polidora')
        self.sub = HierSubcategoria.objects.create(categoria=self.cat, nome='DLP')
        self.pads = HierItem.objects.create(subcategoria=self.sub, nome='Pads', unidade='un', meta=Decimal('10'))
        self.liquido = HierItem.objects.create(subcategoria=self.sub, nome='Líquido', unidade='L', meta=Decimal('4'))

    def importar(self, linhas, formatado=None):
        info = insumos.interpretar(formatado if formatado is not None else linhas)
        return insumos.importar(info['registros'])


class TelaInsumosTests(InsumosBase):
    def test_cards_por_item_agrupados_por_setor_em_dia_semana_e_mes(self):
        HierConsumo.objects.create(item=self.pads, periodo=date(2026, 10, 31), valor=Decimal('8'))
        for visao in ('mes', 'semana', 'dia'):
            r = self.client.get(reverse('kpi:hier_consumo'), {'visao': visao, 'mes': '2026-10'})
            self.assertEqual(r.status_code, 200, visao)
            cards = [c for g in r.context['grupos'] for c in g['cards']]
            self.assertEqual({c['item'].nome for c in cards}, {'Pads', 'Líquido'})
            self.assertEqual(r.context['grupos'][0]['setor'].nome, 'Surfaçagem')
        r = self.client.get(reverse('kpi:hier_consumo'), {'visao': 'mes', 'mes': '2026-10'})
        pads = next(c for g in r.context['grupos'] for c in g['cards'] if c['item'] == self.pads)
        self.assertEqual((pads['ultimo']['valor'], pads['dentro'], pads['fora']), (8, 1, 0))
        hmc = self.kpi.setores.get(nome='HMC')
        sub_hmc = HierSubcategoria.objects.create(categoria=HierCategoria.objects.create(setor=hmc, nome='CDC'), nome='CDC')
        HierItem.objects.create(subcategoria=sub_hmc, nome='Filtro', unidade='un')
        r = self.client.get(reverse('kpi:hier_consumo'), {'setor': hmc.pk})
        self.assertEqual([c['item'].nome for g in r.context['grupos'] for c in g['cards']], ['Filtro'])


class KpiHierarquicoTests(InsumosBase):
    def test_semente_tem_os_tres_setores(self):
        self.assertEqual(set(self.kpi.setores.values_list('nome', flat=True)), {'Surfaçagem', 'HMC', 'Montagem'})

    def test_cadastro_cria_a_arvore_com_codigos(self):
        r = self.client.post(reverse('kpi:hier_cadastro_salvar'), {'tipo': 'sub', 'pai': self.cat.pk, 'nome': 'Toro Flex'})
        self.assertEqual(r.status_code, 302)
        sub = HierSubcategoria.objects.get(nome='Toro Flex')
        self.client.post(reverse('kpi:hier_cadastro_salvar'),
                         {'tipo': 'item', 'pai': sub.pk, 'nome': 'Graxa', 'unidade': 'un', 'meta': '12,5', 'codigos': '3989, 3993'})
        item = HierItem.objects.get(nome='Graxa')
        self.assertEqual(item.meta, Decimal('12.5'))
        self.assertEqual(set(item.codigos.values_list('codigo', flat=True)), {3989, 3993})

    def test_editar_codigos_do_item_move_e_desvincula(self):
        self.client.post(reverse('kpi:hier_cadastro_salvar'), {'tipo': 'item', 'pk': self.pads.pk, 'nome': 'Pads', 'codigos': '3989 3993'})
        self.client.post(reverse('kpi:hier_cadastro_salvar'), {'tipo': 'item', 'pk': self.liquido.pk, 'nome': 'Líquido', 'codigos': '3993'})
        self.assertEqual(set(self.pads.codigos.values_list('codigo', flat=True)), {3989})
        self.assertEqual(set(self.liquido.codigos.values_list('codigo', flat=True)), {3993})
        self.client.post(reverse('kpi:hier_cadastro_salvar'), {'tipo': 'item', 'pk': self.pads.pk, 'nome': 'Pads', 'codigos': ''})
        self.assertIsNone(HierCodigo.objects.get(codigo=3989).item)

    def test_nome_duplicado_no_mesmo_nivel_nao_quebra(self):
        r = self.client.post(reverse('kpi:hier_cadastro_salvar'), {'tipo': 'sub', 'pai': self.cat.pk, 'nome': 'DLP'}, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(HierSubcategoria.objects.filter(categoria=self.cat, nome='DLP').count(), 1)

    def test_lancar_manual_e_filtros_do_painel(self):
        url = reverse('kpi:hier_lancar')
        self.client.post(url, {'mes': '2026-10', f'valor_{self.pads.pk}': '8', f'valor_{self.liquido.pk}': '5,5'})
        self.client.post(url, {'mes': '2026-10', f'valor_{self.pads.pk}': '9', f'valor_{self.liquido.pk}': ''})
        self.assertEqual(HierConsumo.objects.get(item=self.pads).valor, Decimal('9'))
        self.assertEqual(HierConsumo.objects.get(item=self.liquido).valor, Decimal('5.5'))
        r = self.client.get(reverse('kpi:hier_painel'), {'kpi': self.kpi.pk, 'setor': self.setor.pk, 'categoria': self.cat.pk, 'sub': self.sub.pk, 'mes': '2026-10'})
        self.assertEqual((r.context['dentro'], r.context['fora']), (1, 1))
        self.assertEqual(r.context['serie']['modo'], 'percentual')
        r = self.client.get(reverse('kpi:hier_painel'), {'kpi': self.kpi.pk, 'setor': self.setor.pk, 'categoria': self.cat.pk, 'sub': self.sub.pk, 'item': self.liquido.pk, 'mes': '2026-10'})
        self.assertEqual((r.context['serie']['modo'], r.context['serie']['valores'][-1], r.context['serie']['meta']), ('valor', 5.5, 4.0))

    def test_indicadores_do_item_viram_abas_na_tabela_do_grafico(self):
        base = {'kpi': self.kpi.pk, 'item': self.liquido.pk, 'mes': '2026-10'}
        r = self.client.get(reverse('kpi:hier_painel'), base)
        self.assertEqual(r.context['indicadores_item'], [])
        self.assertNotContains(r, 'data-bs-toggle="tab"')
        IndicadorInsumo.objects.create(nome='Uso do líquido', item=self.liquido, modo='uso', meta=Decimal(10), casas=1)
        IndicadorInsumo.objects.create(nome='Inativo', item=self.liquido, modo='uso', ativo=False)
        r = self.client.get(reverse('kpi:hier_painel'), base)
        self.assertEqual([x['ind'].nome for x in r.context['indicadores_item']], ['Uso do líquido'])
        self.assertContains(r, 'Uso do líquido')
        self.assertNotContains(r, 'Inativo')
        self.assertNotContains(r, '<th class="text-end">% da meta</th>')

    def test_reajustar_meta_pelo_grid_de_consumo(self):
        url = reverse('kpi:hier_lancar')
        self.client.post(url, {'mes': '2026-10', f'meta_{self.liquido.pk}': '7,5'})
        self.liquido.refresh_from_db()
        self.assertEqual(self.liquido.meta, Decimal('7.50'))
        self.client.post(url, {'mes': '2026-10', f'meta_{self.liquido.pk}': 'abc'})
        self.liquido.refresh_from_db()
        self.assertEqual(self.liquido.meta, Decimal('7.50'))
        self.client.post(url, {'mes': '2026-10', f'meta_{self.liquido.pk}': ''})
        self.liquido.refresh_from_db()
        self.assertIsNone(self.liquido.meta)

    def test_filtros_independentes_deduzem_os_niveis_acima(self):
        r = self.client.get(reverse('kpi:hier_painel'), {'kpi': self.kpi.pk, 'item': self.liquido.pk})
        c = r.context
        self.assertEqual((c['setor'], c['categoria'], c['sub'], c['item']), (self.setor, self.cat, self.sub, self.liquido))
        # Sem nenhum filtro, todas as categorias/subcategorias/itens ficam disponíveis (nada desabilitado em cascata).
        r = self.client.get(reverse('kpi:hier_painel'), {'kpi': self.kpi.pk})
        self.assertIn(self.cat, r.context['categorias'])
        self.assertIn(self.sub, r.context['subs'])
        self.assertIn(self.pads, r.context['itens_opcoes'])
        self.assertNotRegex(r.content.decode(), r'<select[^>]*disabled')

    def test_filtros_em_botoes_e_area_de_resultado_atualizavel(self):
        r = self.client.get(reverse('kpi:hier_painel'), {'kpi': self.kpi.pk, 'sub': self.sub.pk})
        html = r.content.decode()
        for nivel in ('setor', 'categoria', 'sub', 'item'):
            self.assertIn(f'data-chips="{nivel}"', html)
        self.assertNotIn('<select name="setor"', html)
        # A área #resultado (gráfico + tabela) é o que o JS troca ao filtrar, sem recarregar a página.
        self.assertIn('id="resultado"', html)
        self.assertIn('id="dados-grafico"', html)
        self.assertEqual(r.context['arvore']['setores'][0]['nome'], self.setor.nome)
        self.assertEqual(r.context['sub'], self.sub)

    def test_filtros_em_popup_com_botao_de_limpar(self):
        html = self.client.get(reverse('kpi:hier_painel'), {'kpi': self.kpi.pk}).content.decode()
        self.assertIn('data-bs-target="#modal-filtros"', html)  # botão que abre o pop-up
        self.assertIn('id="modal-filtros"', html)
        self.assertIn('id="limpar-filtros"', html)  # botão de limpar filtros fora do pop-up
        self.assertIn('data-limpar', html)  # e também no rodapé do pop-up
        # as linhas de botões ficam dentro do pop-up
        modal = html[html.index('id="modal-filtros"'):]
        for nivel in ('setor', 'categoria', 'sub', 'item'):
            self.assertIn(f'data-chips="{nivel}"', modal)

    def test_tabela_de_dados_do_grafico(self):
        HierConsumo.objects.create(item=self.liquido, periodo=date(2026, 9, 30), valor=Decimal('3'))
        HierConsumo.objects.create(item=self.liquido, periodo=date(2026, 10, 31), valor=Decimal('5.5'))
        base = {'kpi': self.kpi.pk, 'item': self.liquido.pk, 'mes': '2026-10'}
        s = self.client.get(reverse('kpi:hier_painel'), base).context['serie']
        self.assertEqual(len(s['tabela']), 12)
        set_, out = s['tabela'][-2], s['tabela'][-1]
        self.assertEqual((set_['rotulo'], set_['valor'], set_['meta'], set_['pct'], set_['ok']), ('09/2026', 3.0, 4.0, 75, True))
        self.assertEqual((out['valor'], out['pct'], out['ok']), (5.5, 138, False))
        self.assertEqual(s['tabela'][0]['ok'], None)  # sem lançamento
        r = self.client.get(reverse('kpi:hier_painel'), base)
        self.assertContains(r, 'id="tabela-dados"')
        self.assertContains(r, 'Acima')
        # vários itens: tabela em % da meta (sem coluna de %)
        r = self.client.get(reverse('kpi:hier_painel'), {'kpi': self.kpi.pk, 'mes': '2026-10'})
        t = r.context['serie']['tabela']
        self.assertEqual(r.context['serie']['modo'], 'percentual')
        self.assertTrue(all(l['pct'] is None for l in t))
        self.assertNotContains(r, '% da meta</th>')
        # dia e semana: uma linha por período, com a faixa de datas
        d = self.client.get(reverse('kpi:hier_painel'), {**base, 'visao': 'dia'}).context['serie']['tabela']
        self.assertEqual((len(d), d[0]['faixa']), (31, '01/10/2026'))
        w = self.client.get(reverse('kpi:hier_painel'), {**base, 'visao': 'semana'}).context['serie']['tabela']
        self.assertEqual(len(w), 12)
        self.assertRegex(w[-1]['faixa'], r'^\d\d/\d\d/\d\d a \d\d/\d\d/\d\d$')
        self.assertRegex(w[-1]['rotulo'], r'^S\d\d$')

    def test_visao_por_dia_e_por_semana_usa_movimentos(self):
        cod = HierCodigo.objects.create(codigo=3989, item=self.pads)
        HierMovimento.objects.create(codigo=cod, data=date(2026, 10, 5), quantidade=Decimal('3'), tipo='UTILIZACOES')
        HierMovimento.objects.create(codigo=cod, data=date(2026, 10, 6), quantidade=Decimal('2'), tipo='PERDAS')
        HierMovimento.objects.create(codigo=cod, data=date(2026, 10, 7), quantidade=Decimal('9'), tipo='DEVOLUCAO')
        base = {'kpi': self.kpi.pk, 'item': self.pads.pk, 'mes': '2026-10'}
        s = self.client.get(reverse('kpi:hier_painel'), {**base, 'visao': 'dia'}).context['serie']
        self.assertEqual(len(s['labels']), 31)
        self.assertEqual((s['valores'][4], s['valores'][5], s['valores'][6]), (3.0, 2.0, 0.0))
        self.assertAlmostEqual(s['metas'][0], 10 / 31, places=2)
        s = self.client.get(reverse('kpi:hier_painel'), {**base, 'visao': 'semana'}).context['serie']
        self.assertEqual(len(s['labels']), 12)
        self.assertIn(5.0, s['valores'])  # semana de 05/10: 3 + 2
        s = self.client.get(reverse('kpi:hier_painel'), {**base, 'visao': 'invalida'}).context['serie']
        self.assertEqual(len(s['labels']), 12)  # cai no mês a mês
        self.assertEqual(s['labels'][-1], '10/2026')

    def test_sentido_da_meta(self):
        self.pads.meta = Decimal('10')
        self.pads.sentido = '>='
        self.pads.save()
        self.assertIs(self.pads.atingiu(Decimal('12')), True)
        self.assertIs(self.pads.atingiu(Decimal('8')), False)
        self.pads.sentido = '<'
        self.assertIs(self.pads.atingiu(Decimal('10')), False)
        self.pads.sentido = '='
        self.assertIs(self.pads.atingiu(Decimal('10')), True)

    def test_telas_abrem(self):
        for nome in ('hier_cadastro', 'hier_importar', 'hier_codigos', 'hier_painel'):
            self.assertEqual(self.client.get(reverse(f'kpi:{nome}')).status_code, 200, nome)
        HierSetor.objects.all().delete()
        self.assertEqual(self.client.get(reverse('kpi:hier_painel')).status_code, 200)


class ImportacaoInsumosTests(InsumosBase):
    def linhas(self):
        return [
            _linha(3989, 'ESPONJA CLIP 50', 2, 'UTILIZAÇOES', SERIAL_2026_10_05, ident=100),
            _linha(3989, 'ESPONJA CLIP 50', 2, 'UTILIZAÇOES', SERIAL_2026_10_05, ident=100),   # repetida de verdade
            _linha(3989, 'ESPONJA CLIP 50', 4, 'UTILIZAÇOES', SERIAL_2026_10_20, ident=101),
            _linha(3989, 'ESPONJA CLIP 50', 1, 'DEVOLUÇAO', SERIAL_2026_10_20, 'MOV. ESTOQUE', ident=102),
            _linha(3993, 'ESPONJA CLIP 55', 3, 'PERDAS', SERIAL_2026_11_02, 'MOV. ESTOQUE', ident=103),
            _linha(2906, 'ALCOOL 70%', 1.5, 'UTILIZAÇOES', SERIAL_2026_10_05, ident=104),
        ]

    def vincular_pads(self):
        for n in (3989, 3993):
            HierCodigo.objects.update_or_create(codigo=n, defaults={'item': self.pads})

    def test_interpreta_o_formato_enxuto_e_o_formatado_igualmente(self):
        enxuto = insumos.interpretar(self.linhas())['registros']
        fmt = insumos.interpretar(_formatado({'POLIDORA DLP': self.linhas()[:5], 'GERAL': self.linhas()[5:]}))['registros']
        self.assertEqual(len(enxuto), len(fmt), 6)
        chave = lambda r: (r['codigo'], r['data'], r['quantidade'], r['tipo'], r['identif'])
        self.assertEqual(sorted(map(chave, enxuto)), sorted(map(chave, fmt)))
        self.assertEqual({r['familia'] for r in fmt if r['codigo'] == 3989}, {'POLIDORA DLP'})
        self.assertEqual(enxuto[0]['tipo'], 'UTILIZACOES')

    def test_le_xlsx_pelo_leitor_de_arquivos(self):
        linhas, datemode = insumos.ler_linhas(_xlsx(self.linhas()), 'r.xlsx')
        self.assertEqual(len(insumos.interpretar(linhas, datemode)['registros']), 6)
        with self.assertRaises(insumos.ErroImportacao):
            insumos.ler_linhas(b'isto nao e planilha')

    def test_importa_vincula_e_calcula_o_consumo_mensal(self):
        self.vincular_pads()
        resumo = self.importar(self.linhas())
        self.assertEqual((resumo['lidas'], resumo['adicionadas'], resumo['codigos_novos']), (6, 6, 1))  # 3989 e 3993 já existiam (vinculados)
        out =HierConsumo.objects.get(item=self.pads, periodo=date(2026, 10, 31))
        self.assertEqual((out.valor, out.origem), (Decimal('8.00'), 'importado'))  # 2+2+4, sem a devolução
        self.assertEqual(HierConsumo.objects.get(item=self.pads, periodo=date(2026, 11, 30)).valor, Decimal('3.00'))  # perdas contam
        self.assertEqual(resumo['sem_vinculo'], 1)  # o álcool (2906) não foi vinculado
        cod = HierCodigo.objects.get(codigo=3989)
        self.assertEqual((cod.descricao, cod.unidade), ('ESPONJA CLIP 50 / REF3989', 'UN'))

    def test_reimportar_nao_duplica_mas_traz_o_que_faltava(self):
        self.vincular_pads()
        self.importar(self.linhas())
        again = self.importar(self.linhas())
        self.assertEqual((again['adicionadas'], again['ja_existiam']), (0, 6))
        self.assertEqual(HierMovimento.objects.count(), 6)
        extra = self.linhas() + [_linha(3989, 'ESPONJA CLIP 50', 6, 'UTILIZAÇOES', SERIAL_2026_10_20, ident=200)]
        self.assertEqual(self.importar(extra)['adicionadas'], 1)
        self.assertEqual(HierConsumo.objects.get(item=self.pads, periodo=date(2026, 10, 31)).valor, Decimal('14.00'))

    def test_vincular_depois_recalcula_sem_reimportar_e_fator_converte(self):
        self.importar(self.linhas())
        self.assertFalse(HierConsumo.objects.exists())
        ids = list(HierCodigo.objects.filter(codigo__in=[2906]).values_list('pk', flat=True))
        self.client.post(reverse('kpi:hier_codigos_acao'), {'acao': 'vincular', 'item': self.liquido.pk, 'sel': ids})
        self.assertEqual(HierConsumo.objects.get(item=self.liquido).valor, Decimal('1.50'))
        cod = HierCodigo.objects.get(codigo=2906)
        self.client.post(reverse('kpi:hier_codigos_acao'), {'acao': 'fatores', 'sel': [cod.pk], f'fator_{cod.pk}': '2'})
        cod.refresh_from_db()
        self.assertEqual(cod.fator, 2)
        self.assertEqual(HierConsumo.objects.get(item=self.liquido).valor, Decimal('1.50'))  # consumo segue em unidades
        self.client.post(reverse('kpi:hier_codigos_acao'), {'acao': 'desvincular', 'sel': [cod.pk]})
        self.assertFalse(HierConsumo.objects.filter(item=self.liquido).exists())

    def test_lancamento_manual_prevalece_sobre_o_importado(self):
        self.vincular_pads()
        self.importar(self.linhas())
        self.client.post(reverse('kpi:hier_lancar'), {'mes': '2026-10', f'valor_{self.pads.pk}': '8'})  # igual ao importado: não vira manual
        self.assertEqual(HierConsumo.objects.get(item=self.pads, periodo=date(2026, 10, 31)).origem, 'importado')
        self.client.post(reverse('kpi:hier_lancar'), {'mes': '2026-10', f'valor_{self.pads.pk}': '20'})
        self.importar(self.linhas() + [_linha(3989, 'ESPONJA CLIP 50', 1, 'UTILIZAÇOES', SERIAL_2026_10_20, ident=300)])
        manual = HierConsumo.objects.get(item=self.pads, periodo=date(2026, 10, 31))
        self.assertEqual((manual.valor, manual.origem), (Decimal('20.00'), 'manual'))
        self.client.post(reverse('kpi:hier_consumo_excluir', args=[self.pads.pk]), {'mes': '2026-10'})
        self.assertEqual(HierConsumo.objects.get(item=self.pads, periodo=date(2026, 10, 31)).valor, Decimal('9.00'))  # volta o importado

    def test_importar_pela_tela(self):
        self.vincular_pads()
        arq = SimpleUploadedFile('Report.xlsx', _xlsx(self.linhas()))
        r = self.client.post(reverse('kpi:hier_importar'), {'arquivo': arq})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['resumo']['adicionadas'], 6)
        r = self.client.post(reverse('kpi:hier_importar'), {'arquivo': SimpleUploadedFile('x.xlsx', b'lixo')})
        self.assertIsNone(r.context['resumo'])
        r = self.client.get(reverse('kpi:hier_codigos'), {'status': 'pendente', 'q': '2906'})
        self.assertEqual(r.context['total'], 1)

    def test_migracao_de_dados_nao_e_necessaria_para_banco_novo(self):
        # a subcategoria "Geral" só nasce da migração quando já havia itens soltos na categoria
        self.assertFalse(HierSubcategoria.objects.filter(nome='Geral').exists())
