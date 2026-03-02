#!/usr/bin/env python
"""
🚀 DEPLOYMENT STARTER - Quick setup for staging/production
"""

import os
import sys
from pathlib import Path


def print_banner(title):
    """Print formatted banner"""
    width = 70
    print("\n" + "="*width)
    print(f"  {title.center(width-4)}")
    print("="*width + "\n")


def check_files_exist():
    """Verify all critical files exist"""
    print_banner("📁 Checking Critical Files")
    
    critical_files = [
        'config/cache_invalidation.py',
        'config/multilevel_cache.py',
        'config/cache_decorators.py',
        'qms/cache_warming.py',
        'qms/cache_warming_tasks.py',
        'qms/cache_dashboard.py',
        'qms/cache_signals.py',
        'manage.py',
        'requirements.txt',
    ]
    
    all_exist = True
    for filepath in critical_files:
        exists = os.path.exists(filepath)
        status = "✅" if exists else "❌"
        print(f"{status} {filepath}")
        if not exists:
            all_exist = False
    
    return all_exist


def check_redis():
    """Check Redis connectivity"""
    print_banner("🔴 Checking Redis")
    
    try:
        import redis
        try:
            r = redis.Redis(host='localhost', port=6379, db=0)
            r.ping()
            print("✅ Redis is running and accessible")
            print("   Host: localhost:6379")
            info = r.info()
            print(f"   Version: {info.get('redis_version', 'unknown')}")
            print(f"   Memory used: {info.get('used_memory_human', 'unknown')}")
            return True
        except Exception as e:
            print(f"⚠️ Redis not running or not accessible")
            print(f"   Error: {str(e)}")
            print("\n   How to start Redis:")
            print("   Option 1 (Docker): docker run -d -p 6379:6379 redis:latest")
            print("   Option 2 (Windows): redis-server.exe")
            print("   Option 3 (Cloud): Configure REDIS_URL in .env")
            return False
    except ImportError:
        print("⚠️ Redis library not installed")
        print("   Install with: pip install redis")
        return False


def check_django():
    """Check Django setup"""
    print_banner("🎯 Checking Django Setup")
    
    try:
        import django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
        django.setup()
        print(f"✅ Django {django.get_version()} configured")
        
        # Check database
        from django.db import connection
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            print("✅ Database connected")
            return True
        except Exception as e:
            print(f"⚠️ Database connection failed: {str(e)}")
            return False
    except Exception as e:
        print(f"❌ Django setup failed: {str(e)}")
        return False


def check_dependencies():
    """Check Python dependencies"""
    print_banner("📦 Checking Dependencies")
    
    required = [
        'django',
        'redis',
        'celery',
        'django_redis',
        'psycopg2',  # PostgreSQL
    ]
    
    all_installed = True
    for package in required:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} (run: pip install {package})")
            all_installed = False
    
    return all_installed


def show_quick_start():
    """Show quick start guide"""
    print_banner("🚀 QUICK START GUIDE")
    
    guide = """
STEP 1: Setup Environment
  $ .venv\\Scripts\\Activate.ps1
  $ pip install -r requirements.txt
  $ python manage.py migrate

STEP 2: Start Redis (choose one)
  Option A: docker run -d -p 6379:6379 redis:latest
  Option B: redis-server.exe
  
STEP 3: Start Services
  Terminal 1: celery -A config worker -l info
  Terminal 2: celery -A config beat -l info
  Terminal 3: python manage.py runserver
  
STEP 4: Monitor Cache
  Terminal 4: python manage.py cache_dashboard --live --interval 2

STEP 5: Validate Everything
  $ python manage.py test qms --verbosity=2
  $ python manage.py cache_dashboard --health

STEP 6: Deploy to Staging
  See DEPLOYMENT_GUIDE.md for complete instructions
    """
    
    print(guide)


def show_next_steps():
    """Show next steps"""
    print_banner("📋 NEXT STEPS")
    
    steps = """
1. IMMEDIATE (Now):
   ✅ Review ARCHITECTURE_OVERVIEW.md (understand design)
   ✅ Read DEPLOYMENT_GUIDE.md (setup instructions)
   ✅ Read README_FASE7.md (complete reference)

2. TODAY/TOMORROW:
   ✅ Setup staging environment
   ✅ Configure Redis for staging
   ✅ Run Django migrations
   ✅ Start Celery worker & beat
   ✅ Validate with: python manage.py cache_dashboard --health

3. STAGING (24-48 hours):
   ✅ Monitor cache hit rates
   ✅ Run load tests
   ✅ Verify all alerts working
   ✅ Check performance metrics

4. PRODUCTION (Week 2):
   ✅ Blue-green deployment
   ✅ 24/7 monitoring
   ✅ Gradual traffic ramp-up
   ✅ Performance validation

REFERENCE DOCUMENTS:
  • README_FASE7.md ..................... Main reference
  • DEPLOYMENT_GUIDE.md ................. Staging/Production setup
  • PREDEPLOYMENT_CHECKLIST.md .......... Validation checklist
  • ARCHITECTURE_OVERVIEW.md ........... System design
  • CACHE_DASHBOARD.md .................. Monitoring
  • MULTILEVEL_CACHE.md ................. Cache architecture
    """
    
    print(steps)


def main():
    """Main function"""
    
    print("\n" + "="*70)
    print("  🚀 CALIBRAWEB FASE 7 - DEPLOYMENT STARTER 🚀")
    print("="*70)
    
    # Check everything
    files_ok = check_files_exist()
    deps_ok = check_dependencies()
    django_ok = check_django()
    redis_ok = check_redis()
    
    # Show quick start
    show_quick_start()
    
    # Show next steps
    show_next_steps()
    
    # Summary
    print_banner("✅ STATUS SUMMARY")
    
    print("Critical Files:    ", "✅ OK" if files_ok else "⚠️ ISSUES")
    print("Dependencies:      ", "✅ OK" if deps_ok else "⚠️ INSTALL MISSING")
    print("Django Setup:      ", "✅ OK" if django_ok else "⚠️ CONFIGURE DB")
    print("Redis:             ", "✅ OK" if redis_ok else "⚠️ START REDIS")
    
    if not all([files_ok, deps_ok, django_ok]):
        print("\n⚠️ Please fix issues above before deployment")
        return False
    
    if not redis_ok:
        print("\n⚠️ Redis is required - start it before running services")
    
    print("\n" + "="*70)
    print("  ✨ Ready for Staging Deployment!")
    print("  📖 Start with: README_FASE7.md")
    print("  🚀 Deploy with: DEPLOYMENT_GUIDE.md")
    print("="*70 + "\n")
    
    return True


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
