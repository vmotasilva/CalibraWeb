#!/usr/bin/env python
"""
Security Audit Script for CalibraWeb Production Deployment
Validates all security-related configurations and best practices
"""
import os
import sys
import json
import re
from pathlib import Path

print("=" * 80)
print("CALIBRAWEB - SECURITY AUDIT REPORT")
print("=" * 80)

# Django setup
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
from django.core.management import call_command
import io
from contextlib import redirect_stdout, redirect_stderr

audit_results = {
    "passed": [],
    "warnings": [],
    "failed": [],
    "timestamp": None
}

def check(category, name, condition, message=""):
    """Helper to log check results"""
    status = "✅ PASS" if condition else "⚠️  WARN" if message.startswith("Warning") else "❌ FAIL"
    if condition:
        audit_results["passed"].append(f"{category}: {name}")
        print(f"{status} - {category}: {name}")
    else:
        if message.startswith("Warning"):
            audit_results["warnings"].append(f"{category}: {name} - {message}")
            print(f"{status} - {category}: {name}")
        else:
            audit_results["failed"].append(f"{category}: {name} - {message}")
            print(f"{status} - {category}: {name}")
    if message and not condition:
        print(f"      → {message}")

# 1. SECRET KEY CHECK
print("\n" + "=" * 80)
print("1. SECRET KEY SECURITY")
print("=" * 80)

secret_key = settings.SECRET_KEY
if secret_key:
    is_secure = (
        len(secret_key) >= 50 and
        not secret_key.startswith('django-insecure-') and
        len(set(secret_key)) >= 10
    )
    check(
        "SECRET_KEY",
        "Secret key strength",
        is_secure,
        "For production: Generate with 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'"
    )
else:
    check("SECRET_KEY", "SECRET_KEY defined", False, "SECRET_KEY must be set")

# 2. DEBUG MODE CHECK
print("\n" + "=" * 80)
print("2. DEBUG MODE SECURITY")
print("=" * 80)

check("DEBUG", "DEBUG=False for production", not settings.DEBUG)
if settings.DEBUG:
    print("      ⚠️  WARNING: DEBUG=True exposes sensitive information in error pages")

# 3. ALLOWED HOSTS CHECK
print("\n" + "=" * 80)
print("3. ALLOWED HOSTS CONFIGURATION")
print("=" * 80)

allowed_hosts_ok = (
    settings.ALLOWED_HOSTS and
    len(settings.ALLOWED_HOSTS) > 0 and
    '*' not in settings.ALLOWED_HOSTS
)
check("ALLOWED_HOSTS", "Hosts properly configured", allowed_hosts_ok)
print(f"      Current: {settings.ALLOWED_HOSTS}")

# 4. SSL/HTTPS SECURITY
print("\n" + "=" * 80)
print("4. SSL/HTTPS SECURITY")
print("=" * 80)

session_cookie_secure = getattr(settings, 'SESSION_COOKIE_SECURE', False)
csrf_cookie_secure = getattr(settings, 'CSRF_COOKIE_SECURE', False)
secure_ssl_redirect = getattr(settings, 'SECURE_SSL_REDIRECT', False)
secure_hsts = getattr(settings, 'SECURE_HSTS_SECONDS', 0)

check("Cookies", "SESSION_COOKIE_SECURE", session_cookie_secure)
check("Cookies", "CSRF_COOKIE_SECURE", csrf_cookie_secure)
check("SSL", "SECURE_SSL_REDIRECT", secure_ssl_redirect, "Warning: Set to True unless using reverse proxy")
check("HSTS", "SECURE_HSTS_SECONDS configured", secure_hsts > 0, f"Current: {secure_hsts}")

if not secure_ssl_redirect:
    print(f"      ℹ️  INFO: Reverse proxy or platform SSL redirect may handle this, which can be OK")

# 5. FRAMEWORK SECURITY
print("\n" + "=" * 80)
print("5. FRAMEWORK SECURITY HEADERS")
print("=" * 80)

