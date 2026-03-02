import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from metrologia.models import HistoricoCalibracao
from django.template.loader import render_to_string

h = HistoricoCalibracao.objects.get(id=127)

# Simular contexto do template
context = {
    'historico': h,
    'instrumento': h.instrumento,
}

# Renderizar apenas a parte do template que precisa
template_str = """{% if historico.certificado_carimbado or historico.certificado %}
    PDF URL: {% if historico.certificado_carimbado %}{{ historico.certificado_carimbado.url }}{% else %}{{ historico.certificado.url }}{% endif %}
{% else %}
    SEM PDF
{% endif %}"""

from django.template import Template, Context
t = Template(template_str)
result = t.render(Context(context))
print("Template result:")
print(result)
print(f"\nCertificado carimbado: {h.certificado_carimbado}")
print(f"Certificado: {h.certificado}")
print(f"Certificado URL: {h.certificado.url if h.certificado else 'NONE'}")
