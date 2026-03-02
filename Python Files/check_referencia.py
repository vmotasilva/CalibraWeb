#!/usr/bin/env python
import os, sys, django
sys.path.insert(0, 'c:\\CalibraWeb')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from metrologia.models import Instrumento, InstrumentoReferencia

inst = Instrumento.objects.get(id=109)
print(f"Instrumento: {inst.tag}")
print(f"Referencia: {inst.referencia}")
if inst.referencia:
    print(f"Codigo Referencia: '{inst.referencia.codigo_referencia}'")
    print(f"Full str: {str(inst.referencia)}")
