#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from metrologia.models import FaixaMedicao, Instrumento

# Find instruments with potential duplicate faixas
for inst in Instrumento.objects.all()[:5]:
    faixas = inst.faixas.all().order_by('valor_minimo', 'valor_maximo')
    if faixas.count() > 0:
        print(f"\n{inst.tag} ({inst.id}): {faixas.count()} faixas")
        seen = {}
        for f in faixas:
            key = f"{f.valor_minimo},{f.valor_maximo},{f.unidade.id}"
            if key in seen:
                print(f"  DUPLICATE: {f.valor_minimo}-{f.valor_maximo} ({f.unidade.nome}) ID:{f.id} [also ID:{seen[key]}]")
            else:
                print(f"  - {f.valor_minimo} a {f.valor_maximo} {f.unidade.nome} (ID:{f.id})")
                seen[key] = f.id
