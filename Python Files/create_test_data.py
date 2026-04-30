#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from rh.models import Colaborador, Setor, Ferias
from datetime import date, timedelta

# Criar setor RH
setor, _ = Setor.objects.get_or_create(nome='RH', defaults={'descricao': 'Recursos Humanos'})

# Criar usuário
user, _ = User.objects.get_or_create(
    username='admin',
    defaults={'is_staff': True, 'is_superuser': True, 'first_name': 'Admin'}
)

# Criar colaborador RH
colab_rh, _ = Colaborador.objects.get_or_create(
    nome_completo='Admin RH',
    matricula='000001',
    defaults={'setor': setor, 'cpf': '00000000001', 'email': 'admin@test.com'}
)

# Associar user ao colaborador
colab_rh.usuario = user
colab_rh.save()

# Criar alguns colaboradores de teste
for i in range(3):
    colab, _ = Colaborador.objects.get_or_create(
        nome_completo=f'Colaborador {i+1}',
        matricula=f'000{i+2:03d}',
        defaults={'setor': setor, 'cpf': f'0000000000{i+2}', 'email': f'colab{i+1}@test.com'}
    )
    
    # Criar férias para cada colaborador
    Ferias.objects.get_or_create(
        colaborador=colab,
        data_inicio=date.today() + timedelta(days=10),
        data_fim=date.today() + timedelta(days=20),
        defaults={'aprovada': True, 'status': 'PLANEJADO'}
    )

print('✅ Dados de teste criados com sucesso!')
print(f'  - Colaboradores: {Colaborador.objects.count()}')
print(f'  - Férias: {Ferias.objects.count()}')
print(f'  - Usuários: {User.objects.count()}')
