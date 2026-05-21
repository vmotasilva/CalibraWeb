"""
Script para configurar automaticamente o banco de dados, a coleção 'acoes'
e todos os seus atributos necessários no Appwrite.

Requisitos:
- pip install appwrite

Variáveis de ambiente requeridas:
- APPWRITE_ENDPOINT (ex: https://cloud.appwrite.io/v1)
- APPWRITE_PROJECT
- APPWRITE_API_KEY
- APPWRITE_DATABASE_ID (opcional, padrão 'default')
"""

import os
import sys
import time
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.exception import AppwriteException

# 1. Carregar variáveis de ambiente
from dotenv import load_dotenv
load_dotenv()

APPWRITE_ENDPOINT = os.getenv('APPWRITE_ENDPOINT')
APPWRITE_PROJECT = os.getenv('APPWRITE_PROJECT')
APPWRITE_API_KEY = os.getenv('APPWRITE_API_KEY')
APPWRITE_DATABASE_ID = os.getenv('APPWRITE_DATABASE_ID', 'default')

if not all([APPWRITE_ENDPOINT, APPWRITE_PROJECT, APPWRITE_API_KEY]):
    print("Erro: As variáveis de ambiente do Appwrite não estão configuradas completamente.")
    print("Certifique-se de definir: APPWRITE_ENDPOINT, APPWRITE_PROJECT e APPWRITE_API_KEY.")
    sys.exit(1)

# 2. Inicializar o cliente Appwrite
client = Client()
client.set_endpoint(APPWRITE_ENDPOINT)
client.set_project(APPWRITE_PROJECT)
client.set_key(APPWRITE_API_KEY)
db_service = Databases(client)

COLLECTION_ID = 'acoes'

# Definição dos atributos necessários para a coleção 'acoes'
ATTRIBUTES_DEFINITION = [
    # (Nome/Key, Tipo, Tamanho/Configuração, Requerido)
    ('numero_registro', 'string', 100, False),
    ('ano', 'integer', None, False),
    ('unidade', 'string', 100, False),
    ('titulo', 'string', 255, True),
    ('descricao', 'string', 5000, True),
    ('tipo', 'string', 50, True),
    ('tipo_solucao', 'string', 100, False),
    ('prioridade', 'string', 50, True),
    ('origem', 'string', 255, False),
    ('causa_raiz', 'string', 5000, False),
    ('status', 'string', 50, True),
    ('data_abertura', 'string', 50, False),
    ('data_vencimento', 'string', 50, True),
    ('data_conclusao', 'string', 50, False),
    ('criado_por', 'string', 255, False),
    ('responsavel', 'string', 255, False),
    ('responsavel_id', 'string', 255, False),
    ('acoes_status_resumo', 'string', 255, False),
]

def ensure_database():
    """Garante que a base de dados existe."""
    print(f"Verificando banco de dados '{APPWRITE_DATABASE_ID}'...")
    try:
        db_service.get(database_id=APPWRITE_DATABASE_ID)
        print(f"[OK] Banco de dados '{APPWRITE_DATABASE_ID}' ja existe.")
    except AppwriteException as e:
        if e.code == 404 or "not found" in str(e).lower():
            if APPWRITE_DATABASE_ID == 'default':
                print("Banco de dados 'default' deve ser criado no painel do Appwrite, ou use outro ID.")
                print("Tentando criar banco de dados 'default'...")
            try:
                db_service.create(database_id=APPWRITE_DATABASE_ID, name="CalibraWeb Database")
                print(f"[OK] Banco de dados '{APPWRITE_DATABASE_ID}' criado com sucesso.")
            except Exception as ex:
                print(f"Erro ao criar banco de dados: {ex}")
                print("Continuando mesmo assim, pois o banco pode ja existir ou estar disponivel.")
        else:
            print(f"Aviso ao verificar banco de dados: {e}")

