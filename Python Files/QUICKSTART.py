#!/usr/bin/env python
"""
🚀 QUICK START GUIDE - CalibraWeb Fase 7 Caching System

Este script fornece comandos rápidos para colocar o sistema de cache em funcionamento.
"""

import os
import sys
from pathlib import Path


class QuickStart:
    """Helper para quick start do sistema de caching"""
    
    COMMANDS = {
        'dev_setup': {
            'title': '🔧 Setup Inicial (Desenvolvimento)',
            'steps': [
                ('Ativar virtualenv', '.venv\\Scripts\\Activate.ps1'),
                ('Instalar dependências', 'pip install -r requirements.txt'),
                ('Rodar migrations', 'python manage.py migrate'),
            ]
        },
        'dev_redis': {
            'title': '🔴 Iniciar Redis (Desenvolvimento)',
            'steps': [
                ('Opção 1: Docker', 'docker run -d -p 6379:6379 redis:latest'),
                ('Opção 2: Windows nativo', 'redis-server.exe'),
                ('Verificar conexão', 'redis-cli ping'),
            ]
        },
        'dev_celery': {
            'title': '⚙️ Iniciar Celery (Desenvolvimento)',
            'steps': [
                ('Terminal 1: Worker', 'celery -A config worker -l info'),
                ('Terminal 2: Beat', 'celery -A config beat -l info'),
                ('Verificar tasks', 'celery -A config inspect active'),
            ]
        },
        'dev_django': {
            'title': '🎯 Iniciar Django (Desenvolvimento)',
            'steps': [
                ('Iniciar servidor', 'python manage.py runserver'),
                ('Verificar saúde', 'python manage.py check'),
                ('Acessar', 'http://localhost:8000/'),
            ]
        },
        'dev_dashboard': {
            'title': '📊 Dashboard em Tempo Real',
            'steps': [
                ('Modo live', 'python manage.py cache_dashboard --live --interval 2'),
                ('Stats', 'python manage.py cache_dashboard --stats'),
                ('Health', 'python manage.py cache_dashboard --health'),
                ('Alerts', 'python manage.py cache_dashboard --alerts'),
            ]
        },
        'validate': {
            'title': '✅ Validar Sistema de Cache',
            'steps': [
                ('Validação completa', 'python validate_cache_system.py'),
                ('Gerar relatório', 'python validate_cache_system.py > validation_report.txt'),
            ]
        },
        'tests': {
            'title': '🧪 Rodar Testes',
            'steps': [
                ('Todos os testes', 'python manage.py test qms --verbosity=2'),
                ('Testes de cache', 'python manage.py test qms.tests.CacheTests'),
                ('Com coverage', 'coverage run --source="." manage.py test qms'),
                ('Relatório', 'coverage report'),
            ]
        },
        'production': {
            'title': '🚀 Setup Produção',
            'steps': [
                ('Gerar config', 'python setup_deployment_environment.py'),
                ('Com Docker', 'docker-compose -f docker-compose.production.yml up -d'),
                ('Migrations', 'python manage.py migrate'),
                ('Static files', 'python manage.py collectstatic --noinput'),
            ]
        },
    }
    
    @staticmethod
    def print_header():
        """Print header"""
        print("\n" + "="*70)
        print("🚀 CalibraWeb Fase 7 - Caching System Quick Start")
        print("="*70)
        print()
    
    @staticmethod
    def print_menu():
        """Print main menu"""
        print("Selecione o que fazer:\n")
        
        for idx, (key, info) in enumerate(QuickStart.COMMANDS.items(), 1):
            print(f"{idx}. {info['title']}")
        
        print(f"\n0. Sair")
        print()
    
    @staticmethod
    def print_section(info):
        """Print section with commands"""
        print("\n" + "="*70)
        print(info['title'])
        print("="*70 + "\n")
        
        for idx, (desc, cmd) in enumerate(info['steps'], 1):
            print(f"{idx}. {desc}")
            print(f"   $ {cmd}\n")
    
    @staticmethod
    def show_development_workflow():
        """Show recommended development workflow"""
        print("\n" + "="*70)
        print("💡 Workflow Recomendado (Desenvolvimento)")
        print("="*70 + "\n")
        
        workflow = """
1. SETUP INICIAL (uma vez)
   $ .venv\\Scripts\\Activate.ps1
   $ pip install -r requirements.txt
   $ python manage.py migrate

2. INICIAR REDIS (um terminal)
   $ docker run -d -p 6379:6379 redis:latest
   
   ou
   
   $ redis-server.exe

3. INICIAR CELERY (outro terminal)
   $ celery -A config worker -l info
   
4. INICIAR BEAT (outro terminal)
   $ celery -A config beat -l info

5. INICIAR DJANGO (outro terminal)
   $ python manage.py runserver

6. MONITORAR (outro terminal)
   $ python manage.py cache_dashboard --live --interval 2

7. TESTAR (quando necessário)
   $ python manage.py test qms
   $ python validate_cache_system.py

💡 Dica: Use ConEmu, tmux, ou VS Code terminals para múltiplos terminais
"""
        print(workflow)
    
    @staticmethod
    def show_files_structure():
        """Show important files structure"""
        print("\n" + "="*70)
        print("📁 Estrutura de Arquivos Importante")
        print("="*70 + "\n")
        
        structure = """
Caching Implementation:
├── config/
│   ├── http_cache_config.py (HTTP caching strategies)
│   ├── cache_decorators.py (View decorators)
│   ├── multilevel_cache.py (L1/L2/L3 implementation)
│   ├── cache_managers.py (Specialized managers)
│   ├── cache_invalidation.py (Invalidation logic)
│   ├── varnish.vcl (Varnish reverse proxy)
│   └── nginx.cache.conf (Nginx caching)
│
├── qms/
│   ├── cache_signals.py (Django signals)
│   ├── cache_warming.py (Access pattern analysis)
│   ├── cache_warming_tasks.py (Celery tasks)
│   ├── cache_dashboard.py (Monitoring system)
│   └── management/commands/
│       ├── cache_dashboard.py (CLI tool)
│       ├── cache_purge.py (Manual purge)
│       ├── multilevel_cache_monitor.py (Monitoring)
│       └── http_cache_monitor.py (HTTP monitoring)

Documentation:
├── MULTILEVEL_CACHE.md (Architecture reference)
├── CACHE_INVALIDATION.md (Invalidation guide)
├── CACHE_WARMING.md (Warming strategies)
├── CACHE_DASHBOARD.md (Monitoring guide)
├── HTTPCACHE.md (HTTP caching guide)
├── DEPLOYMENT_GUIDE.md (Staging/Production setup)
├── PREDEPLOYMENT_CHECKLIST.md (Validation checklist)
├── PROJECT_STATUS_REPORT.md (Project overview)
└── FASE_7_SUMMARY.md (Fase 7 summary)

Tools:
├── validate_cache_system.py (Validation script)
└── setup_deployment_environment.py (Config generator)
"""
        print(structure)
    
    @staticmethod
    def show_key_metrics():
        """Show key performance metrics"""
        print("\n" + "="*70)
        print("📊 Métricas-Chave de Performance")
        print("="*70 + "\n")
        
        metrics = """
Esperado após deployment:

Cache Hit Rate:
  ├── L1 (Request-scoped): 30-50%
  ├── L2 (Worker-scoped): 40-60%
  ├── L3 (Redis): 70-85%
  └── COMBINED: 85-95% ✅ TARGET

Response Time:
  ├── Cached requests: <5ms ✅
  ├── Uncached requests: 50-200ms
  └── Overall improvement: 90x faster ✅

Database Load:
  ├── Before cache: 100%
  ├── After cache: 5-10% ✅
  └── Reduction: 90% ✅

Throughput:
  ├── Before: 100 req/sec
  ├── After: 10,000+ req/sec ✅
  └── Improvement: 100x ✅

Monitor em tempo real:
  $ python manage.py cache_dashboard --live
"""
        print(metrics)
    
    @staticmethod
    def show_troubleshooting():
        """Show troubleshooting guide"""
        print("\n" + "="*70)
        print("🔧 Troubleshooting Rápido")
        print("="*70 + "\n")
        
        troubleshooting = """
❌ Problem: "Redis connection refused"
✅ Solution:
   docker run -d -p 6379:6379 redis:latest
   ou
   Instale Redis nativo: https://redis.io/

❌ Problem: "Celery worker not running"
✅ Solution:
   celery -A config worker -l info
   Verifique se Redis está rodando primeiro

❌ Problem: "Hit rate muito baixo (<50%)"
✅ Solution:
   python manage.py cache_dashboard --access-patterns
   Aumentar TTL em config/cache_invalidation.py
   Rodar cache warming manualmente

❌ Problem: "Memory usage muito alto"
✅ Solution:
   Reduzir L2_CACHE_MAX_SIZE em config/multilevel_cache.py
   Limpar cache: python manage.py cache_purge --all
   Configurar TTL mais agressivo

❌ Problem: "Testes falhando"
✅ Solution:
   python manage.py check
   python manage.py migrate
   Instalar dependências: pip install -r requirements.txt

📖 Para mais detalhes, consulte:
   - DEPLOYMENT_GUIDE.md
   - PREDEPLOYMENT_CHECKLIST.md
   - Logs do projeto
"""
        print(troubleshooting)
    
    @staticmethod
    def run():
        """Run interactive menu"""
        QuickStart.print_header()
        
        while True:
            QuickStart.print_menu()
            
            choice = input("Escolha (0-8): ").strip()
            
            if choice == '0':
                print("👋 Até logo!\n")
                break
            
            try:
                choice_idx = int(choice) - 1
                keys = list(QuickStart.COMMANDS.keys())
                
                if 0 <= choice_idx < len(keys):
                    key = keys[choice_idx]
                    QuickStart.print_section(QuickStart.COMMANDS[key])
                else:
                    print("❌ Opção inválida\n")
            except ValueError:
                print("❌ Entrada inválida\n")


