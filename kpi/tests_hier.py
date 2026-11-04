import io
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from openpyxl import Workbook

from kpi import insumos
from kpi.models import (HierCategoria, HierCodigo, HierConsumo, HierItem, HierMovimento, HierSetor,
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
        self.assertEqual(HierConsumo.objects.get(item=self.liquido).valor, Decimal('3.00'))
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
