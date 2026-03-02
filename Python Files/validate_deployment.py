#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para VALIDAR que Celery Beat foi deployado com sucesso no Railway

Use APÓS fazer o deploy manual no Railway
"""

import sys
from pathlib import Path
from datetime import datetime

def check_files():
    """Verifica se arquivos existem"""
    print("\n=== VALIDACAO 1: Arquivos Criados ===\n")
    
    files = {
        'Dockerfile.beat': 'Docker para Celery Beat',
        'entrypoint-beat.py': 'Script de inicializacao',
        'config/celery.py': 'Configuracao Celery',
        'qms/celery_beat_config.py': 'Configuracao Beat',
    }
    
    all_exist = True
    for file_path, desc in files.items():
        if Path(file_path).exists():
            print(f"[OK] {file_path}: {desc}")
        else:
            print(f"[ERRO] {file_path}: NAO ENCONTRADO")
            all_exist = False
    
    return all_exist

def check_docker():
    """Verifica Dockerfile.beat"""
    print("\n=== VALIDACAO 2: Configuracao Docker ===\n")
    
    try:
        with open('Dockerfile.beat', 'r') as f:
            content = f.read()
        
        checks = [
            ('CMD presente', 'entrypoint-beat.py' in content),
            ('Sem HEALTHCHECK', 'HEALTHCHECK' not in content),
            ('Sem EXPOSE 8000', 'EXPOSE 8000' not in content),
        ]
        
        all_ok = True
        for name, result in checks:
            status = "[OK]" if result else "[ERRO]"
            print(f"{status} Dockerfile.beat: {name}")
            all_ok = all_ok and result
        
        return all_ok
    
    except Exception as e:
        print(f"[ERRO] Lendo Dockerfile.beat: {e}")
        return False

def main():
    """Função principal"""
    print_header("VALIDAÇÃO DE DEPLOYMENT - CELERY BEAT")
    
    print(f"Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"Diretório: {Path.cwd()}\n")
    
    # Executar validações
    print_warning("Validando ambiente local (antes do deploy no Railway)...\n")
    
    checks = [
        ("Arquivos existem", check_files_exist()),
        ("Docker configurado", check_docker_config()),
        ("Entrypoint configurado", check_entrypoint_config()),
    ]
    
    all_passed = all(result for _, result in checks)
    
    # Imprimir resultados
    print_header("RESUMO DAS VALIDAÇÕES")
    
    for check_name, result in checks:
        if result:
            print_success(f"{check_name}")
        else:
            print_error(f"{check_name}")
    
    if all_passed:
        print(f"\n{Colors.GREEN}✓ TUDO PRONTO PARA DEPLOY!{Colors.END}\n")
    else:
        print(f"\n{Colors.RED}✗ Existem problemas a resolver{Colors.END}\n")
        return 1
    
    # Imprimir instruções
    print_deployment_checklist()
    print_environment_variables()
    print_log_validation()
    print_scheduled_tasks()
    
    # Final
    print_header("PRÓXIMO PASSO")
    print(f"""
{Colors.BLUE}1. Abra: DEPLOY_MANUAL_RAILWAY.md{Colors.END}
{Colors.BLUE}2. Siga os 9 passos simples{Colors.END}
{Colors.BLUE}3. Após deploy, verifique nos logs{Colors.END}
{Colors.BLUE}4. Procure por: "Entering tick loop"{Colors.END}

Tempo estimado: 15-20 minutos

Boa sorte! 🚀
    """)
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
