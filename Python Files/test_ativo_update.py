import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

import django
django.setup()

from procedures.models import RegistroTreinamento

# Pegar um registro
reg = RegistroTreinamento.objects.get(id=1)
print(f"Antes: ID={reg.id}, Ativo={reg.ativo}")

# Desmarcar
reg.ativo = False
reg.save()
print(f"Depois: ID={reg.id}, Ativo={reg.ativo}")

# Verificar no banco
reg.refresh_from_db()
print(f"Após refresh: ID={reg.id}, Ativo={reg.ativo}")

# Voltar para True
reg.ativo = True
reg.save()
print(f"Marcado novamente: ID={reg.id}, Ativo={reg.ativo}")
