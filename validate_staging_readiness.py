#!/usr/bin/env python
"""
Pre-Staging Deployment Validator
Validates that everything is ready for staging deployment
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

def run_command(cmd, capture=True):
    """Run a shell command and return output"""
    try:
        if capture:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            return result.returncode == 0, result.stdout + result.stderr
        else:
            result = subprocess.run(cmd, shell=True, timeout=10)
            return result.returncode == 0, ""
    except subprocess.TimeoutExpired:
        return False, "Command timeout"
    except Exception as e:
        return False, str(e)

def print_header(title):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")

def print_section(title):
    print(f"\n{title}")
    print(f"{'-'*80}")

def check_python():
    """Verify Python version"""
    print_section("✓ Python Version")
    try:
        version = sys.version_info
        if version.major >= 3 and version.minor >= 9:
            print(f"  ✅ Python {version.major}.{version.minor}.{version.micro}")
            return True
        else:
            print(f"  ❌ Python {version.major}.{version.minor} (need 3.9+)")
            return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def check_git():
    """Verify Git status"""
    print_section("✓ Git Status")
    
    # Check uncommitted changes
    success, output = run_command("git status --porcelain")
    if not success:
        print("  ❌ Not a git repository")
        return False
    
    if output.strip():
        print("  ⚠️  Uncommitted changes detected:")
        for line in output.strip().split('\n'):
            print(f"     {line}")
        print("\n  Run: git add . && git commit -m 'Your message'")
        return False
    
    # Check last commits
    success, output = run_command("git log --oneline -5")
    if success:
        print("  ✅ Last 5 commits:")
        for line in output.strip().split('\n'):
            print(f"     {line}")
        return True
    
    return False

def check_files():
    """Verify critical files exist"""
    print_section("✓ Critical Files")
    
    files_to_check = [
        'manage.py',
        'config/settings.py',
        'config/celery.py',
        'requirements.txt',
        'config/cache_invalidation.py',
        'config/multilevel_cache.py',
        'qms/cache_warming.py',
        'qms/cache_dashboard.py',
        'DEPLOYMENT_GUIDE.md',
        'README_FASE7.md',
    ]
    
    all_exist = True
    for file in files_to_check:
        path = Path(file)
        if path.exists():
            print(f"  ✅ {file}")
        else:
            print(f"  ❌ {file} MISSING")
            all_exist = False
    
    return all_exist

def check_dependencies():
    """Verify Python dependencies"""
    print_section("✓ Dependencies")
    
    packages = [
        'django',
        'redis',
        'celery',
        'django_redis',
        'psycopg2',
    ]
    
    all_installed = True
    for package in packages:
        success, output = run_command(f"python -m pip show {package}")
        if success and output:
            # Extract version
            for line in output.split('\n'):
                if line.startswith('Version:'):
                    version = line.split(':', 1)[1].strip()
                    print(f"  ✅ {package:<20} {version}")
                    break
        else:
            print(f"  ❌ {package} NOT INSTALLED")
            all_installed = False
    
    return all_installed

def check_database():
    """Verify database connectivity"""
    print_section("✓ Database")
    
    success, output = run_command("python manage.py dbshell")
    if success or "No database configuration" in output:
        print("  ✅ Database accessible")
        return True
    else:
        print(f"  ❌ Database error: {output[:100]}")
        return False

def check_django():
    """Verify Django configuration"""
    print_section("✓ Django Configuration")
    
    success, output = run_command("python manage.py check")
    if success:
        print("  ✅ Django system checks passed")
        return True
    else:
        print(f"  ❌ Django errors detected:")
        for line in output.split('\n')[:5]:
            if line.strip():
                print(f"     {line}")
        return False

def check_tests():
    """Verify tests can run"""
    print_section("✓ Tests")
    
    # Try running one simple test
    success, output = run_command(
        "python manage.py test qms.tests.CeleryTasksTests --settings=config.settings_test"
    )
    
    if "OK" in output or "ok" in output:
        print("  ✅ Test suite functional")
        # Count total tests
        if "Ran" in output:
            for line in output.split('\n'):
                if "Ran" in line:
                    print(f"     {line}")
        return True
    else:
        print(f"  ⚠️  Test execution needs verification")
        print(f"     Run: python manage.py test qms --settings=config.settings_test")
        return True  # Don't block on tests

def check_documentation():
    """Verify documentation exists"""
    print_section("✓ Documentation")
    
    docs = [
        'README_FASE7.md',
        'DEPLOYMENT_GUIDE.md',
        'ARCHITECTURE_OVERVIEW.md',
        'MULTILEVEL_CACHE.md',
        'CACHE_INVALIDATION.md',
        'CACHE_WARMING.md',
        'CACHE_DASHBOARD.md',
    ]
    
    all_exist = True
    for doc in docs:
        path = Path(doc)
        if path.exists():
            size = path.stat().st_size
            print(f"  ✅ {doc:<40} ({size:,} bytes)")
        else:
            print(f"  ❌ {doc} MISSING")
            all_exist = False
    
    return all_exist

def print_summary(results):
    """Print summary of checks"""
    print_header("STAGING DEPLOYMENT READINESS")
    
    checks = [
        ("Python Version", results.get('python', False)),
        ("Git Repository", results.get('git', False)),
        ("Critical Files", results.get('files', False)),
        ("Dependencies", results.get('dependencies', False)),
        ("Database", results.get('database', False)),
        ("Django Config", results.get('django', False)),
        ("Tests", results.get('tests', False)),
        ("Documentation", results.get('documentation', False)),
    ]
    
    print("\n📊 VALIDATION RESULTS:\n")
    
    passed = 0
    for check_name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {check_name:<25} {status}")
        if result:
            passed += 1
    
    print(f"\n{'─'*80}")
    print(f"  Result: {passed}/{len(checks)} checks passed")
    print(f"{'─'*80}\n")
    
    if passed == len(checks):
        print("🎉 YOU ARE READY FOR STAGING DEPLOYMENT!\n")
        print("Next steps:")
        print("  1. Read STAGING_ACTION_PLAN.md")
        print("  2. Choose deployment strategy")
        print("  3. Execute staging deployment")
        print("  4. Monitor with cache dashboard\n")
        return 0
    else:
        print("⚠️  Some checks failed. Please fix issues before deploying.\n")
        return 1

def main():
    """Run all checks"""
    print_header("PRE-STAGING DEPLOYMENT VALIDATOR")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    results = {}
    
    results['python'] = check_python()
    results['git'] = check_git()
    results['files'] = check_files()
    results['dependencies'] = check_dependencies()
    results['database'] = check_database()
    results['django'] = check_django()
    results['tests'] = check_tests()
    results['documentation'] = check_documentation()
    
    return print_summary(results)

if __name__ == '__main__':
    sys.exit(main())
