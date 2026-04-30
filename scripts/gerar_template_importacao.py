import csv
from pathlib import Path

CSV_ORIGINAL = Path('Relatorio_de_Lista_Mestra_Selecao.csv')
CSV_TEMPLATE = Path('Relatorio_de_Lista_Mestra_Selecao_template.csv')

# Mapeamento: CSV original -> colunas do template
COL_MAP = {
    'Text10': 'codigo',
    'Text11': 'titulo',
    'Text16': 'revisao',
    'Text18': 'data_revisao',
    'Text63': 'data_aprovacao',
    'Text31': 'numero',
    'Text12': 'descricao',
    'Text28': 'proxima_revisao',
    'Text25': 'data_validade',
    'Text23': 'documentos_controlados',
}

# Colunas do template final
COLUNAS_SAIDA = [
    'codigo', 'titulo', 'tipo', 'revisao', 'data_revisao', 'data_aprovacao',
    'setor', 'area', 'elaborador', 'revisor', 'aprovador',
    'numero', 'descricao', 'proxima_revisao', 'data_validade', 'documentos_controlados'
]

def extrair_tipo(codigo):
    if codigo and '.' in codigo:
        return codigo.split('.')[0].strip().upper()
    return ''

def gerar_template():
    with open(CSV_ORIGINAL, encoding='utf-8') as fin, open(CSV_TEMPLATE, 'w', encoding='utf-8', newline='') as fout:
        reader = csv.DictReader(fin, delimiter=';')
        writer = csv.DictWriter(fout, fieldnames=COLUNAS_SAIDA, delimiter=';')
        writer.writeheader()
        for row in reader:
            if not row.get('Text10') or not row.get('Text11'):
                continue
            base = {out: row.get(inp, '').strip() for inp, out in COL_MAP.items()}
            base['tipo'] = extrair_tipo(base['codigo'])
            # Campos extras para preenchimento manual
            base['setor'] = ''
            base['area'] = ''
            base['elaborador'] = ''
            base['revisor'] = ''
            base['aprovador'] = ''
            writer.writerow(base)
    print(f'Template gerado em: {CSV_TEMPLATE.resolve()}')

if __name__ == '__main__':
    gerar_template()
