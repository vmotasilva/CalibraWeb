"""
Management command to create a superuser from environment variables.
Usage: python manage.py ensure_superuser
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
import os


class Command(BaseCommand):
    help = "Create superuser if it doesn't exist (from env vars or prompts)"

    def handle(self, *args, **options):
        User = get_user_model()
        
        username = os.getenv("DJANGO_SUPERUSER_USERNAME", "admin")
        email = os.getenv("DJANGO_SUPERUSER_EMAIL", "admin@example.com")
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD")
        
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f"Superuser '{username}' already exists.")
            )
            return
        
        if not password:
            self.stdout.write(
                self.style.ERROR(
                    "DJANGO_SUPERUSER_PASSWORD not set. Cannot create superuser."
                )
            )
            self.stdout.write("Run: python manage.py createsuperuser")
            return
        
        User.objects.create_superuser(
            username=username, email=email, password=password
        )
        self.stdout.write(
            self.style.SUCCESS(f"Superuser '{username}' created successfully!")
        )
