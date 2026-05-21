"""
Script para importar dados de arquivos CSV (exportados do PostgreSQL Railway) para collections do Appwrite Database.
- Requer: appwrite (pip install appwrite)
- Requer: pandas (pip install pandas)
- Configure as variáveis de ambiente APPWRITE_ENDPOINT, APPWRITE_PROJECT, APPWRITE_API_KEY, APPWRITE_DATABASE_ID
- Ajuste o mapeamento de collections conforme necessário.
Coloque os arquivos CSV na pasta 'export_pg/'.
"""
import os
import pandas as pd
from appwrite.client import Client
from appwrite.services.databases import Databases

# Configurações do Appwrite
APPWRITE_ENDPOINT = os.getenv('APPWRITE_ENDPOINT')
APPWRITE_PROJECT = os.getenv('APPWRITE_PROJECT')
APPWRITE_API_KEY = os.getenv('APPWRITE_API_KEY')
APPWRITE_DATABASE_ID = os.getenv('APPWRITE_DATABASE_ID', 'default')

client = Client()
client.set_endpoint(APPWRITE_ENDPOINT)
client.set_project(APPWRITE_PROJECT)
client.set_key(APPWRITE_API_KEY)
db = Databases(client)


import glob
EXPORT_DIR = 'export_pg'

def import_csv_to_appwrite(csv_file, collection_id):
    df = pd.read_csv(os.path.join(EXPORT_DIR, csv_file))
    for _, row in df.iterrows():
        data = row.dropna().to_dict()
        db.create_document(
            database_id=APPWRITE_DATABASE_ID,
            collection_id=collection_id,
            document_id='unique()',
            data=data
        )
    print(f"Importado {len(df)} registros para {collection_id}")

if __name__ == '__main__':
    csv_files = glob.glob(os.path.join(EXPORT_DIR, '*.csv'))
    if not csv_files:
        print(f'Nenhum arquivo CSV encontrado em {EXPORT_DIR}/')
    for path in csv_files:
        csv_file = os.path.basename(path)
        collection_id = os.path.splitext(csv_file)[0]
        print(f'Importando {csv_file} para collection {collection_id}...')
        import_csv_to_appwrite(csv_file, collection_id)
