import os
import django
from django.contrib.auth import get_user_model

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

User = get_user_model()

ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME')
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')

if not ADMIN_USERNAME or not ADMIN_PASSWORD:
    print("Environment variables ADMIN_USERNAME and ADMIN_PASSWORD are required to create a superuser.")
    print("Use 'python manage.py createsuperuser' to create a user interactively, or set the env vars and run this script again.")
else:
    if not User.objects.filter(username=ADMIN_USERNAME).exists():
        User.objects.create_superuser(ADMIN_USERNAME, ADMIN_EMAIL, ADMIN_PASSWORD)
        print("Superuser created successfully")
    else:
        print(f"Superuser '{ADMIN_USERNAME}' already exists")