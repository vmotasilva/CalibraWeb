"""
Script para validar a importação dos dados no Appwrite Database.
- Lista todas as collections e conta o número de documentos em cada uma.
- Requer: appwrite (pip install appwrite)
- Configure as variáveis de ambiente APPWRITE_ENDPOINT, APPWRITE_PROJECT, APPWRITE_API_KEY, APPWRITE_DATABASE_ID
"""
import os
from appwrite.client import Client
from appwrite.services.databases import Databases

from dotenv import load_dotenv
load_dotenv()

APPWRITE_ENDPOINT = os.getenv('APPWRITE_ENDPOINT')
APPWRITE_PROJECT = os.getenv('APPWRITE_PROJECT')
APPWRITE_API_KEY = os.getenv('APPWRITE_API_KEY')
APPWRITE_DATABASE_ID = os.getenv('APPWRITE_DATABASE_ID', 'default')

client = Client()
client.set_endpoint(APPWRITE_ENDPOINT)
client.set_project(APPWRITE_PROJECT)
client.set_key(APPWRITE_API_KEY)
db = Databases(client)

def validate_collections():
    res = db.list_collections(database_id=APPWRITE_DATABASE_ID)
    collections = res.collections if hasattr(res, 'collections') else res.get('collections', [])
    for collection in collections:
        if hasattr(collection, 'to_dict'):
            c_dict = collection.to_dict()
        else:
            c_dict = collection
            
        collection_id = c_dict.get('$id') or c_dict.get('id')
        name = c_dict.get('name')
        
        docs_res = db.list_documents(database_id=APPWRITE_DATABASE_ID, collection_id=collection_id)
        if hasattr(docs_res, 'to_dict'):
            d_dict = docs_res.to_dict()
        else:
            d_dict = docs_res
            
        print(f"Collection: {name} (ID: {collection_id}) - {d_dict.get('total', 0)} documentos")

if __name__ == '__main__':
    validate_collections()