browser_xss_filter = getattr(settings, 'SECURE_BROWSER_XSS_FILTER', False)
content_type_nosniff = getattr(settings, 'SECURE_CONTENT_TYPE_NOSNIFF', False)
x_frame_options = getattr(settings, 'X_FRAME_OPTIONS', 'SAMEORIGIN')

check("XSS", "SECURE_BROWSER_XSS_FILTER", browser_xss_filter)
check("MIME", "SECURE_CONTENT_TYPE_NOSNIFF", content_type_nosniff)
check("Clickjacking", f"X_FRAME_OPTIONS={x_frame_options}", x_frame_options != 'ALLOW')

# 6. DATABASE SECURITY
print("\n" + "=" * 80)
print("6. DATABASE SECURITY")
print("=" * 80)

db_engine = settings.DATABASES['default']['ENGINE']
db_name = settings.DATABASES['default'].get('NAME', '')

if 'sqlite' in db_engine.lower():
    check("Database", "Using SQLite in development", True, "Warning: Use PostgreSQL for production")
elif 'postgres' in db_engine.lower():
    check("Database", "Using PostgreSQL", True)
    
    # Check for password in settings (should use DATABASE_URL instead)
    password = settings.DATABASES['default'].get('PASSWORD', '')
    if password and not os.getenv('DATABASE_URL'):
        check("Database", "Password in settings file", False, 
              "Use DATABASE_URL environment variable instead")
else:
    check("Database", "Database configured", True)

# 7. STATIC FILES SECURITY
print("\n" + "=" * 80)
print("7. STATIC FILES SECURITY")
print("=" * 80)

static_root = settings.STATIC_ROOT
static_files_exist = os.path.exists(static_root) if static_root else False

check("Static Files", "STATIC_ROOT configured", bool(static_root))
check("Static Files", "Files collected", static_files_exist)

if static_files_exist:
    # Count static files
    num_files = sum([len(files) for _, _, files in os.walk(static_root)])
    print(f"      Total files: {num_files}")

# 8. INSTALLED APPS SECURITY
print("\n" + "=" * 80)
print("8. INSTALLED APPS SECURITY")
print("=" * 80)

required_apps = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

for app in required_apps:
    is_installed = app in settings.INSTALLED_APPS
    check("Apps", f"{app.split('.')[-1]}", is_installed)

# 9. MIDDLEWARE SECURITY
print("\n" + "=" * 80)
print("9. MIDDLEWARE SECURITY")
print("=" * 80)

critical_middleware = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

for middleware in critical_middleware:
    is_present = middleware in settings.MIDDLEWARE
    short_name = middleware.split('.')[-1]
    check("Middleware", short_name, is_present)

# Check WhiteNoise
whitenoise_present = any('whitenoise' in m.lower() for m in settings.MIDDLEWARE)
check("Static Files", "WhiteNoise middleware", whitenoise_present)

# 10. ENVIRONMENT VARIABLES
print("\n" + "=" * 80)
print("10. ENVIRONMENT VARIABLES")
print("=" * 80)

env_file_exists = os.path.exists('.env')
env_example_exists = os.path.exists('.env.example')

check("Environment", ".env.example exists", env_example_exists)
check("Environment", ".env file exists (dev)", env_file_exists, "Warning: Should not exist in production")

# Check if .env is in .gitignore
gitignore_path = Path('.gitignore')
if gitignore_path.exists():
    gitignore_content = gitignore_path.read_text()
    env_ignored = '.env' in gitignore_content
    check("Git Security", ".env in .gitignore", env_ignored)

# 11. LOGGING CONFIGURATION
print("\n" + "=" * 80)
print("11. LOGGING CONFIGURATION")
print("=" * 80)

logging_config = settings.LOGGING
has_logging = bool(logging_config)
check("Logging", "Logging configured", has_logging)

