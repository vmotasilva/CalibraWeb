import os
import django

# Configura o Django para rodar o script
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# Só cria se não existir
if not User.objects.filter(username='admin').exists():
    print("Criando usuario admin...")
    User.objects.create_superuser('admin', 'admin@exemplo.com', 'admin123')
    print("Pronto! Usuario criado.")
else:
    print("Usuario admin ja existe.")