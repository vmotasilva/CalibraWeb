from django.urls import path
from . import views

app_name = "fornecedores"

urlpatterns = [
    path("", views.fornecedor_list, name="fornecedor_list"),
    path("novo/", views.fornecedor_create, name="fornecedor_create"),
    path("<int:pk>/editar/", views.fornecedor_update, name="fornecedor_update"),
    path("<int:pk>/", views.fornecedor_detail, name="fornecedor_detail"),
    path("<int:fornecedor_id>/documentos/novo/", views.documento_create, name="documento_create"),
    path("<int:fornecedor_id>/documentos/<int:doc_id>/remover/", views.documento_delete, name="documento_delete"),
    path("<int:fornecedor_id>/avaliacoes/selecao/", views.avaliacao_selecao_create, name="avaliacao_selecao_create"),
    path("<int:fornecedor_id>/avaliacoes/reavaliacao/", views.avaliacao_reavaliacao_create, name="avaliacao_reavaliacao_create"),
    path("<int:fornecedor_id>/avaliacoes/matriz/", views.avaliacao_matriz_create, name="avaliacao_matriz_create"),
    path("<int:fornecedor_id>/avaliacoes/", views.avaliacao_list, name="avaliacao_list"),
    path("<int:fornecedor_id>/avaliacoes/nova/", views.avaliacao_create, name="avaliacao_create"),
    path("<int:fornecedor_id>/avaliacoes/<int:avaliacao_id>/editar/", views.avaliacao_edit, name="avaliacao_edit"),
    path("<int:fornecedor_id>/reavaliacoes/", views.reavaliacao_list, name="reavaliacao_list"),
    path("<int:fornecedor_id>/reavaliacoes/nova/", views.reavaliacao_create, name="reavaliacao_create"),
    path("<int:fornecedor_id>/exportar-avaliacoes/", views.export_avaliacoes_excel, name="export_avaliacoes_excel"),

    # Perguntas de Avaliação
    path("perguntas/", views.pergunta_list, name="pergunta_list"),
    path("perguntas/nova/", views.pergunta_create, name="pergunta_create"),
    path("perguntas/<int:pk>/editar/", views.pergunta_edit, name="pergunta_edit"),
    path("perguntas/<int:pk>/remover/", views.pergunta_delete, name="pergunta_delete"),
    path("perguntas-filtradas/", views.perguntas_filtradas, name="perguntas_filtradas"),
    path("api/respostas-avaliacao/<int:avaliacao_id>/", views.api_respostas_avaliacao, name="api_respostas_avaliacao"),
]