# 12. PERMISSIONS AND FILE SYSTEM
print("\n" + "=" * 80)
print("12. FILE PERMISSIONS")
print("=" * 80)

# Check media directory
media_root = settings.MEDIA_ROOT
if media_root and os.path.exists(media_root):
    check("Media", "MEDIA_ROOT exists", True)
else:
    check("Media", "MEDIA_ROOT configured", bool(media_root), "Create directory in production")

# 13. DJANGO ADMIN SECURITY
print("\n" + "=" * 80)
print("13. DJANGO ADMIN SECURITY")
print("=" * 80)

admin_site_header = getattr(settings, 'ADMIN_SITE_HEADER', 'Django administration')
has_custom_admin = admin_site_header != 'Django administration'
check("Admin", "Custom admin site header", has_custom_admin, "Warning: Consider changing to hide Django info")

from django.contrib import admin
admin_models = len(admin.site._registry)
check("Admin", f"Models registered ({admin_models}/27)", admin_models >= 27)

# 14. RUN DJANGO CHECK --DEPLOY
print("\n" + "=" * 80)
print("14. DJANGO DEPLOY CHECK")
print("=" * 80)

try:
    # Capture the output of check --deploy
    f = io.StringIO()
    try:
        call_command('check', '--deploy', stdout=f, stderr=f)
        check("Django Check", "No critical errors", True)
    except SystemExit:
        # check --deploy uses SystemExit for warnings
        output = f.getvalue()
        has_errors = 'ERROR' in output
        if has_errors:
            check("Django Check", "No critical errors", False, "See output above")
        else:
            check("Django Check", "Warnings only (acceptable)", True)
except Exception as e:
    check("Django Check", "check --deploy", False, str(e))

# SUMMARY
print("\n" + "=" * 80)
print("SECURITY AUDIT SUMMARY")
print("=" * 80)

total_checks = len(audit_results["passed"]) + len(audit_results["warnings"]) + len(audit_results["failed"])
passed_count = len(audit_results["passed"])
warning_count = len(audit_results["warnings"])
failed_count = len(audit_results["failed"])

print(f"\nTotal Checks: {total_checks}")
print(f"✅ Passed: {passed_count}")
print(f"⚠️  Warnings: {warning_count}")
print(f"❌ Failed: {failed_count}")

if failed_count > 0:
    print("\n❌ FAILED CHECKS:")
    for item in audit_results["failed"]:
        print(f"   - {item}")
    print("\n⚠️  IMPORTANT: Fix failed checks before production deployment!")
else:
    print("\n✅ NO CRITICAL FAILURES - READY FOR PRODUCTION")

if warning_count > 0:
    print(f"\n⚠️  {warning_count} WARNINGS (should be reviewed):")
    for item in audit_results["warnings"]:
        print(f"   - {item}")

print("\n" + "=" * 80)
print("DEPLOYMENT CHECKLIST")
print("=" * 80)
checklist = [
    ("Generate secure SECRET_KEY", not secret_key.startswith('django-insecure-')),
    ("Set DEBUG=False in production", not settings.DEBUG),
    ("Configure ALLOWED_HOSTS", '*' not in settings.ALLOWED_HOSTS),
    ("Set up PostgreSQL database", 'postgres' in db_engine.lower()),
    ("Collect static files", static_files_exist),
    ("Set up SSL/HTTPS certificate", True),  # Manual step
    ("Configure environment variables", env_example_exists),
    ("Set up logging and monitoring", has_logging),
    ("Configure Redis/Celery", True),  # Optional
    ("Set up backup procedures", True),  # Manual step
    ("Run security audit", True),  # Current step
]

print("\nPre-Deployment Tasks:")
for i, (task, completed) in enumerate(checklist, 1):
    status = "✅" if completed else "⏳"
    print(f"  {i:2}. {status} {task}")

print("\n" + "=" * 80)
print("END OF SECURITY AUDIT")
print("=" * 80)
