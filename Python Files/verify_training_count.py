#!/usr/bin/env python
"""
Script para verificar e validar a contagem de treinamentos
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(__file__))

django.setup()

from rh.models import Colaborador
from procedures.models import RegistroTreinamento

# Pegar um colaborador com treinamentos
colaboradores = Colaborador.objects.filter(treinamentos__isnull=False).distinct()

print(f"\n{'='*80}")
print(f"VERIFICAÇÃO DE CONTAGEM DE TREINAMENTOS")
print(f"{'='*80}\n")

for colab in colaboradores[:5]:  # Apenas os primeiros 5
    vig = 0
    pend = 0
    nao_iniciado = 0
    
    treinamentos = colab.treinamentos.all()
    
    for rt in treinamentos:
        status = rt.status_treinamento
        if status == "OK":
            vig += 1
        elif status == "PENDENTE":
            pend += 1
        else:
            nao_iniciado += 1
    
    print(f"\n{colab.nome_completo} (ID: {colab.id})")
    print(f"  Total: {treinamentos.count()}")
    print(f"  Vigentes (OK):     {vig}")
    print(f"  Pendentes:         {pend}")
    print(f"  Não Iniciados:     {nao_iniciado}")
    print(f"  " + "-"*70)

print(f"\n{'='*80}\n")
