#!/usr/bin/env python
"""Bootstrap helper for production: diagnose issues and run recovery tasks.

This script has two main modes:
  --diagnose : check for common deployment problems (SECRET_KEY, DB connectivity, pending migrations)
  --apply    : attempt to fix automatically (run migrate and create admin user from env vars, if provided)

CAUTION: When using --apply the script will run migrations and create a superuser non-interactively
if ADMIN_USERNAME/ADMIN_PASSWORD are present. Do NOT commit passwords to the repository.

Usages (examples):
  # Quick diagnosis
  python scripts/bootstrap_deploy.py --diagnose

  # Apply fixes (migrate + optional admin creation) -- make sure SECRET_KEY and DB are configured
  ADMIN_USERNAME=admin ADMIN_PASSWORD='S3cure!' python scripts/bootstrap_deploy.py --apply

This tool is helpful when executed as a one-off process on the host (container shell, SSH, platform console).
"""
import os
import sys


def main():
    import argparse

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

    # Ensure the project root is on sys.path so `config` and app modules can be imported
    proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if proj_root not in sys.path:
        sys.path.insert(0, proj_root)

    try:
        import django
        from django.contrib.auth import get_user_model
        from django.core.management import call_command
        from django.db import connections
        from django.db.migrations.executor import MigrationExecutor
    except Exception as exc:  # pragma: no cover - environment-dependent
        print('Error importing Django or DB modules:', exc)
        sys.exit(1)

    parser = argparse.ArgumentParser(description='Bootstrap / diagnose deployment')
    parser.add_argument('--diagnose', action='store_true', help='Run diagnostics and print results')
    parser.add_argument('--apply', action='store_true', help='Apply migrations and create admin if env vars set')
    args = parser.parse_args()

    django.setup()

    def check_secret_key():
        from django.conf import settings

        sk = getattr(settings, 'SECRET_KEY', None)
        present = bool(sk and 'insecure' not in sk.lower())
        return present, sk if present else None

    def check_db_connection():
        try:
            conn = connections['default']
            conn.ensure_connection()
            return True, 'Database connected'
        except Exception as e:
            return False, str(e)

    def check_pending_migrations():
        try:
            conn = connections['default']
            executor = MigrationExecutor(conn)
            targets = executor.loader.graph.leaf_nodes()
            plan = executor.migration_plan(targets)
            return len(plan) > 0, plan
        except Exception as e:
            return False, str(e)

    if args.diagnose:
        print('\n=== DIAGNOSTIC REPORT ===')
        sk_ok, sk_val = check_secret_key()
        print(f'SECRET_KEY present: {sk_ok}')
        if not sk_ok:
            print('  - SECRET_KEY is missing or insecure (production requires a secure key)')

        db_ok, db_msg = check_db_connection()
        print(f'DB connection: {db_ok} -> {db_msg}')

        pending, plan = check_pending_migrations()
        print(f'Pending migrations: {pending}')
        if pending:
            print('Migration plan items:')
            for item in plan:
                print(' -', item)

        print('\nDiagnostic finished. To apply fixes run with --apply')
        return

    if args.apply:
        # Apply migrations (non-interactive)
        print('Running migrations (migrate --noinput) ...')
        try:
            call_command('migrate', interactive=False)
        except Exception as e:
            print('Error running migrations:', e)
            sys.exit(1)

        # Auto-create admin if env vars present
        username = os.environ.get('ADMIN_USERNAME')
        password = os.environ.get('ADMIN_PASSWORD')
        email = os.environ.get('ADMIN_EMAIL', 'admin@example.com')

        if username and password:
            User = get_user_model()
            if not User.objects.filter(username=username).exists():
                print(f"Creating superuser '{username}' from environment variables...")
                User.objects.create_superuser(username, email, password)
                print('Superuser created')
            else:
                print('Superuser already exists — skipping creation')
        else:
            print('ADMIN_USERNAME and ADMIN_PASSWORD env vars not provided — skipping superuser creation')

        print('Apply finished — validate /healthz and restart the process if necessary')
        return

    print('No action requested. Use --diagnose to inspect production environment or --apply to attempt fixes')


if __name__ == '__main__':
    main()
