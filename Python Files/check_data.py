#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'calibraweb.settings')
django.setup()

from acoes.models import AcaoCorretiva
from django.utils import timezone

hoje = timezone.now().date()

print('=== STATUS COUNT ===')
print(f'Concluída: {AcaoCorretiva.objects.filter(status="concluida").count()}')
print(f'Em Progresso: {AcaoCorretiva.objects.filter(status="em_progresso").count()}')
print(f'Cancelada: {AcaoCorretiva.objects.filter(status="cancelada").count()}')
print(f'Aberta: {AcaoCorretiva.objects.filter(status="aberta").count()}')
print(f'Atrasada (aberta + vencimento < hoje): {AcaoCorretiva.objects.filter(status="aberta", data_vencimento__lt=hoje).count()}')
print()

print('=== TIPO SOLUÇÃO (Unique) ===')
tipos = set(t for t in AcaoCorretiva.objects.values_list('tipo_solucao', flat=True) if t)
for t in sorted(tipos):
    print(f'  {t}')
print()

print('=== ORIGEM (Unique - First 20) ===')
origens = set(o for o in AcaoCorretiva.objects.values_list('origem', flat=True) if o)
for o in sorted(origens)[:20]:
    print(f'  {o}')
if len(origens) > 20:
    print(f'  ... e mais {len(origens) - 20}')
