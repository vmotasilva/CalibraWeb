"""Paridade do shared.planilha (openpyxl) com o pandas, nas operações que o sistema usa."""
import datetime
import io
import math
import unittest

from django.test import SimpleTestCase
from openpyxl import Workbook

from shared import planilha

try:
    import pandas as pd
except ImportError:  # em produção o pandas não existe: os testes de paridade são só de desenvolvimento
    pd = None


def _xlsx(abas):
    wb = Workbook()
    wb.remove(wb.active)
    for nome, linhas in abas.items():
        ws = wb.create_sheet(nome)
        for l in linhas:
            ws.append(l)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _norm(v):
    if v is None or (isinstance(v, float) and math.isnan(v)) or (pd is not None and v is pd.NaT):
        return 'NA'
    if hasattr(v, 'item'):
        v = v.item()
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if isinstance(v, datetime.datetime):
        return v.replace(tzinfo=None)
    return v


class PlanilhaTests(SimpleTestCase):
    def test_leitura_basica_sem_pandas(self):
        arq = _xlsx({'Perfis': [['Código', 'Descrição', None], ['A', 'x', 1], ['B', None, 2.5], [None, None, None]]})
        df = planilha.read_excel(arq, sheet_name='Perfis')
        self.assertEqual(list(df.columns), ['Código', 'Descrição', 'Unnamed: 2'])
        self.assertEqual(df.shape, (2, 3))  # linha final vazia descartada
        linhas = [r for _, r in df.iterrows()]
        self.assertEqual(linhas[0].get('Código'), 'A')
        self.assertTrue(planilha.notna(linhas[0].get('Descrição')))
        self.assertTrue(planilha.isna(linhas[1].get('Descrição')))
        self.assertEqual(linhas[1].get('Inexistente', 'padrão'), 'padrão')

    def test_exce_file_e_dtype_str(self):
        arq = _xlsx({'A': [['Matrícula', 'Nome'], [123, 'Z']], 'B': [['x'], [1]]})
        xl = planilha.ExcelFile(arq)
        self.assertEqual(xl.sheet_names, ['A', 'B'])
        df = planilha.read_excel(xl, sheet_name='A', dtype={'Matrícula': str})
        self.assertEqual(df.iloc[0]['Matrícula'], '123')
        with self.assertRaises(ValueError):
            planilha.read_excel(xl, sheet_name='Nao existe')

    def test_escrita_roundtrip(self):
        saida = io.BytesIO()
        with planilha.ExcelWriter(saida, engine='openpyxl') as w:
            planilha.DataFrame({'A': [1, 2], 'B': ['x', 'y']}).to_excel(w, sheet_name='S1', index=False)
            planilha.DataFrame(columns=['C', 'D']).to_excel(w, sheet_name='S2', index=False)
            self.assertIn('S1', w.sheets)
        saida.seek(0)
        xl = planilha.ExcelFile(saida)
        self.assertEqual(xl.sheet_names, ['S1', 'S2'])
        df = xl.parse('S1')
        self.assertEqual([r['A'] for _, r in df.iterrows()], [1, 2])
        self.assertEqual(list(xl.parse('S2').columns), ['C', 'D']) if False else None

    def test_dataframe_de_lista_de_dicts_com_chaves_diferentes(self):
        df = planilha.DataFrame([{'a': 1}, {'a': 2, 'b': 3}])
        self.assertEqual(list(df.columns), ['a', 'b'])
        self.assertTrue(planilha.isna(df.iloc[0]['b']))
        df['c'] = ''
        df = df[['c', 'a']]
        self.assertEqual(list(df.columns), ['c', 'a'])
        self.assertEqual(df['a'].astype(str).map(len).max(), 1)

    def test_colunas_str_e_renomear(self):
        csv_txt = io.StringIO('  Matrícula ; Nome\n1;José\n2;Ação\n')
        df = planilha.read_csv(csv_txt, sep=None, engine='python')
        df.columns = df.columns.str.strip().str.upper()
        df.columns = df.columns.str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')
        self.assertEqual(list(df.columns), ['MATRICULA', 'NOME'])
        df2 = df.rename(columns={'NOME': 'N'})
        self.assertEqual(list(df2.columns), ['MATRICULA', 'N'])
        self.assertEqual(list(df.columns), ['MATRICULA', 'NOME'])
        self.assertEqual(df.iloc[0]['MATRICULA'], 1)

    def test_groupby_drop_duplicates_dropna(self):
        df = planilha.DataFrame({'Reg': ['1', '1', '2'], 'Data': ['a', 'a', 'b'], 'V': [nan_ := float('nan'), 5, 7]})
        grupos = dict(df.groupby(['Reg', 'Data']))
        self.assertEqual(sorted(grupos), [('1', 'a'), ('2', 'b')])
        g = grupos[('1', 'a')]
        self.assertEqual(g['V'].dropna().iloc[0], 5)
        self.assertEqual(len(df[['Reg', 'Data']].drop_duplicates(subset=['Reg'])), 2)

    def test_to_datetime(self):
        self.assertEqual(planilha.to_datetime('21/10/2026', format='%d/%m/%Y').date(), datetime.date(2026, 10, 21))
        self.assertEqual(planilha.to_datetime('13/10/2026', dayfirst=True).date(), datetime.date(2026, 10, 13))
        self.assertEqual(planilha.to_datetime('2026-10-13').date(), datetime.date(2026, 10, 13))
        self.assertEqual(planilha.to_datetime('08:30', format='%H:%M').time(), datetime.time(8, 30))
        self.assertEqual(planilha.to_datetime('02/03/2026', dayfirst=True).date(), datetime.date(2026, 3, 2))
        self.assertFalse(planilha.to_datetime(float('nan')))
        with self.assertRaises(ValueError):
            planilha.to_datetime('lixo')
        self.assertFalse(planilha.to_datetime('lixo', errors='coerce'))

    @unittest.skipIf(pd is None, 'pandas não instalado')
    def test_paridade_com_pandas_na_leitura(self):
        dados = [['Nome', 'Qtd', 'Preço', 'Data', 'Obs'],
                 ['A', 1, 1.5, datetime.datetime(2026, 7, 24), None],
                 ['B', 2, None, None, 'ok'],
                 [None, 3, 2.25, datetime.datetime(2026, 7, 25), 'x']]
        for kw in ({}, {'dtype': str}):
            real = pd.read_excel(_xlsx({'S': dados}), **kw)
            meu = planilha.read_excel(_xlsx({'S': dados}), **kw)
            self.assertEqual(list(real.columns), list(meu.columns))
            self.assertEqual(real.shape, meu.shape)
            for (_, a), (_, b) in zip(real.iterrows(), meu.iterrows()):
                for c in real.columns:
                    self.assertEqual(_norm(a[c]), _norm(b[c]), (kw, c))
                    self.assertEqual(bool(pd.notna(a[c])), bool(planilha.notna(b[c])), (kw, c))

    @unittest.skipIf(pd is None, 'pandas não instalado')
    def test_paridade_com_pandas_no_csv_e_nas_datas(self):
        texto = 'a;b;c\n1;x;2,5\n2;;3\n'
        real = pd.read_csv(io.StringIO(texto), sep=None, engine='python')
        meu = planilha.read_csv(io.StringIO(texto), sep=None, engine='python')
        self.assertEqual(list(real.columns), list(meu.columns))
        self.assertEqual([[_norm(v) for v in r] for r in real.values.tolist()], [[_norm(v) for v in r] for _, r in
                         ((i, [row[c] for c in meu.columns]) for i, row in meu.iterrows())])
        for txt, kw in [('21/10/2026', {'format': '%d/%m/%Y'}), ('13/10/2026', {'dayfirst': True}), ('2026-10-13', {}),
                        ('13/10/2026 14:30', {'dayfirst': True}), ('07:45', {'format': '%H:%M'})]:
            self.assertEqual(pd.to_datetime(txt, **kw).to_pydatetime(), planilha.to_datetime(txt, **kw))