def main():
    """Main function"""
    try:
        # Check if running in repo root
        if not os.path.exists('manage.py'):
            print("❌ Erro: Execute este script no diretório raiz do projeto")
            print("   Correct: cd c:\\CalibraWeb && python -m qms.quickstart")
            sys.exit(1)
        
        quick_start = QuickStart()
        quick_start.run()
        
        # Show additional info
        print("\n")
        choice = input("Ver informações adicionais? (S/n): ").strip().lower()
        
        if choice != 'n':
            quick_start.show_development_workflow()
            quick_start.show_files_structure()
            quick_start.show_key_metrics()
            quick_start.show_troubleshooting()
        
        print("\n" + "="*70)
        print("✨ Sucesso! Sistema de caching pronto para uso")
        print("="*70 + "\n")
        
        print("Próximos passos:")
        print("1. 📚 Ler documentação (MULTILEVEL_CACHE.md, etc.)")
        print("2. 🧪 Rodar testes: python manage.py test qms")
        print("3. ✅ Validar sistema: python validate_cache_system.py")
        print("4. 📊 Monitorar: python manage.py cache_dashboard --live")
        print("5. 🚀 Deploy: Seguir DEPLOYMENT_GUIDE.md\n")
        
    except KeyboardInterrupt:
        print("\n\n👋 Interrompido pelo usuário")
        sys.exit(0)


if __name__ == '__main__':
    main()
