"""
Test script to verify prefetch_related works with padroes_arquivo
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from metrologia.models import HistoricoCalibracao, ArquivoPadrao
from django.db.models import Prefetch

# Get a historico with padroes
historicos = HistoricoCalibracao.objects.filter(padroes_arquivo__isnull=False).distinct()

if historicos.exists():
    h_id = historicos.first().id
    print(f"Testing with historico ID: {h_id}")
    
    # Test 1: Without prefetch_related
    print("\n[Test 1] Without prefetch_related:")
    h1 = HistoricoCalibracao.objects.get(id=h_id)
    count1 = h1.padroes_arquivo.count()
    print(f"  Count: {count1}")
    print(f"  padroes_arquivo.all: {list(h1.padroes_arquivo.all())}")
    
    # Test 2: With prefetch_related
    print("\n[Test 2] With prefetch_related:")
    h2 = HistoricoCalibracao.objects.prefetch_related('padroes_arquivo').get(id=h_id)
    count2 = h2.padroes_arquivo.count()
    print(f"  Count: {count2}")
    print(f"  padroes_arquivo.all: {list(h2.padroes_arquivo.all())}")
    
    # Test 3: Check if both are equal
    print(f"\n[Test 3] Results match: {count1 == count2}")
    
    if count2 > 0:
        print("\n✅ Prefetch_related working correctly!")
        for p in h2.padroes_arquivo.all():
            print(f"  - {p.nome}")
    else:
        print("\n❌ No padrões found!")
else:
    print("No historicos with padroes found.")
