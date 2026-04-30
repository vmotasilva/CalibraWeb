#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from procedures.models import TemplateListaPresenca

# Listar templates
templates = TemplateListaPresenca.objects.all()[:3]
print(f"Total de templates: {TemplateListaPresenca.objects.count()}")
for tmpl in templates:
    print(f"ID: {tmpl.id}, Nome: {tmpl.nome}, Mapeamentos: {tmpl.mapeamentos.count()}")

