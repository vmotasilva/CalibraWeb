#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from procedures.models import RegistroTreinamento

registros = RegistroTreinamento.objects.all()[:5]

for r in registros:
    print(f"\n--- Registro ID: {r.id} ---")
    print(f"Colaborador: {r.colaborador.nome_completo if r.colaborador else 'N/A'}")
    print(f"Procedimento: {r.procedimento}")
    print(f"Status: {r.status_treinamento}")
    print(f"Lista presença: {r.lista_presenca_id}")
    print(f"Data treinamento: {r.data_treinamento}")
    print(f"Revisão treinada: {r.revisao_treinada}")
    if r.procedimento:
        print(f"Número revisão proc: {r.procedimento.numero_revisao}")
        print(f"Última revisão: {r.procedimento.ultima_revisao}")
