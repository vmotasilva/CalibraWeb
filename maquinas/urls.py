from django.urls import path

from . import views

app_name = "maquinas"

urlpatterns = [
    path("", views.maquinas_list, name="maquinas_list"),
    path("nova/", views.maquina_create, name="maquina_create"),
    path("<int:pk>/editar/", views.maquina_update, name="maquina_update"),
    path("<int:pk>/excluir/", views.maquina_delete, name="maquina_delete"),
    path("categorias/", views.categorias_list, name="categorias_list"),
    path("categorias/nova/", views.categoria_create, name="categoria_create"),
    path("categorias/<int:pk>/editar/", views.categoria_update, name="categoria_update"),
    path("categorias/<int:pk>/excluir/", views.categoria_delete, name="categoria_delete"),
]