from django.urls import path

from . import views

app_name = "laboratorio"

urlpatterns = [
    path("", views.modulo_laboratorio_view, name="modulo"),
    path("ocorrencias/", views.ocorrencias_list, name="ocorrencias_list"),
    path("ocorrencias/nova/", views.ocorrencia_create, name="ocorrencia_create"),
    path("ocorrencias/<int:pk>/", views.ocorrencia_detail, name="ocorrencia_detail"),
    path("ocorrencias/<int:pk>/anotacoes/", views.ocorrencia_notes, name="ocorrencia_notes"),
    path("ocorrencias/<int:pk>/editar/", views.ocorrencia_update, name="ocorrencia_update"),
    path("ocorrencias/<int:pk>/encerrar/", views.ocorrencia_close, name="ocorrencia_close"),
    path("ocorrencias/<int:pk>/excluir/", views.ocorrencia_delete, name="ocorrencia_delete"),
    path("categorias/", views.categorias_list, name="categorias_list"),
    path("categorias/nova/", views.categoria_create, name="categoria_create"),
    path("categorias/<int:pk>/editar/", views.categoria_update, name="categoria_update"),
    path("dashboard/", views.dashboard_laboratorio, name="dashboard"),
]
