#!/usr/bin/env python
"""
Local Deployment Starter
Sets up all 4 required services for local testing
"""

import os
import sys
import subprocess
import time
from pathlib import Path

def get_windows_terminal_command():
    """Generate Windows Terminal commands to open 4 tabs"""
    
    # Base commands for each terminal
    activate = r".venv\Scripts\Activate.ps1"
    redis_cmd = "python mock_redis_server.py"
    celery_worker = "celery -A config worker -l info"
    celery_beat = "celery -A config beat -l info"
    django = "python manage.py runserver"
    dashboard = "python manage.py cache_dashboard --live --interval 2"
    
    # Build Windows Terminal command
    commands = [
        # Tab 0: Mock Redis Server
        f'wt -w 0 -p "PowerShell" --title "Redis Server" powershell -NoExit -Command "{activate}; {redis_cmd}"',
        
        # Tab 1: Celery Worker
        f'wt -w 0 -t "Celery Worker" powershell -NoExit -Command "{activate}; {celery_worker}"',
        
        # Tab 2: Celery Beat
        f'wt -w 0 -t "Celery Beat" powershell -NoExit -Command "{activate}; {celery_beat}"',
        
        # Tab 3: Django Server
        f'wt -w 0 -t "Django Dev" powershell -NoExit -Command "{activate}; {django}"',
        
        # Tab 4: Dashboard Monitor
        f'wt -w 0 -t "Cache Dashboard" powershell -NoExit -Command "{activate}; {dashboard}"',
    ]
    
    return commands


def print_header():
    print("\n" + "="*80)
    print("🚀 LOCAL DEPLOYMENT STARTER - CalibraWeb")
    print("="*80)
    print("\nThis script will start 5 components in separate Windows Terminal tabs:")
    print("\n  Tab 1: 🔴 Mock Redis Server .................... Port 6379")
    print("  Tab 2: ⚙️  Celery Worker ...................... Async tasks")
    print("  Tab 3: ⏰ Celery Beat ........................ Scheduled tasks")
    print("  Tab 4: 🌐 Django Development Server ........... http://localhost:8000")
    print("  Tab 5: 📊 Cache Dashboard .................... Real-time monitoring")
    print("\n" + "="*80)


def print_instructions():
    print("\n📋 NEXT STEPS:\n")
    print("  1. ✅ All 5 services should start in separate tabs")
    print("  2. ⏳ Wait ~10 seconds for all services to initialize")
    print("  3. 🌐 Open browser: http://localhost:8000")
    print("  4. 📊 Dashboard: Tab 5 (Cache Dashboard)")
    print("  5. 📈 Watch cache hit rates increase")
    print("\n🔍 MONITORING:\n")
    print("  • Django logs: Tab 4")
    print("  • Celery logs: Tabs 2 & 3")
    print("  • Redis logs: Tab 1")
    print("  • Cache metrics: Tab 5 dashboard")
    print("\n💡 TROUBLESHOOTING:\n")
    print("  • If Redis fails: Check if port 6379 is already in use")
    print("  • If Celery fails: Ensure Redis is running")
    print("  • If Django fails: Check database migrations (python manage.py migrate)")
    print("  • View logs: Each terminal shows real-time output")
    print("\n📚 DOCUMENTATION:\n")
    print("  • Architecture: ARCHITECTURE_OVERVIEW.md")
    print("  • Cache Guide: MULTILEVEL_CACHE.md")
    print("  • Dashboard: CACHE_DASHBOARD.md")
    print("  • Deployment: DEPLOYMENT_GUIDE.md")
    print("\n⏹️  TO STOP:\n")
    print("  • Press Ctrl+C in each terminal tab")
    print("  • Or close the Windows Terminal window")
    print("\n" + "="*80 + "\n")


def check_prerequisites():
    """Check if all required files and dependencies exist"""
    print("\n🔍 Checking prerequisites...\n")
    
    required_files = [
        'manage.py',
        'config/settings.py',
        'requirements.txt',
    ]
    
    required_commands = [
        ('python', 'Python'),
        ('celery', 'Celery'),
    ]
    
    # Check files
    for file in required_files:
        path = Path(file)
        if path.exists():
            print(f"  ✅ {file}")
        else:
            print(f"  ❌ {file} - MISSING!")
            return False
    
    # Check commands
    for cmd, name in required_commands:
        try:
            subprocess.run([cmd, '--version'], 
                         capture_output=True, 
                         timeout=5,
                         check=True)
            print(f"  ✅ {name}")
        except:
            print(f"  ❌ {name} - NOT FOUND!")
            print(f"     Install: pip install {cmd.lower()}")
            return False
    
    print("\n✅ All prerequisites met!\n")
    return True


def start_local_deployment():
    """Start local deployment with all services"""
    
    print_header()
    
    if not check_prerequisites():
        print("\n❌ Some prerequisites are missing. Please install them first.")
        return False
    
    print("\n🚀 Starting services in Windows Terminal...\n")
    
    # For development, we'll provide instructions instead of auto-launching
    # since Windows Terminal auto-launch can be complex
    
    print("📋 MANUAL START (if auto-start doesn't work):\n")
    print("Open PowerShell and run these commands in separate windows:\n")
    
    print("Terminal 1 - Redis Server:")
    print("  .venv\\Scripts\\Activate.ps1")
    print("  python mock_redis_server.py\n")
    
    print("Terminal 2 - Celery Worker:")
    print("  .venv\\Scripts\\Activate.ps1")
    print("  celery -A config worker -l info\n")
    
    print("Terminal 3 - Celery Beat:")
    print("  .venv\\Scripts\\Activate.ps1")
    print("  celery -A config beat -l info\n")
    
    print("Terminal 4 - Django Server:")
    print("  .venv\\Scripts\\Activate.ps1")
    print("  python manage.py runserver\n")
    
    print("Terminal 5 - Cache Dashboard:")
    print("  .venv\\Scripts\\Activate.ps1")
    print("  python manage.py cache_dashboard --live --interval 2\n")
    
    # Try to launch Windows Terminal with tabs
    try:
        commands = get_windows_terminal_command()
        for cmd in commands:
            subprocess.Popen(cmd, shell=True)
            time.sleep(0.5)  # Small delay between launching tabs
        print("✅ Windows Terminal launched with all tabs\n")
    except Exception as e:
        print(f"⚠️  Could not auto-launch Windows Terminal: {e}")
        print("   Please run the commands above manually in separate terminal windows\n")
    
    print_instructions()
    
    return True


if __name__ == '__main__':
    try:
        if start_local_deployment():
            print("✨ Local deployment setup complete!")
            print("   Monitor logs in each terminal tab\n")
    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
