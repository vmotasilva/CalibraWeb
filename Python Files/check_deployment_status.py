#!/usr/bin/env python
"""
LOCAL DEPLOYMENT STATUS CHECKER
Shows comprehensive status of all local services
"""

import subprocess
import socket
import time
import sys
from datetime import datetime
from pathlib import Path

def check_redis():
    """Check if Redis mock server is running"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', 6379))
        sock.close()
        return result == 0
    except:
        return False

def check_django():
    """Check if Django development server is running"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', 8000))
        sock.close()
        return result == 0
    except:
        return False

def check_database():
    """Check if database is accessible"""
    try:
        result = subprocess.run(
            ['python', 'manage.py', 'migrate', '--check'],
            capture_output=True,
            timeout=10
        )
        return result.returncode == 0
    except:
        return False

def print_status():
    """Print comprehensive status"""
    
    print("\n" + "="*80)
    print("📊 LOCAL DEPLOYMENT STATUS - CalibraWeb")
    print("="*80)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Check services
    redis_ok = check_redis()
    django_ok = check_django()
    db_ok = check_database()
    
    print("🔧 SERVICES STATUS:")
    print(f"  {'✅ Redis Mock Server' if redis_ok else '❌ Redis Mock Server':<40} {'🟢 Running' if redis_ok else '🔴 Not Running'}")
    print(f"  {'✅ Django Dev Server' if django_ok else '❌ Django Dev Server':<40} {'🟢 Running' if django_ok else '🔴 Not Running'}")
    print(f"  {'✅ Database' if db_ok else '❌ Database':<40} {'🟢 Connected' if db_ok else '🔴 Not Connected'}")
    
    print("\n📋 CRITICAL FILES:")
    critical_files = [
        'manage.py',
        'config/settings.py',
        'config/cache_invalidation.py',
        'config/multilevel_cache.py',
        'qms/cache_dashboard.py',
        'requirements.txt',
    ]
    
    for file in critical_files:
        exists = Path(file).exists()
        print(f"  {'✅' if exists else '❌'} {file}")
    
    print("\n🎯 NEXT STEPS:")
    
    if redis_ok:
        print("\n  1. ✅ Redis Mock Server is running")
        print("     → You can now start Celery and Django")
    else:
        print("\n  1. ❌ Start Redis Mock Server:")
        print("     → Terminal: python mock_redis_server.py")
    
    if redis_ok:
        print("\n  2. Start Celery Worker (in separate terminal):")
        print("     → .venv\\Scripts\\Activate.ps1")
        print("     → celery -A config worker -l info")
    
    if redis_ok:
        print("\n  3. Start Celery Beat (in separate terminal):")
        print("     → .venv\\Scripts\\Activate.ps1")
        print("     → celery -A config beat -l info")
    
    if redis_ok:
        print("\n  4. Start Django Dev Server (in separate terminal):")
        print("     → .venv\\Scripts\\Activate.ps1")
        print("     → python manage.py runserver")
    
    if redis_ok:
        print("\n  5. Monitor Cache Dashboard (in separate terminal):")
        print("     → .venv\\Scripts\\Activate.ps1")
        print("     → python manage.py cache_dashboard --live --interval 2")
    
    print("\n📚 DOCUMENTATION:")
    print("  • Quick Start: IMMEDIATE_ACTIONS.md")
    print("  • Architecture: ARCHITECTURE_OVERVIEW.md")
    print("  • Cache Guide: MULTILEVEL_CACHE.md")
    print("  • Deployment: DEPLOYMENT_GUIDE.md")
    print("  • Dashboard: CACHE_DASHBOARD.md")
    
    print("\n🌐 QUICK LINKS:")
    if django_ok:
        print("  • Django Admin: http://localhost:8000/admin/")
        print("  • API Docs: http://localhost:8000/api/")
    else:
        print("  • Django Server: Not yet running")
        print("  • Start with: python manage.py runserver")
    
    print("\n" + "="*80 + "\n")
    
    return redis_ok and django_ok


if __name__ == '__main__':
    try:
        success = print_status()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        sys.exit(1)
