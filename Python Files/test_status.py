#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from procedures.models import ListaPresenca

lista = ListaPresenca.objects.filter(titulo__contains='DOC.084').first()
if lista:
    r = lista.registros.first()
    if r:
        print(f"Status string: {repr(r.status_treinamento)}")
        print(f"Status == 'OK': {r.status_treinamento == 'OK'}")
        print(f"Status == \"OK\": {r.status_treinamento == 'OK'}")
        print(f"Lista_presenca_id: {r.lista_presenca_id}")
        print(f"Data: {r.data_treinamento}")
        print(f"Procedimento: {r.procedimento}")
        if r.procedimento:
            print(f"Ultima revisao: {r.procedimento.ultima_revisao}")
            print(f"Data >= Ultima revisao: {r.data_treinamento >= r.procedimento.ultima_revisao}")
