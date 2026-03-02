#!/usr/bin/env python
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from rh.models import Colaborador

# Buscar por nome
colab = Colaborador.objects.filter(nome_completo__icontains="AFONSO PAULO").first()
if colab:
    print(f"Encontrado: {colab.nome_completo} (ID: {colab.id})")
else:
    print("Não encontrado")
    # Listar alguns
    for c in Colaborador.objects.all()[:5]:
        print(f"  - {c.nome_completo} (ID: {c.id})")
