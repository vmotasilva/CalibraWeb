#!/usr/bin/env python
"""Bootstrap helper for production: run migrations and create superuser from environment.

Use with caution: this reads ADMIN_USERNAME and ADMIN_PASSWORD from environment variables
and will create a superuser non-interactively. Do NOT commit passwords.

Usage (example):
  ADMIN_USERNAME=admin ADMIN_EMAIL=you@example.com ADMIN_PASSWORD='S3cure!' python scripts/bootstrap_deploy.py

This script is handy to run in a remote one-off process (eg. Railway console) to bring
the application into a runnable state after deployments or data loss.
"""
import os
import sys

if __name__ == "__main__":
    # Minimal guard so this file can be executed as a one-off script
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    try:
        import django
        from django.contrib.auth import get_user_model
        from django.core.management import call_command
    except Exception as e:
        print("Error importing Django:", e)
        sys.exit(1)

    django.setup()

    # Run migrations
    print("Running migrations...")
    call_command("migrate", interactive=False)

    # Auto-create admin if env vars present
    username = os.environ.get("ADMIN_USERNAME")
    password = os.environ.get("ADMIN_PASSWORD")
    email = os.environ.get("ADMIN_EMAIL", "admin@example.com")

    if username and password:
        User = get_user_model()
        if not User.objects.filter(username=username).exists():
            print(f"Creating superuser '{username}' from environment variables...")
            User.objects.create_superuser(username, email, password)
            print("Superuser created")
        else:
            print("Superuser already exists — skipping creation")
    else:
        print(
            "ADMIN_USERNAME and ADMIN_PASSWORD env vars not provided — skipping superuser creation"
        )

    print("Bootstrap finished — check logs and restart your process if needed")
