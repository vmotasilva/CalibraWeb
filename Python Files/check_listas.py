#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from procedures.models import ListaPresenca

# Listar primeiras 3 listas com template
listas = ListaPresenca.objects.all()[:3]
for lista in listas:
    print(f"ID: {lista.id}, Titulo: {lista.titulo}, Template: {lista.template}")
