import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from laboratorio.models import CicloManutencaoCoating
c = CicloManutencaoCoating.objects.filter(nome__icontains='Espessura').first()
if c:
    print("Name:", c.nome)
    print("Min:", c.valor_minimo)
    print("Max:", c.valor_maximo)
else:
    print("Not found")
