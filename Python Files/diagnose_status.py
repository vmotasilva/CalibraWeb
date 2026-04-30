import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'calibraweb.settings')
django.setup()

from acoes.models import AcaoCorretiva
from django.utils import timezone

hoje = timezone.now().date()

print('=== STATUS DISTRIBUTION ===')
for status in ['aberta', 'em_progresso', 'concluida', 'cancelada', 'em_andamento']:
    count = AcaoCorretiva.objects.filter(status=status).count()
    if count > 0:
        print(f'{status}: {count}')

print('\n=== ALL UNIQUE STATUS VALUES ===')
status_values = set(AcaoCorretiva.objects.values_list('status', flat=True))
print(f'Unique status values: {status_values}')

print('\n=== SAMPLE RECORDS ===')
for acao in AcaoCorretiva.objects.all()[:5]:
    print(f'ID: {acao.id}, Nº: {acao.numero_registro}, Status: "{acao.status}", Data Venc: {acao.data_vencimento}')
