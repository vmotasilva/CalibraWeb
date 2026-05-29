"""
Configuração do cliente Appwrite para uso no backend Django.
Coloque este arquivo em core/appwrite_client.py e use em seus serviços.
"""
import os
import requests
import requests.api
import appwrite.client
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.services.account import Account
from appwrite.services.storage import Storage

# Monkey-patch para corrigir o bug do SDK do Appwrite (que envia data={} em GET),
# evitando o erro 400 "request cannot have request body" no Appwrite Cloud.
_original_request = requests.request

def _patched_request(method, url, **kwargs):
    if method.lower() == 'get' and kwargs.get('data') == {}:
        kwargs['data'] = None
    return _original_request(method, url, **kwargs)

requests.request = _patched_request
requests.api.request = _patched_request
appwrite.client.requests.request = _patched_request

APPWRITE_ENDPOINT = (os.getenv('APPWRITE_ENDPOINT') or '').strip()
APPWRITE_PROJECT = (os.getenv('APPWRITE_PROJECT') or '').strip()
APPWRITE_API_KEY = (os.getenv('APPWRITE_API_KEY') or '').strip()
APPWRITE_DATABASE_ID = (os.getenv('APPWRITE_DATABASE_ID') or '').strip()
if not APPWRITE_DATABASE_ID:
    APPWRITE_DATABASE_ID = 'default'

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
