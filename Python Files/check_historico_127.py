#!/usr/bin/env python
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from metrologia.models import HistoricoCalibracao, ResultadoFaixaCalibracao

# Check historico 127
historico = HistoricoCalibracao.objects.get(id=127)
print(f"Historico 127: {historico}")
print(f"Instrumento: {historico.instrumento}")

# Check resultados_faixa
resultados = historico.resultados_faixa.all()
print(f"\nNumber of ResultadoFaixaCalibracao records: {resultados.count()}")

# Check all ResultadoFaixaCalibracao records
all_results = ResultadoFaixaCalibracao.objects.filter(historico_id=127)
print(f"Direct query count: {all_results.count()}")

# Show some details
if all_results.exists():
    for r in all_results[:3]:
        print(f"  ID: {r.id}, Min: {r.valor_minimo}, Max: {r.valor_maximo}, Resultado: {r.resultado}")
else:
    print("No records found!")
