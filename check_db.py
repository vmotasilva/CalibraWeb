import django
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from auditoria.models import ItemNorma
items = ItemNorma.objects.filter(referencia__startswith='5.1')
for item in items:
    print(f"{item.referencia} - is_parent: {item.is_parent if hasattr(item, 'is_parent') else 'N/A'}")
