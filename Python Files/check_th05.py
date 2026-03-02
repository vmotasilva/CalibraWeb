#!/usr/bin/env python
import os, sys, django
sys.path.insert(0, 'c:\\CalibraWeb')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from metrologia.models import Instrumento

# Procurar especificamente TH-05
inst = Instrumento.objects.filter(tag='TH-05').first()
if inst:
    print(f"Tag armazenada: '{inst.tag}'")
    print(f"ID: {inst.id}")
else:
    print("TH-05 não encontrado")
    # Listar TH
    ths = Instrumento.objects.filter(tag__startswith='TH')
    for t in ths[:5]:
        print(f"  - {t.tag}")
