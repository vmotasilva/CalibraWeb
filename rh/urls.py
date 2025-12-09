from django.urls import path
from . import views

app_name = 'rh'

urlpatterns = [
    # RH module URLs
    path("", views.modulo_rh_view, name="modulo_rh"),
    path("colaborador/<int:colab_id>/", views.detalhe_colaborador_view, name="detalhe_colaborador"),
    path("colaborador/<int:colab_id>/editar/", views.editar_colaborador_view, name="editar_colaborador"),
    path("ocorrencia/", views.registrar_ocorrencia_view, name="registrar_ocorrencia"),
]
