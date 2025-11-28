import pandas as pd

# Arquivo de entrada e saída
ARQUIVO_ENTRADA = 'c:/CalibraWeb/procedimentos_export (1).csv'
ARQUIVO_SAIDA = 'c:/CalibraWeb/procedimentos_para_importar.csv'

# Ordem e nomes das colunas do template
colunas_template = [
    'no', 'codigo', 'nome', 'descricao', 'pasta', 'classificacao', 'autor',
    'numero_revisao', 'ultima_revisao', 'data_aprovacao', 'proxima_revisao',
    'data_validade', 'documentos_controlados', 'matriz', 'sub_area'
]

# Mapeamento de nomes do export para o template
mapa_colunas = {
    'CODIGO': 'codigo',
    'NOME': 'nome',
    'CLASSIFICACAO': 'classificacao',
    'NUMERO_REVISAO': 'numero_revisao',
    'ULTIMA_REVISAO': 'ultima_revisao',
    'DATA_APROVACAO': 'data_aprovacao',
    'PROXIMA_REVISAO': 'proxima_revisao',
    'DATA_VALIDADE': 'data_validade',
    'PASTA': 'pasta',
    'AUTOR': 'autor',
    'DOCUMENTOS_CONTROLADOS': 'documentos_controlados',
    'MATRIZ': 'matriz',
    'SUB_AREA': 'sub_area',
}

def adaptar_csv():
    # Lê o CSV exportado
    df = pd.read_csv(ARQUIVO_ENTRADA, sep=';', dtype=str)
    # Renomeia as colunas
    df = df.rename(columns=mapa_colunas)
    # Adiciona coluna descricao vazia
    df['descricao'] = ''
    # Adiciona coluna no sequencial
    df['no'] = range(1, len(df) + 1)
    # Garante que todas as colunas do template existem
    for col in colunas_template:
        if col not in df.columns:
            df[col] = ''
    # Reordena as colunas
    df = df[colunas_template]
    # Salva o novo CSV
    df.to_csv(ARQUIVO_SAIDA, sep=';', index=False)
    print(f'Arquivo adaptado salvo como: {ARQUIVO_SAIDA}')

if __name__ == '__main__':
    adaptar_csv()
