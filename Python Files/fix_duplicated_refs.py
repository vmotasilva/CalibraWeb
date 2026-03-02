#!/usr/bin/env python
import os, sys, django
sys.path.insert(0, 'c:\\CalibraWeb')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from metrologia.models import InstrumentoReferencia

# Encontrar e corrigir duplicações
refs = InstrumentoReferencia.objects.all()
print(f"Total de referências: {refs.count()}")

for ref in refs:
    original = ref.codigo_referencia
    
    # Procurar padrão duplicado (ex: TH-TH-05)
    if '-' in original:
        parts = original.split('-')
        if len(parts) >= 3:  # Ex: ['TH', 'TH', '05']
            if parts[0] == parts[1]:  # Duplicado
                corrected = f"{parts[0]}-{'-'.join(parts[2:])}"
                print(f"  Corrigindo: '{original}' → '{corrected}'")
                ref.codigo_referencia = corrected
                ref.save()
            else:
                print(f"  OK: {original}")
        else:
            print(f"  OK: {original}")
    else:
        print(f"  OK: {original}")

print(f"\n✓ Correcção concluída")
