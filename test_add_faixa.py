#!/usr/bin/env python
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from metrologia.models import HistoricoCalibracao, ResultadoFaixaCalibracao, FaixaMedicao

# Create test user if needed
user, created = User.objects.get_or_create(
    username='testuser',
    defaults={'is_staff': True, 'is_superuser': True}
)
if created:
    user.set_password('testpass123')
    user.save()

# Test with historico 127
historico = HistoricoCalibracao.objects.get(id=127)
print(f"Histórico: {historico}")
print(f"Instrumento: {historico.instrumento}")

# Get available faixas
faixas = FaixaMedicao.objects.filter(instrumento=historico.instrumento).order_by('valor_minimo')
print(f"\nFaixas disponíveis: {faixas.count()}")
for f in faixas:
    print(f"  - {f.id}: {f.valor_minimo} a {f.valor_maximo}")

# Get current results
resultados = historico.resultados_faixa.all()
print(f"\nResultados atuais: {resultados.count()}")
for r in resultados:
    print(f"  - {r.id}: {r.valor_minimo} a {r.valor_maximo}")

# Try to add a faixa
if faixas.exists():
    faixa_to_add = faixas[0]
    print(f"\nTentando adicionar faixa: {faixa_to_add.id} ({faixa_to_add.valor_minimo} a {faixa_to_add.valor_maximo})")
    
    resultado, created = ResultadoFaixaCalibracao.objects.get_or_create(
        historico=historico,
        faixa=faixa_to_add,
        defaults={
            'valor_minimo': faixa_to_add.valor_minimo,
            'valor_maximo': faixa_to_add.valor_maximo,
        }
    )
    
    if created:
        print(f"✓ Faixa criada com sucesso! ID: {resultado.id}")
    else:
        print(f"⚠ Faixa já existia. ID: {resultado.id}")
    
    # Verify
    new_count = historico.resultados_faixa.all().count()
    print(f"\nResultados após: {new_count}")
