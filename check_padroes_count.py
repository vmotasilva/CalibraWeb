"""
Check which historico has the 14 padroes
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from metrologia.models import HistoricoCalibracao, ArquivoPadrao
from django.db.models import Count

# Get all historicos with padroes
historicos = HistoricoCalibracao.objects.annotate(
    padroes_count=Count('padroes_arquivo')
).filter(padroes_count__gt=0).order_by('-padroes_count')

print("Historicos com padroes:")
for h in historicos[:5]:
    count = h.padroes_arquivo.count()
    print(f"  ID {h.id}: {count} padroes - {h.instrumento}")

# Get the one with most padroes
if historicos.exists():
    h_max = historicos.first()
    print(f"\nHistorico com mais padroes: ID {h_max.id} ({h_max.padroes_count})")
    print("Padroes:")
    for p in h_max.padroes_arquivo.all():
        print(f"  - {p.id}: {p.nome}")
