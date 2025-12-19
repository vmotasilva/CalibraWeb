"""
Test both ways to get padroes
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from metrologia.models import HistoricoCalibracao, ArquivoPadrao

# Get historico 354 (from the image)
try:
    h = HistoricoCalibracao.objects.get(id=354)
    
    print(f"Historico ID: {h.id}")
    print(f"Instrumento: {h.instrumento}")
    
    # Test 1: Via related_name
    print(f"\nTest 1: historico.padroes_arquivo.count()")
    count1 = h.padroes_arquivo.count()
    print(f"  Count: {count1}")
    for p in h.padroes_arquivo.all():
        print(f"    - {p.id}: {p.nome}")
    
    # Test 2: Via queryset filter
    print(f"\nTest 2: ArquivoPadrao.objects.filter(historico=historico).count()")
    count2 = ArquivoPadrao.objects.filter(historico=h).count()
    print(f"  Count: {count2}")
    for p in ArquivoPadrao.objects.filter(historico=h):
        print(f"    - {p.id}: {p.nome}")
        
    # Test 3: Via prefetch
    print(f"\nTest 3: With prefetch_related")
    h3 = HistoricoCalibracao.objects.prefetch_related('padroes_arquivo').get(id=354)
    count3 = h3.padroes_arquivo.count()
    print(f"  Count: {count3}")
    for p in h3.padroes_arquivo.all():
        print(f"    - {p.id}: {p.nome}")
        
except HistoricoCalibracao.DoesNotExist:
    print("Historico 354 not found")
    
    # Check what historicos exist
    all_h = HistoricoCalibracao.objects.all()[:5]
    print(f"\nAvailable historicos:")
    for h in all_h:
        print(f"  - {h.id}")
