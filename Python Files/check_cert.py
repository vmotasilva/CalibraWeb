import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from metrologia.models import HistoricoCalibracao

h = HistoricoCalibracao.objects.get(id=127)
print(f'Certificado: {h.certificado}')
print(f'Existe: {bool(h.certificado)}')
if h.certificado:
    print(f'URL: {h.certificado.url}')
    print(f'Path: {h.certificado.path}')
    print(f'File exists: {os.path.exists(h.certificado.path)}')
