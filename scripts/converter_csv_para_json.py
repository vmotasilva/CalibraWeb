import csv
import json
from pathlib import Path

CSV_PATH = Path('Relatorio_de_Lista_Mestra_Selecao.csv')
JSON_PATH = Path('database/procedimentos_extraidos.json')

# Mapeamento das colunas do CSV para os campos do JSON
COL_MAP = {
    'Text31': 'numero',
    'Text10': 'codigo',
    'Text11': 'nome',
    'Text12': 'descricao',
    'Text22': 'pasta',
    'Text14': 'classificacao',
    'Text15': 'autor',
    'Text16': 'numero_revisao',
    'Text18': 'ultima_revisao',
    'Text63': 'data_aprovacao',
    'Text28': 'proxima_revisao',
    'Text25': 'data_validade',
    'Text23': 'documentos_controlados',
}

def converter_csv_para_json():
    procedimentos = []
    with open(CSV_PATH, encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        for row in reader:
            # Ignora linhas em branco ou incompletas
            if not row['Text10'] or not row['Text11']:
                continue
            proc = {json_key: row.get(csv_key, '').strip() for csv_key, json_key in COL_MAP.items()}
            procedimentos.append(proc)
    with open(JSON_PATH, 'w', encoding='utf-8') as jsonfile:
        json.dump(procedimentos, jsonfile, ensure_ascii=False, indent=2)
    print(f'Arquivo JSON salvo em: {JSON_PATH.resolve()}')

if __name__ == '__main__':
    converter_csv_para_json()
