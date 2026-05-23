import os
import time
from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import models
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.exception import AppwriteException
from dotenv import load_dotenv

class Command(BaseCommand):
    help = 'Sincroniza o schema do Django para o Appwrite (Fase 1: Coleções, Fase 2: Atributos)'

    def handle(self, *args, **options):
        load_dotenv()
        endpoint = os.getenv('APPWRITE_ENDPOINT')
        project = os.getenv('APPWRITE_PROJECT')
        api_key = os.getenv('APPWRITE_API_KEY')
        database_id = os.getenv('APPWRITE_DATABASE_ID', 'default')

        if not all([endpoint, project, api_key]):
            self.stdout.write(self.style.ERROR('Variáveis do Appwrite não configuradas.'))
            return

        client = Client()
        client.set_endpoint(endpoint).set_project(project).set_key(api_key)
        db = Databases(client)

        exclude_apps = ['admin', 'auth', 'contenttypes', 'sessions', 'phonenumber', 'otp_static', 'otp_totp']
        all_models = [m for m in apps.get_models() if m._meta.app_label not in exclude_apps]

        self.stdout.write(f'Encontrados {len(all_models)} models para sincronizar.')

        # Fase 1: Criar Coleções
        self.stdout.write('\n--- FASE 1: CRIANDO COLEÇÕES ---')
        for model in all_models:
            app_label = model._meta.app_label
            model_name = model._meta.model_name
            collection_id = f"{app_label}_{model_name}"[:36]
            collection_name = f"{app_label.capitalize()} - {model._meta.verbose_name.capitalize()}"[:128]

            try:
                db.get_collection(database_id, collection_id)
                self.stdout.write(f'Coleção já existe: {collection_id}')
            except AppwriteException as e:
                if e.code == 404:
                    try:
                        db.create_collection(
                            database_id=database_id,
                            collection_id=collection_id,
                            name=collection_name
                        )
                        self.stdout.write(self.style.SUCCESS(f'Coleção CRIADA: {collection_id}'))
                    except Exception as ex:
                        self.stdout.write(self.style.ERROR(f'Erro ao criar coleção {collection_id}: {ex}'))
                else:
                    self.stdout.write(self.style.ERROR(f'Erro ao buscar coleção {collection_id}: {e}'))

        # Fase 2: Criar Atributos
        self.stdout.write('\n--- FASE 2: CRIANDO ATRIBUTOS ---')
        for model in all_models:
            app_label = model._meta.app_label
            model_name = model._meta.model_name
            collection_id = f"{app_label}_{model_name}"[:36]

            # Verificar se a coleção existe
            try:
                db.get_collection(database_id, collection_id)
            except AppwriteException:
                continue

            # Appwrite limita chaves a 32 caracteres.
            # Também precisamos evitar atributos com nome "id" se quisermos, mas o Appwrite aceita atributos customizados normais.
            # O sistema nativamente tem "$id". O id do django será "django_id".
            
            for field in model._meta.get_fields():
                # Ignorar campos reversos sem nome de banco de dados e propriedades não-concretas
                if field.auto_created and not field.concrete and not isinstance(field, models.ManyToManyField):
                    continue
                
                if not hasattr(field, 'name'):
                    continue

                field_name = field.name[:32]
                
                if field.primary_key:
                    field_name = 'django_id'

                try:
                    self._create_attribute_for_field(db, database_id, collection_id, field, field_name)
                    # Dá um respiro pra API do Appwrite processar a criação de atributos
                    time.sleep(0.3) 
                except AppwriteException as e:
                    if e.code == 409: # Conflict - already exists
                        pass
                    else:
                        self.stdout.write(self.style.WARNING(f'  [Aviso] Erro ao criar atributo {field_name} em {collection_id}: {e}'))
            
            self.stdout.write(f'Atributos processados para: {collection_id}')

        self.stdout.write(self.style.SUCCESS('\nSincronização de schema finalizada!'))

    def _create_attribute_for_field(self, db, database_id, collection_id, field, field_name):
        # Simplificando required para evitar conflitos de default com o banco Appwrite
        required = False 
        array = False
        
        if isinstance(field, models.ManyToManyField):
            array = True

        if isinstance(field, (models.CharField, models.TextField, models.EmailField, models.URLField, models.FileField, models.ImageField, models.UUIDField, models.GenericIPAddressField, models.SlugField)):
            size = getattr(field, 'max_length', None)
            if not size or size > 10000:
                size = 10000 # Appwrite limit for strings if not specified carefully, though text can be larger. Let's use 10000.
            db.create_string_attribute(database_id, collection_id, field_name, size=size, required=required, array=array)
        
        elif isinstance(field, (models.IntegerField, models.SmallIntegerField, models.BigIntegerField, models.PositiveIntegerField, models.PositiveSmallIntegerField)):
            db.create_integer_attribute(database_id, collection_id, field_name, required=required, array=array)
            
        elif isinstance(field, (models.FloatField, models.DecimalField)):
            db.create_float_attribute(database_id, collection_id, field_name, required=required, array=array)
            
        elif isinstance(field, (models.BooleanField, models.NullBooleanField)):
            db.create_boolean_attribute(database_id, collection_id, field_name, required=required, array=array)
            
        elif isinstance(field, (models.DateTimeField, models.DateField, models.TimeField)):
            db.create_datetime_attribute(database_id, collection_id, field_name, required=required, array=array)
            
        elif isinstance(field, (models.ForeignKey, models.OneToOneField)):
            # Save ID as string (ou Integer, dependendo da PK, mas String é mais seguro para englobar UUIDs)
            db.create_string_attribute(database_id, collection_id, field_name, size=255, required=required, array=array)
        else:
            # Fallback for complex types or custom fields
            db.create_string_attribute(database_id, collection_id, field_name, size=5000, required=required, array=array)
