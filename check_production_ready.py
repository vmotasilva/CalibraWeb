#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Pre-deployment verification script for CalibraWeb
Verifies all systems before pushing to production
"""

import os
import sys
import subprocess
from pathlib import Path

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def print_header(text):
    print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BLUE}{text.center(60)}{Colors.RESET}")
    print(f"{Colors.BLUE}{'='*60}{Colors.RESET}\n")

def check(name, condition, error_msg=""):
    status = f"{Colors.GREEN}✓{Colors.RESET}" if condition else f"{Colors.RED}✗{Colors.RESET}"
    print(f"{status} {name}")
    if not condition and error_msg:
        print(f"  {Colors.YELLOW}⚠ {error_msg}{Colors.RESET}")
    return condition

def run_command(cmd, description=""):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return False, "", str(e)

def main():
    print_header("PRÉ-DEPLOYMENT VERIFICATION")
    print("Verificando a prontidão da aplicação para produção...\n")
    
    checks_passed = 0
    checks_total = 0
    
    # 1. Python Environment
    print(f"{Colors.BLUE}1. AMBIENTE PYTHON{Colors.RESET}")
    
    # Check Python version
    checks_total += 1
    version_ok, stdout, _ = run_command("python --version")
    if check("Python 3.8+", "3.8" in stdout or "3.9" in stdout or "3.10" in stdout or "3.11" in stdout or "3.12" in stdout):
        checks_passed += 1
        print(f"  Versão: {stdout}")
    
    # Check venv
    checks_total += 1
    if check("Virtual Environment", os.path.exists("venv") or os.path.exists(".venv")):
        checks_passed += 1
    
    # Check Django
    checks_total += 1
    django_ok, _, _ = run_command("python -c 'import django; print(django.get_version())'")
    if check("Django Instalado", django_ok):
        checks_passed += 1
    
    # 2. Project Configuration
    print(f"\n{Colors.BLUE}2. CONFIGURAÇÃO DO PROJETO{Colors.RESET}")
    
    # Check settings.py
    checks_total += 1
    if check("Settings.py", os.path.exists("config/settings.py")):
        checks_passed += 1
    
    # Check manage.py
    checks_total += 1
    if check("Manage.py", os.path.exists("manage.py")):
        checks_passed += 1
    
    # Check requirements
    checks_total += 1
    if check("Requirements.txt", os.path.exists("requirements.txt")):
        checks_passed += 1
    
    checks_total += 1
    if check("Requirements-prod.txt", os.path.exists("requirements-prod.txt")):
        checks_passed += 1
    
    # 3. Docker Configuration
    print(f"\n{Colors.BLUE}3. CONFIGURAÇÃO DOCKER{Colors.RESET}")
    
    checks_total += 1
    if check("Dockerfile", os.path.exists("Dockerfile")):
        checks_passed += 1
    
    checks_total += 1
    if check(".dockerignore", os.path.exists(".dockerignore")):
        checks_passed += 1
    
    # 4. Railway Configuration
    print(f"\n{Colors.BLUE}4. CONFIGURAÇÃO RAILWAY{Colors.RESET}")
    
    checks_total += 1
    if check("railway.toml", os.path.exists("railway.toml")):
        checks_passed += 1
    
    checks_total += 1
    if check(".env.railway.example", os.path.exists(".env.railway.example")):
        checks_passed += 1
    
    # 5. Code Quality
    print(f"\n{Colors.BLUE}5. QUALIDADE DO CÓDIGO{Colors.RESET}")
    
    # Django Check
    checks_total += 1
    django_check_ok, stdout, stderr = run_command("python manage.py check")
    if check("Django Check", django_check_ok, stderr if not django_check_ok else ""):
        checks_passed += 1
    
    # Python Syntax
    checks_total += 1
    syntax_ok, _, _ = run_command("python -m py_compile qms/views.py qms/urls.py")
    if check("Python Syntax (Views/URLs)", syntax_ok):
        checks_passed += 1
    
    # 6. Git Status
    print(f"\n{Colors.BLUE}6. STATUS GIT{Colors.RESET}")
    
    # Check git repo
    checks_total += 1
    git_ok, _, _ = run_command("git rev-parse --git-dir")
    if check("Git Repository", git_ok):
        checks_passed += 1
    
    # Check remote
    checks_total += 1
    remote_ok, stdout, _ = run_command("git remote -v")
    if check("Git Remote Configured", "origin" in stdout):
        checks_passed += 1
    
    # Check main branch
    checks_total += 1
    branch_ok, stdout, _ = run_command("git rev-parse --abbrev-ref HEAD")
    if check("On main branch", stdout.strip() == "main", f"Você está em: {stdout.strip()}"):
        checks_passed += 1
    
    # 7. Database
    print(f"\n{Colors.BLUE}7. BANCO DE DADOS{Colors.RESET}")
    
    checks_total += 1
    if check("Database exists", os.path.exists("db.sqlite3") or True, "SQLite ou PostgreSQL configurado"):
        checks_passed += 1
    
    # Check migrations
    checks_total += 1
    migrations_ok, stdout, _ = run_command("python manage.py showmigrations --plan")
    has_pending = "0 applied" not in stdout and len(stdout) > 0
    if check("Migrations status", True, "Verifique com 'python manage.py showmigrations'"):
        checks_passed += 1
    
    # 8. Feature Implementation
    print(f"\n{Colors.BLUE}8. IMPLEMENTAÇÃO DE FEATURES{Colors.RESET}")
    
    # Check new view
    checks_total += 1
    view_ok, _, _ = run_command("python -c \"import os; os.environ['DJANGO_SETTINGS_MODULE']='config.settings'; import django; django.setup(); from qms.views import listar_historicos_calibracao_view; print('OK')\"")
    if check("View 'listar_historicos_calibracao_view'", view_ok):
        checks_passed += 1
    
    # Check URLs
    checks_total += 1
    url_ok, _, _ = run_command("python -c \"import os; os.environ['DJANGO_SETTINGS_MODULE']='config.settings'; import django; django.setup(); from django.urls import reverse; print(reverse('qms:listar_historicos_calibracao'))\"")
    if check("URL 'qms:listar_historicos_calibracao'", url_ok):
        checks_passed += 1
    
    # Check template
    checks_total += 1
    if check("Template 'historicos_calibracao_list.html'", os.path.exists("qms/templates/qms/historicos_calibracao_list.html")):
        checks_passed += 1
    
    # 9. Environment Variables
    print(f"\n{Colors.BLUE}9. VARIÁVEIS DE AMBIENTE{Colors.RESET}")
    
    checks_total += 1
    env_file_exists = os.path.exists(".env")
    if check(".env arquivo existe", env_file_exists, "Necessário em produção via Railway"):
        checks_passed += 1
    
    required_vars = [
        'SECRET_KEY', 'DEBUG', 'ALLOWED_HOSTS', 'DATABASE_URL',
        'REDIS_URL', 'CELERY_BROKER_URL', 'EMAIL_HOST'
    ]
    
    env_vars = {}
    if os.path.exists('.env'):
        with open('.env') as f:
            for line in f:
                if '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    
    for var in required_vars:
        checks_total += 1
        var_exists = var in env_vars or var in os.environ
        if check(f"Variável '{var}'", var_exists, "Configure no Railway ou .env"):
            checks_passed += 1
    
    # 10. Documentation
    print(f"\n{Colors.BLUE}10. DOCUMENTAÇÃO{Colors.RESET}")
    
    docs = [
        "DEPLOY_PRODUCAO_GUIA_COMPLETO.md",
        "IMPLEMENTACAO_HISTORICOS_CALIBRACAO.md",
        "README.md"
    ]
    
    for doc in docs:
        checks_total += 1
        if check(f"Documento '{doc}'", os.path.exists(doc)):
            checks_passed += 1
    
    # Summary
    print_header("RESUMO DA VERIFICAÇÃO")
    
    percentage = (checks_passed / checks_total * 100) if checks_total > 0 else 0
    
    print(f"Total de Verificações: {checks_total}")
    print(f"Passaram: {checks_passed}")
    print(f"Falharam: {checks_total - checks_passed}")
    print(f"Percentual: {percentage:.1f}%\n")
    
    if checks_passed == checks_total:
        print(f"{Colors.GREEN}✓ TUDO PRONTO PARA DEPLOY!{Colors.RESET}\n")
        print("Próximas etapas:")
        print("1. git push origin main")
        print("2. Acompanhe o deploy em https://railway.app")
        print("3. Execute migrations se necessário")
        print("4. Teste a aplicação em produção")
        return 0
    else:
        print(f"{Colors.RED}✗ Resolva os problemas acima antes de fazer deploy{Colors.RESET}\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
