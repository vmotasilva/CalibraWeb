#!/usr/bin/env python
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from metrologia.models import Instrumento, ItemCotacao

# Find instruments with quotations
print("Instrumentos com cotações:\n")

instruments_with_cotacoes = Instrumento.objects.filter(cotacoes_itens__isnull=False).distinct()
for inst in instruments_with_cotacoes[:10]:
    cotacao_count = ItemCotacao.objects.filter(instrumento=inst).count()
    print(f"  - {inst.tag} (ID: {inst.id}): {cotacao_count} cotação(ões)")
