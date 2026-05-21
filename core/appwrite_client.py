"""
Configuração do cliente Appwrite para uso no backend Django.
Coloque este arquivo em core/appwrite_client.py e use em seus serviços.
"""
import os
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.services.account import Account
from appwrite.services.storage import Storage

APPWRITE_ENDPOINT = os.getenv('APPWRITE_ENDPOINT')
APPWRITE_PROJECT = os.getenv('APPWRITE_PROJECT')
APPWRITE_API_KEY = os.getenv('APPWRITE_API_KEY')
APPWRITE_DATABASE_ID = os.getenv('APPWRITE_DATABASE_ID', 'default')

client = Client()

if APPWRITE_ENDPOINT:
    client.set_endpoint(APPWRITE_ENDPOINT)
if APPWRITE_PROJECT:
    client.set_project(APPWRITE_PROJECT)
if APPWRITE_API_KEY:
    client.set_key(APPWRITE_API_KEY)


db = Databases(client)
account = Account(client)
storage = Storage(client)

# Exemplo de uso:
# from core.appwrite_client import db, APPWRITE_DATABASE_ID
# db.list_documents(database_id=APPWRITE_DATABASE_ID, collection_id='acoes')
