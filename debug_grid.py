import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
django.setup()

from laboratorio.models import RegistroCoating
from datetime import datetime, timedelta, time
from django.utils import timezone

qs = RegistroCoating.objects.filter(turno_coating__data='2026-07-28', turno_coating__regra__nome='TURNO 02', maquina__codigo='DLX1200').order_by('hora_entrada')

for reg in qs:
    # Mimic views.py logic exactly
    hora_entrada_dt = reg.hora_entrada
    hora_saida_dt = reg.hora_saida
    
    if hora_entrada_dt and timezone.is_aware(hora_entrada_dt):
        hora_entrada_dt = timezone.localtime(hora_entrada_dt).replace(tzinfo=None)
    if hora_saida_dt and timezone.is_aware(hora_saida_dt):
        hora_saida_dt = timezone.localtime(hora_saida_dt).replace(tzinfo=None)
        
    if isinstance(hora_entrada_dt, time):
        hora_entrada_dt = datetime.combine(reg.turno_coating.data, hora_entrada_dt)
    if isinstance(hora_saida_dt, time):
        hora_saida_dt = datetime.combine(reg.turno_coating.data, hora_saida_dt)
        
    hora_inicio_turno = None
    if reg.turno_coating and reg.turno_coating.regra:
        if reg.turno_coating.regra.hora_inicio:
            hora_inicio_turno = datetime.combine(reg.turno_coating.data, reg.turno_coating.regra.hora_inicio)
            
    if hora_inicio_turno:
        if hora_entrada_dt and hora_entrada_dt.hour < 12 and hora_inicio_turno.hour > 12:
            hora_entrada_dt += timedelta(days=1)
            
    print(f"Lote {reg.lote} {reg.lado}: Entrada={hora_entrada_dt} Inicio={hora_inicio_turno}")
    if hora_entrada_dt and hora_inicio_turno:
        diff = (hora_entrada_dt - hora_inicio_turno).total_seconds()
        print(f"  Diff seconds: {diff} (which is {diff/3600} hours)")