def ensure_collection():
    """Garante que a colecao 'acoes' existe."""
    print(f"Verificando colecao '{COLLECTION_ID}'...")
    try:
        db_service.get_collection(database_id=APPWRITE_DATABASE_ID, collection_id=COLLECTION_ID)
        print(f"[OK] Colecao '{COLLECTION_ID}' ja existe.")
    except AppwriteException as e:
        if e.code == 404 or "not found" in str(e).lower():
            print(f"Colecao '{COLLECTION_ID}' nao encontrada. Criando...")
            try:
                db_service.create_collection(
                    database_id=APPWRITE_DATABASE_ID,
                    collection_id=COLLECTION_ID,
                    name="Acoes Corretivas"
                )
                print(f"[OK] Colecao '{COLLECTION_ID}' criada com sucesso.")
            except Exception as ex:
                print(f"Erro critico ao criar colecao: {ex}")
                sys.exit(1)
        else:
            print(f"Erro ao verificar colecao: {e}")
            sys.exit(1)

def get_existing_attributes():
    """Retorna um conjunto com as chaves dos atributos ja existentes."""
    try:
        res = db_service.list_attributes(database_id=APPWRITE_DATABASE_ID, collection_id=COLLECTION_ID)
        # Suporta tanto objetos com atributo .attributes quanto dicionarios
        attrs = res.attributes if hasattr(res, 'attributes') else res.get('attributes', [])
        return {attr['key'] if isinstance(attr, dict) else attr.key for attr in attrs}
    except Exception as e:
        print(f"Aviso ao listar atributos: {e}")
        return set()

def create_attributes():
    """Cria os atributos em falta na colecao."""
    existing = get_existing_attributes()
    created_any = False

    for key, attr_type, size, required in ATTRIBUTES_DEFINITION:
        if key in existing:
            print(f"  Attribute '{key}' ja existe. Ignorando.")
            continue

        print(f"  Criando atributo '{key}' ({attr_type})...")
        try:
            if attr_type == 'string':
                db_service.create_string_attribute(
                    database_id=APPWRITE_DATABASE_ID,
                    collection_id=COLLECTION_ID,
                    key=key,
                    size=size,
                    required=required
                )
            elif attr_type == 'integer':
                db_service.create_integer_attribute(
                    database_id=APPWRITE_DATABASE_ID,
                    collection_id=COLLECTION_ID,
                    key=key,
                    required=required
                )
            elif attr_type == 'boolean':
                db_service.create_boolean_attribute(
                    database_id=APPWRITE_DATABASE_ID,
                    collection_id=COLLECTION_ID,
                    key=key,
                    required=required
                )
            created_any = True
            print(f"  [OK] Comando enviado para criar atributo '{key}'.")
        except Exception as e:
            print(f"  [ERRO] Erro ao criar atributo '{key}': {e}")

    if created_any:
        print("\nProcessando criacao dos atributos no backend do Appwrite (isso e assincrono)...")
        # Loop para esperar todos os atributos ficarem disponiveis
        for i in range(30):
            sys.stdout.write(".")
            sys.stdout.flush()
            time.sleep(2)
            try:
                res = db_service.list_attributes(database_id=APPWRITE_DATABASE_ID, collection_id=COLLECTION_ID)
                attrs = res.attributes if hasattr(res, 'attributes') else res.get('attributes', [])
                all_available = True
                processing_keys = []
                for attr in attrs:
                    status = attr['status'] if isinstance(attr, dict) else attr.status
                    key = attr['key'] if isinstance(attr, dict) else attr.key
                    if status != 'available':
                        all_available = False
                        processing_keys.append(key)
                if all_available and len(attrs) >= len(ATTRIBUTES_DEFINITION):
                    print("\n[OK] Todos os atributos foram criados e estao disponiveis!")
                    break
                elif i == 29:
                    print(f"\nAviso: Alguns atributos ainda estao processando ou faltam ser criados: {processing_keys}")
            except Exception as e:
                pass
    else:
        print("Nenhum novo atributo precisou ser criado.")

if __name__ == '__main__':
    print("=== Configuracao de Schema do Appwrite ===")
    ensure_database()
    ensure_collection()
    create_attributes()
    print("=== Configuracao concluida! ===")
