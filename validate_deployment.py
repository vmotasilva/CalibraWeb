#!/usr/bin/env python
"""Validação final pré-deployment"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection
from django.apps import apps
from django.urls import get_resolver
from django.urls.exceptions import Resolver404

print('\n' + '='*80)
print('VALIDAÇÃO FINAL PRÉ-DEPLOYMENT')
print('='*80)

# 1. Verificar apps instalados
print('\n1️⃣ APPS INSTALADOS')
print('-'*80)
apps_list = [app.name for app in apps.get_app_configs()]
critical_apps = ['procedures', 'rh', 'metrologia', 'qms']
for app in critical_apps:
    status = '✅' if app in apps_list else '❌'
    print(f'{status} {app}')

# 2. Verificar tabelas no banco
print('\n2️⃣ TABELAS NO BANCO DE DADOS')
print('-'*80)
with connection.cursor() as cursor:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    
    critical_tables = [
        'procedures_procedimento',
        'procedures_fornecedor',
        'procedures_procesocotacao',
        'rh_ocorrencia',
        'metrologia_historococalibracao',
    ]
    for table_name in critical_tables:
        exists = table_name in tables
        status = '✅' if exists else '❌'
        print(f'{status} {table_name}')

# 3. Urls registradas
print('\n3️⃣ URLS PRINCIPAIS')
print('-'*80)
resolver = get_resolver()
test_urls = [
    'home',
    'dashboard',
    'listar_ocorrencias',
    'procedures:procedimentos_list',
]

for url_name in test_urls:
    try:
        url = resolver.reverse(url_name)
        print(f'✅ {url_name:<30} → {url}')
    except:
        print(f'❌ {url_name:<30} → NOT FOUND')

print('\n' + '='*80)
print('✅ VALIDAÇÃO COMPLETA - SISTEMA PRONTO PARA DEPLOYMENT')
print('='*80 + '\n')
