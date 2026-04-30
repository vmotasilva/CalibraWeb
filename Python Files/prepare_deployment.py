#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Celery Beat Railroad Deployment Automation
Automatiza o máximo possível do deploy no Railroad/Railway
"""
import os
import sys
import json
import subprocess

def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")

def print_success(text):
    """Print success message"""
    print(f"✓ {text}")

def print_error(text):
    """Print error message"""
    print(f"✗ {text}")

def print_warning(text):
    """Print warning message"""
    print(f"⚠ {text}")

def print_info(text):
    """Print info message"""
    print(f"• {text}")

def check_files_exist():
    """Verifica se todos os arquivos necessários existem"""
    print_header("VERIFICACAO 1: Arquivos Necessarios")
    
    required_files = {
        'Dockerfile.beat': 'Docker para Celery Beat',
        'entrypoint-beat.py': 'Script de inicializacao',
        'config/celery.py': 'Configuracao Celery',
        'config/settings.py': 'Configuracao Django',
        'qms/celery_beat_config.py': 'Configuracao Beat Tasks',
    }
    
    all_exist = True
    for file_path, description in required_files.items():
        if os.path.exists(file_path):
            print_success(f"{file_path}: {description}")
        else:
            print_error(f"{file_path}: FALTANDO!")
            all_exist = False
    
    return all_exist

def get_env_variables():
    """Mostra as variáveis de ambiente necessárias"""
    print_header("PASSO 1: Variáveis de Ambiente Necessárias")
    
    variables = {
        'DJANGO_SETTINGS_MODULE': 'config.settings',
        'DEBUG': 'False',
        'SECRET_KEY': '[Copie do web-app]',
        'ALLOWED_HOSTS': '*',
        'DATABASE_URL': '[Copie do PostgreSQL]',
        'POSTGRES_URL': '[Copie do PostgreSQL]',
        'REDIS_URL': '[Copie do Redis]',
        'CELERY_BROKER_URL': '[Copie do Redis]',
        'CELERY_RESULT_BACKEND': '[Copie do Redis]',
        'CELERY_TIMEZONE': 'America/Sao_Paulo',
        'CELERY_ENABLE_UTC': 'True',
    }
    
    print("Copie estas variáveis EXATAMENTE como mostrado:\n")
    
    for key, value in variables.items():
        print(f"  {key} = {value}")
    
    print("\n" + "!" * 70)
    print("  ⚠  IMPORTANTE: Não use ${REDIS_URL}")
    print("  ⚠  Cole a URL COMPLETA: redis://default:PASSWORD@host:6379")
    print("!" * 70 + "\n")

def print_railway_steps():
    """Printa os passos para o Railway"""
    print_header("PASSO 2: Deploy no Railway (Passos Manuais)")
    
    steps = [
        ("Acesse", "https://railway.app"),
        ("Clique em", "+ Create"),
        ("Selecione", "GitHub"),
        ("Repositório", "vmotasilva/CalibraWeb"),
        ("Branch", "main"),
        ("Clique em", "Deploy"),
        ("Aguarde", "Build completar (~5 min)"),
        ("Vá para", "Settings > Dockerfile"),
        ("Mude para", "Dockerfile.beat"),
        ("Clique em", "Save"),
        ("Vá para", "Variables"),
        ("Adicione", "11 variáveis (ver acima)"),
        ("Clique em", "Save"),
        ("Verifique", "Logs para 'Entering tick loop'"),
    ]
    
    for i, (action, detail) in enumerate(steps, 1):
        print(f"{i:2d}. {action:.<30} {detail}")

def print_verification():
    """Instruções de verificação"""
    print_header("PASSO 3: Verificar Deploy")
    
    checks = [
        ("Status do serviço", "celery-beat", "Deve estar UP"),
        ("Logs", "CELERY_BEAT_ENTRYPOINT", "Deve conter inicialização"),
        ("Logs", "beat: Entering tick loop", "Indica sucesso"),
        ("Django Admin", "/admin/django_celery_beat/", "Deve listar 6 tarefas"),
    ]
    
    for check_type, where, expected in checks:
        print(f"  [{check_type}]")
        print(f"    Procure por: {where}")
        print(f"    Esperado: {expected}\n")

def create_quick_reference():
    """Criar arquivo de referência rápida"""
    print_header("CRIANDO: Arquivo de Referencia Rapida")
    
    reference = """# CELERY BEAT DEPLOYMENT - REFERENCIA RAPIDA

## URLs A COPIAR DO RAILWAY

### 1. Do serviço PostgreSQL:
   DATABASE_URL = [Cole aqui]
   POSTGRES_URL = [Cole aqui]

### 2. Do serviço Redis:
   REDIS_URL = [Cole aqui]
   CELERY_BROKER_URL = [Cole aqui]
   CELERY_RESULT_BACKEND = [Cole aqui]

### 3. Do web-app:
   SECRET_KEY = [Cole aqui]

## VARIÁVEIS NO RAILWAY (Variables)

DJANGO_SETTINGS_MODULE=config.settings
DEBUG=False
SECRET_KEY=[do web-app]
ALLOWED_HOSTS=*
DATABASE_URL=[do PostgreSQL]
POSTGRES_URL=[do PostgreSQL]
REDIS_URL=[do Redis]
CELERY_BROKER_URL=[do Redis]
CELERY_RESULT_BACKEND=[do Redis]
CELERY_TIMEZONE=America/Sao_Paulo
CELERY_ENABLE_UTC=True

## VERIFICACAO FINAL

1. Logs contem: "Starting Celery Beat Scheduler..."
2. Logs contem: "beat: Entering tick loop"
3. Django Admin mostra 6 tarefas em /admin/django_celery_beat/
4. Nenhum erro de ConnectionError ou ModuleNotFoundError

## DOCUMENTAÇÃO

Se tiver problemas, consulte:
- README_CELERY_BEAT.md
- RAILWAY_STEP_BY_STEP.md  
- RAILWAY_VARIABLES_EXAMPLE.md
"""
    
    with open('DEPLOYMENT_QUICK_REFERENCE.txt', 'w', encoding='utf-8') as f:
        f.write(reference)
    
    print_success("Arquivo criado: DEPLOYMENT_QUICK_REFERENCE.txt")

def main():
    print_header("CELERY BEAT DEPLOYMENT - PREPARACAO AUTOMATICA")
    
    # 1. Verificar arquivos
    files_ok = check_files_exist()
    if not files_ok:
        print_error("Alguns arquivos estão faltando!")
        return 1
    
    print_success("Todos os arquivos necessarios encontrados!")
    
    # 2. Mostrar variáveis
    get_env_variables()
    
    # 3. Mostrar passos do Railway
    print_railway_steps()
    
    # 4. Mostrar verificação
    print_verification()
    
    # 5. Criar arquivo de referência
    create_quick_reference()
    
    # 6. Resumo final
    print_header("RESUMO FINAL")
    
    print_info("Você está pronto para fazer o deploy!")
    print_info("")
    print_info("Próximos passos:")
    print_info("  1. Abra: DEPLOYMENT_QUICK_REFERENCE.txt")
    print_info("  2. Copie as URLs do PostgreSQL e Redis do Railway")
    print_info("  3. Cole as variáveis no Railway")
    print_info("  4. Aguarde o deploy completar")
    print_info("  5. Verifique os logs")
    print_info("")
    print_success("Tudo pronto para deploy!")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
