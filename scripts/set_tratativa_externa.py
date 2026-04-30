
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from metrologia.models import Instrumento

# Atualiza todos os instrumentos para tratativa EXTERNA
Instrumento.objects.all().update(tratativa_calibracao='EXTERNA')
print('Todos os instrumentos foram atualizados para calibração EXTERNA.')
