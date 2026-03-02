#!/usr/bin/env python
"""
Script para auxiliar no setup do Celery Beat no Railway
Realiza verificações pré-deployment
"""
import os
import sys
import subprocess

def check_redis_connection():
    """Verifica conexão com Redis"""
    redis_url = os.getenv('REDIS_URL') or os.getenv('CELERY_BROKER_URL')
    
    if not redis_url:
        print("⚠️  Redis URL não configurada")
        return False
    
    try:
        import redis
        from urllib.parse import urlparse
        
        parsed = urlparse(redis_url)
        r = redis.from_url(redis_url, decode_responses=True)
        r.ping()
        print(f"✓ Redis conectado: {parsed.hostname}")
        return True
    except Exception as e:
        print(f"✗ Erro ao conectar Redis: {e}")
        return False

def check_database_connection():
    """Verifica conexão com banco de dados"""
    try:
        import django
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        django.setup()
        
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        print("✓ Database conectado")
        return True
    except Exception as e:
        print(f"✗ Erro ao conectar database: {e}")
        return False

def check_celery_tasks():
    """Verifica se tarefas Celery estão registradas"""
    try:
        import django
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        django.setup()
        
        from config.celery import app
        tasks = list(app.tasks.keys())
        
        print(f"✓ {len(tasks)} tarefas registradas em Celery")
        
        # Check for beat tasks
        if hasattr(app.conf, 'beat_schedule'):
            beat_tasks = list(app.conf.beat_schedule.keys())
            print(f"  └─ {len(beat_tasks)} tarefas agendadas no Beat:")
            for task_name in beat_tasks:
                print(f"     • {task_name}")
        
        return True
    except Exception as e:
        print(f"✗ Erro ao verificar tarefas Celery: {e}")
        return False

def check_migrations():
    """Verifica se todas as migrações foram aplicadas"""
    try:
        result = subprocess.run([
            sys.executable, 'manage.py', 'showmigrations', '--plan'
        ], capture_output=True, text=True)
        
        if 'applied' in result.stdout.lower():
            print("✓ Migrações de database aplicadas")
            return True
        else:
            print("⚠️  Verifique o status das migrações")
            return False
    except Exception as e:
        print(f"✗ Erro ao verificar migrações: {e}")
        return False

def main():
    print("=" * 60)
    print("VERIFICAÇÃO PRÉ-DEPLOYMENT: CELERY BEAT")
    print("=" * 60)
    print()
    
    checks = {
        'Redis': check_redis_connection,
        'Database': check_database_connection,
        'Celery Tasks': check_celery_tasks,
        'Database Migrations': check_migrations,
    }
    
    results = {}
    for name, check_func in checks.items():
        print(f"\n[{name}]")
        results[name] = check_func()
    
    print("\n" + "=" * 60)
    print("RESUMO")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, passed_check in results.items():
        status = "✓ PASSOU" if passed_check else "✗ FALHOU"
        print(f"{name:.<40} {status}")
    
    print(f"\nTotal: {passed}/{total} verificações passaram")
    
    if passed == total:
        print("\n✓ Sistema pronto para deploy do Celery Beat!")
        return 0
    else:
        print(f"\n✗ {total - passed} verificação(ões) falharam")
        print("  Verifique os erros acima antes de fazer o deploy")
        return 1

if __name__ == "__main__":
    sys.exit(main())
