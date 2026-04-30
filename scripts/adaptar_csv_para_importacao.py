import csv
from pathlib import Path

# Caminhos
CSV_ORIGINAL = Path('Relatorio_de_Lista_Mestra_Selecao.csv')
CSV_ADAPTADO = Path('Relatorio_de_Lista_Mestra_Selecao_adaptado.csv')

# Mapeamento: CSV original -> colunas esperadas pelo sistema
COL_MAP = {
    'Text10': 'codigo',
    'Text11': 'titulo',
    'Text14': 'tipo',  # ou classificaçao, mas o sistema espera 'tipo'
    'Text16': 'revisao',
    'Text18': 'data_revisao',
    'Text63': 'data_aprovacao',
    'Text31': 'numero',
    'Text12': 'descricao',
    'Text22': 'setor',
    'Text15': 'elaborador',
    'Text28': 'proxima_revisao',
    'Text25': 'data_validade',
    'Text23': 'documentos_controlados',
}

# Colunas obrigatórias para o sistema importar
COLUNAS_SAIDA = [
    'codigo', 'titulo', 'tipo', 'revisao', 'data_revisao', 'data_aprovacao',
    'numero', 'descricao', 'setor', 'elaborador', 'proxima_revisao', 'data_validade', 'documentos_controlados'
]

def adaptar_csv():
    with open(CSV_ORIGINAL, encoding='utf-8') as fin, open(CSV_ADAPTADO, 'w', encoding='utf-8', newline='') as fout:
        reader = csv.DictReader(fin, delimiter=';')
        writer = csv.DictWriter(fout, fieldnames=COLUNAS_SAIDA, delimiter=';')
        writer.writeheader()
        for row in reader:
            if not row.get('Text10') or not row.get('Text11'):
                continue
            nova = {out: row.get(inp, '').strip() for inp, out in COL_MAP.items()}
            writer.writerow(nova)
    print(f'Arquivo adaptado salvo em: {CSV_ADAPTADO.resolve()}')

if __name__ == '__main__':
    adaptar_csv()
