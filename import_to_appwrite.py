"""
Script para importar dados JSON exportados do Django para o Appwrite Database.
- Requer: appwrite (pip install appwrite)
- Configure as variáveis de ambiente APPWRITE_ENDPOINT, APPWRITE_PROJECT, APPWRITE_API_KEY
- Ajuste os nomes das collections conforme necessário.
"""
import os
import json
from appwrite.client import Client
from appwrite.services.databases import Databases

# Configurações do Appwrite
APPWRITE_ENDPOINT = os.getenv('APPWRITE_ENDPOINT')
APPWRITE_PROJECT = os.getenv('APPWRITE_PROJECT')
APPWRITE_API_KEY = os.getenv('APPWRITE_API_KEY')
APPWRITE_DATABASE_ID = os.getenv('APPWRITE_DATABASE_ID', 'default')  # Ajuste se necessário

client = Client()
client.set_endpoint(APPWRITE_ENDPOINT)
client.set_project(APPWRITE_PROJECT)
client.set_key(APPWRITE_API_KEY)
db = Databases(client)

# Mapeamento: nome do arquivo JSON -> nome da collection no Appwrite
MAPPING = {
    'acoes.json': 'acoes',
    'auditoria.json': 'auditoria',
    'core.json': 'core',
    # Adicione outros apps conforme necessário
}

def import_json_to_appwrite(json_file, collection_id):
    with open(json_file, encoding='utf-8') as f:
        data = json.load(f)
    for obj in data:
        fields = obj['fields']
        # O id pode ser usado como document_id se necessário
        db.create_document(
            database_id=APPWRITE_DATABASE_ID,
            collection_id=collection_id,
            document_id='unique()',
            data=fields
        )
    print(f"Importado {len(data)} registros para {collection_id}")

if __name__ == '__main__':
    for json_file, collection_id in MAPPING.items():
        if os.path.exists(json_file):
            import_json_to_appwrite(json_file, collection_id)
        else:
            print(f"Arquivo {json_file} não encontrado.")
