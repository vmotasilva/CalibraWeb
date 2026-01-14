import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

import django
django.setup()

from procedures.models import RegistroTreinamento

# Buscar um registro de treinamento
registros = RegistroTreinamento.objects.all()[:5]

print(f"Total de registros de treinamento: {RegistroTreinamento.objects.count()}\n")

for reg in registros:
    print(f"ID: {reg.id}")
    print(f"Colaborador: {reg.colaborador.nome_completo if reg.colaborador else 'N/A'}")
    print(f"Procedimento: {reg.procedimento.codigo if reg.procedimento else 'N/A'}")
    print(f"Ativo: {reg.ativo}")
    print(f"Tipo: {type(reg.ativo)}")
    print("---")
