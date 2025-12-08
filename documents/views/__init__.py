"""
Documents Module Views
Views relacionadas a gestão de documentos e certificados
"""

import logging
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

logger = logging.getLogger(__name__)

# Views serão migradas da qms/views.py durante a Fase 3
# Plano de migração:
# - preview_certificado_view - Preview do certificado
# - download_certificado_view - Download de certificado
# - aplicar_carimbo_certificado_view - Aplicar carimbo


@login_required
def documents_dashboard(request):
    """
    Dashboard do módulo de documentos
    Placeholder - será preenchido na Fase 3
    """
    context = {
        'module_name': 'Documents',
        'module_description': 'Gestão de Documentos'
    }
    return render(request, 'documents/dashboard.html', context)
