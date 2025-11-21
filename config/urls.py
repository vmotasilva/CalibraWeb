from django.contrib import admin
from django.urls import path
from django.conf import settings 
from django.conf.urls.static import static
from qms.views import (
    carimbar_view, 
    importar_instrumentos_view, 
    importar_colaboradores_view, # Nova
    dashboard_view, 
    detalhe_instrumento_view,
    download_template_instrumentos, # Nova
    download_template_colaboradores # Nova
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', dashboard_view, name='home'),
    
    # Carimbo
    path('carimbar/', carimbar_view, name='carimbar'),
    
    # Instrumentos
    path('importar-instrumentos/', importar_instrumentos_view, name='importar_instrumentos'),
    path('template-instrumentos/', download_template_instrumentos, name='template_instrumentos'),
    path('instrumento/<int:instrumento_id>/', detalhe_instrumento_view, name='detalhe_instrumento'),

    # Colaboradores
    path('importar-colaboradores/', importar_colaboradores_view, name='importar_colaboradores'),
    path('template-colaboradores/', download_template_colaboradores, name='template_colaboradores'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)