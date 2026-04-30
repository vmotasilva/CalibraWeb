#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import django

sys.path.insert(0, 'c:\\CalibraWeb')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from metrologia.models import Instrumento

# Buscar TH-05
inst = Instrumento.objects.filter(tag__contains='05').first()
if inst:
    print(f"\n=== INSTRUMENTO ===")
    print(f"ID: {inst.id}")
    print(f"Tag: '{inst.tag}'")
    print(f"Codigo: '{inst.codigo}'")
    print(f"Modelo: {inst.modelo}")
    print(f"Serie: {inst.serie}")
else:
    print("Não encontrou")

print("\n")
