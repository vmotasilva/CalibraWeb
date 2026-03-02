#!/usr/bin/env python
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, r'c:\CalibraWeb')

django.setup()

from procedures.models import MapeamentoCampoListaPresenca
from django.db.models import Count

# Verificar se ainda há duplicatas
duplicatas = MapeamentoCampoListaPresenca.objects.values('template_id', 'placeholder').annotate(count=Count('id')).filter(count__gt=1)

if duplicatas.exists():
    print('⚠️ Ainda existem duplicatas:')
    for dup in duplicatas:
        print(f'  Template {dup["template_id"]}, Placeholder "{dup["placeholder"]}": {dup["count"]} registros')
else:
    print('✓ Nenhuma duplicata encontrada!')

# Mostrar total de registros
total = MapeamentoCampoListaPresenca.objects.count()
print(f'✓ Total de mapeamentos: {total}')

# Mostrar detalhes por template
print('\n✓ Mapeamentos por template:')
for m in MapeamentoCampoListaPresenca.objects.select_related('template').order_by('template__nome'):
    print(f'  {m.template.nome}: {m.placeholder} → {m.get_campo_dados_display()}')
