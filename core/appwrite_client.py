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

# Guardar referência ao requests.request original globalmente
_original_request = requests.request

def _patched_request(method, url, **kwargs):
    if method.lower() == 'get':
        # 1. Limpar data se for vazio ou dicionário vazio
        if 'data' in kwargs:
            if kwargs['data'] == {} or kwargs['data'] is None:
                kwargs['data'] = None
            else:
                kwargs['data'] = None
                
        # 2. Limpar files se for vazio ou dicionário vazio
        if 'files' in kwargs:
            if kwargs['files'] == {} or kwargs['files'] is None:
                kwargs['files'] = None
                
        # 3. Remover cabeçalho Content-Type (case-insensitive)
        headers = kwargs.get('headers')
        if headers:
            for k in list(headers.keys()):
                if k.lower() == 'content-type':
                    del headers[k]
                    
    return _original_request(method, url, **kwargs)

def patch_appwrite_requests():
    import sys
    
    # 1. Encontrar e patchear todos os módulos "requests" e "requests.api" em sys.modules
    for name, module in list(sys.modules.items()):
        if not module:
            continue
        
        # Patch na função request do módulo requests e requests.api (incluindo versões do _vendor)
        if name in ('requests', '_vendor.requests') or name.endswith('.requests'):
            if hasattr(module, 'request') and module.request != _patched_request:
                try:
                    module.request = _patched_request
                except Exception:
                    pass
                    
        if name in ('requests.api', '_vendor.requests.api') or name.endswith('.requests.api'):
            if hasattr(module, 'request') and module.request != _patched_request:
                try:
                    module.request = _patched_request
                except Exception:
                    pass
                    
        # 2. Encontrar e patchear a referência ao requests no appwrite.client
        if name in ('appwrite.client', '_vendor.appwrite.client') or name.endswith('.appwrite.client'):
            if hasattr(module, 'requests'):
                try:
                    module.requests.request = _patched_request
                except Exception:
                    pass

# Executar imediatamente ao importar
patch_appwrite_requests()

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
