#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from metrologia.models import Instrumento
from datetime import date, timedelta

today = date.today()
print(f"Today: {today}")
print(f"Total: {Instrumento.objects.count()}")
print(f"Ativos: {Instrumento.objects.filter(ativo=True).count()}")

vencidos = Instrumento.objects.filter(data_proxima_calibracao__lt=today, ativo=True).count()
print(f"Vencidos (< today): {vencidos}")

thirty_days = today + timedelta(days=30)
avencer = Instrumento.objects.filter(
    data_proxima_calibracao__gte=today, 
    data_proxima_calibracao__lte=thirty_days,
    ativo=True
).count()
print(f"A vencer (>= today e <= 30 days): {avencer}")

vigentes = Instrumento.objects.filter(data_proxima_calibracao__gt=thirty_days, ativo=True).count()
print(f"Vigentes (> 30 days): {vigentes}")

# Amostra de dados
print("\n--- Amostra (primeiros 10) ---")
for inst in Instrumento.objects.all().order_by('tag')[:10]:
    status = "?" 
    if inst.data_proxima_calibracao:
        if inst.data_proxima_calibracao < today:
            status = "vencido"
        elif inst.data_proxima_calibracao <= thirty_days:
            status = "a vencer"
        else:
            status = "vigente"
    else:
        status = "sem data"
    
    print(f"{inst.tag}: {inst.data_proxima_calibracao} (ativo={inst.ativo}) -> {status}")
