import os
import uuid
from django.core.management.base import BaseCommand
from django.apps import apps
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.exception import AppwriteException
from config import settings
from datetime import datetime, date, time

from dotenv import load_dotenv

class Command(BaseCommand):
    help = 'Migrates data from PostgreSQL to Appwrite'

    def handle(self, *args, **kwargs):
        load_dotenv()
        endpoint = os.getenv('APPWRITE_ENDPOINT')
        project = os.getenv('APPWRITE_PROJECT')
        api_key = os.getenv('APPWRITE_API_KEY')
        database_id = os.getenv('APPWRITE_DATABASE_ID', 'default')

        client = Client()
        client.set_endpoint(endpoint)
        client.set_project(project)
        client.set_key(api_key)

        db = Databases(client)

        # Get all models
        models = apps.get_models()
        self.stdout.write("Iniciando migração de dados para o Appwrite...")

        for model in models:
            app_label = model._meta.app_label
            model_name = model._meta.model_name
            
            # Skip django core models and external libraries
            if app_label in ['admin', 'auth', 'contenttypes', 'sessions', 'auditlog', 'axes']:
                continue

            collection_id = f"{app_label}_{model_name}"
            
            try:
                # Check if collection exists
                db.get_collection(database_id, collection_id)
            except AppwriteException as e:
                self.stdout.write(self.style.WARNING(f"Coleção {collection_id} não encontrada. Pulando..."))
                continue

            self.stdout.write(f"Migrando dados para: {collection_id}")
            
            try:
                queryset = model.objects.all()
                total = queryset.count()
                self.stdout.write(f"Total de registros: {total}")
                
                # Fetch objects into memory to catch errors early
                items = list(queryset)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Erro ao acessar {collection_id}: {e}"))
                from django.db import connection
                connection.rollback()
                continue
            
            success_count = 0
            error_count = 0
            
            for item in items:
                data = {}
                for field in model._meta.get_fields():
                    if field.is_relation and field.many_to_many:
                        continue # Skip M2M for now
                    
                    if hasattr(item, field.name):
                        value = getattr(item, field.name)
                        
                        # Handle foreign keys by getting their string representation or ID
                        if field.is_relation and field.many_to_one:
                            if value is not None:
                                data[field.name] = str(value.pk) if hasattr(value, 'pk') else str(value)
                            else:
                                data[field.name] = None
                        elif isinstance(value, datetime):
                            data[field.name] = value.isoformat()
                        elif isinstance(value, date):
                            data[field.name] = value.isoformat()
                        elif isinstance(value, time):
                            data[field.name] = value.isoformat()
                        elif isinstance(value, uuid.UUID):
                            data[field.name] = str(value)
                        else:
                            data[field.name] = value

                # Filter out None values to let Appwrite use defaults, and empty dicts
                data = {k: v for k, v in data.items() if v is not None}
                
                # Document ID
                doc_id = str(item.pk)
                # Appwrite max document ID length is 36 chars. If longer, generate new or truncate.
                # However, UUID is 36 chars. Integer is much less.
                if len(doc_id) > 36:
                    doc_id = doc_id[:36]
                    
                # Appwrite doc ids must contain only [a-zA-Z0-9._-] and not start with special char
                # If pk is integer, make sure it's a valid string. If UUID, remove dashes or keep if valid.
                import re
                doc_id = re.sub(r'[^a-zA-Z0-9.\-_]', '_', doc_id)
                if not doc_id[0].isalnum():
                    doc_id = 'id_' + doc_id

                try:
                    # Attempt to create or update
                    try:
                        db.create_document(database_id, collection_id, doc_id, data)
                        success_count += 1
                    except AppwriteException as create_e:
                        if create_e.code == 409: # Already exists
                            db.update_document(database_id, collection_id, doc_id, data)
                            success_count += 1
                        else:
                            raise create_e
                except AppwriteException as e:
                    error_count += 1
                    self.stdout.write(self.style.ERROR(f"  Erro ao migrar item {doc_id}: {e.message}"))
                    
            self.stdout.write(self.style.SUCCESS(f"  Sucesso: {success_count} | Erros: {error_count}"))

        self.stdout.write(self.style.SUCCESS("Migração de dados finalizada!"))
