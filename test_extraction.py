import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from procedures.models import TemplateListaPresenca
from procedures.views.lista_presenca_views import extract_placeholders_from_pdf

try:
    template = TemplateListaPresenca.objects.get(id=5)
    if template.arquivo_pdf_template:
        pdf_path = template.arquivo_pdf_template.path
        print(f"PDF path: {pdf_path}")
        print(f"PDF exists: {os.path.exists(pdf_path)}")
        placeholders = extract_placeholders_from_pdf(pdf_path)
        print(f'Placeholders encontrados: {placeholders}')
        print(f'Total: {len(placeholders)} placeholders')
    else:
        print('Nenhum PDF carregado')
except Exception as e:
    print(f"Erro: {e}")
    import traceback
    traceback.print_exc()
