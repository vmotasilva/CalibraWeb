import csv
from pathlib import Path

CSV_ORIGINAL = Path('Relatorio_de_Lista_Mestra_Selecao_adaptado.csv')
CSV_TEMPLATE = Path('Relatorio_de_Lista_Mestra_Selecao_template_final.csv')

COLUNAS_TEMPLATE = [
    'no', 'codigo', 'nome', 'descricao', 'pasta', 'classificacao', 'autor',
    'numero_revisao', 'ultima_revisao', 'data_aprovacao', 'proxima_revisao',
    'data_validade', 'documentos_controlados', 'matriz', 'sub_area'
]

# Mapeamento do arquivo adaptado para o template final
MAP_ORIGEM = {
    'no': 'no',
    'codigo': 'codigo',
    'nome': 'titulo',
    'descricao': 'descricao',
    'pasta': 'pasta',
    'classificacao': 'tipo',
    'autor': '',  # Não existe no adaptado
    'numero_revisao': 'revisao',
    'ultima_revisao': 'data_revisao',
    'data_aprovacao': 'data_aprovacao',
    'proxima_revisao': 'proxima_revisao',
    'data_validade': 'data_validade',
    'documentos_controlados': 'documentos_controlados',
    'matriz': '',  # Não existe no adaptado
    'sub_area': ''  # Não existe no adaptado
}

def gerar_template_final():
    with open(CSV_ORIGINAL, encoding='utf-8') as fin, open(CSV_TEMPLATE, 'w', encoding='utf-8', newline='') as fout:
        reader = csv.DictReader(fin, delimiter=';')
        writer = csv.DictWriter(fout, fieldnames=COLUNAS_TEMPLATE, delimiter=';')
        writer.writeheader()
        for row in reader:
            nova = {}
            for col in COLUNAS_TEMPLATE:
                origem = MAP_ORIGEM.get(col, '')
                if origem:
                    nova[col] = row.get(origem, '').strip()
                else:
                    nova[col] = ''
            writer.writerow(nova)
    print(f'Template final gerado em: {CSV_TEMPLATE.resolve()}')

if __name__ == '__main__':
    gerar_template_final()
