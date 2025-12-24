#!/usr/bin/env python
"""Script para diversificar dados de procedimentos para teste dos filtros."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from procedures.models import Procedimento

# Atualizar classificações para diversificar
classificacoes_variedade = ['POP', 'IT', 'Formulário', 'Instrução', 'Manual', 'Política', 'Procedimento']
matrizes_variedade = ['Matriz Principal', 'Matriz Secundária', 'Matriz Terceira']
sub_areas_variedade = ['Área de Processos', 'Área de Produção', 'Área de Qualidade', 'Área Administrativa']

procs = Procedimento.objects.all()
total = procs.count()

print(f"Atualizando {total} procedimentos...")

for i, proc in enumerate(procs):
    # Distribuir em ciclos
    proc.classificacao = classificacoes_variedade[i % len(classificacoes_variedade)]
    proc.matriz = matrizes_variedade[i % len(matrizes_variedade)]
    proc.sub_area = sub_areas_variedade[i % len(sub_areas_variedade)]
    
    if (i + 1) % 100 == 0:
        print(f"  Processado: {i+1}/{total}")

# Bulk update
Procedimento.objects.bulk_update(procs, ['classificacao', 'matriz', 'sub_area'], batch_size=100)
print(f"✅ Total atualizado: {total}")

# Verificar resultado
print("\n📊 Resumo dos dados:")
print(f"  Classificações: {Procedimento.objects.values_list('classificacao', flat=True).distinct().count()}")
print(f"  Matrizes: {Procedimento.objects.values_list('matriz', flat=True).distinct().count()}")
print(f"  Sub-Áreas: {Procedimento.objects.values_list('sub_area', flat=True).distinct().count()}")
