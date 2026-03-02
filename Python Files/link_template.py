#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from procedures.models import ListaPresenca, TemplateListaPresenca

# Vincular template à lista 3474
lista = ListaPresenca.objects.get(id=3474)
template = TemplateListaPresenca.objects.first()
lista.template = template
lista.save()

print(f"Lista {lista.id} agora tem template: {lista.template}")
