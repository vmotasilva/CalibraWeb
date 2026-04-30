from django.urls import path

from . import views

app_name = "auditoria"

urlpatterns = [
    path("", views.modulo_auditoria_view, name="modulo"),
    path("modelos/", views.modelos_list, name="modelos_list"),
    path("modelos/novo/", views.modelo_create, name="modelo_create"),
    path("modelos/<int:pk>/editar/", views.modelo_edit, name="modelo_edit"),
    path("modelos/<int:pk>/duplicar/", views.modelo_duplicate, name="modelo_duplicate"),
    path("modelos/<int:pk>/remover/", views.modelo_delete, name="modelo_delete"),
    path("perguntas/", views.perguntas_list, name="perguntas_list"),
    path("perguntas/next-ordem/", views.api_next_pergunta_ordem, name="api_next_pergunta_ordem"),
    path("modelos/subcategorias/", views.api_modelo_subcategorias, name="api_modelo_subcategorias"),
    path("perguntas/bulk-subcategoria/", views.perguntas_bulk_set_subcategoria, name="perguntas_bulk_set_subcategoria"),
    path("perguntas/nova/", views.pergunta_create, name="pergunta_create"),
    path("perguntas/<int:pk>/editar/", views.pergunta_edit, name="pergunta_edit"),
    path("perguntas/<int:pk>/duplicar/", views.pergunta_duplicate, name="pergunta_duplicate"),
    path("perguntas/<int:pk>/remover/", views.pergunta_delete, name="pergunta_delete"),
    path("registros/", views.registros_list, name="registros_list"),
    path("registros/selecionar-modelo/", views.selecionar_modelo_preenchimento, name="selecionar_modelo_preenchimento"),
    path("registros/novo/", views.registro_create, name="registro_create"),
    path("registros/novo/<int:modelo_id>/", views.registro_create, name="registro_create_modelo"),
    path("registros/<int:pk>/editar/", views.registro_edit, name="registro_edit"),
    path("registros/<int:pk>/remover/", views.registro_delete, name="registro_delete"),
    path("registros/<int:pk>/exportar-pdf/", views.registro_exportar_pdf, name="registro_exportar_pdf"),
    path("registros/<int:pk>/", views.registro_detail, name="registro_detail"),
    path("modelos/<int:modelo_id>/registros/", views.registros_por_modelo, name="registros_por_modelo"),
    path("modelos/<int:modelo_id>/registros/compartilhado/", views.registros_por_modelo, name="registros_por_modelo_compartilhado"),
    path(
        "modelos/<int:modelo_id>/comentarios/<int:pk>/editar/",
        views.comentario_edit,
        name="comentario_edit",
    ),
    path(
        "modelos/<int:modelo_id>/comentarios/<int:pk>/remover/",
        views.comentario_delete,
        name="comentario_delete",
    ),
    path(
        "modelos/<int:modelo_id>/registros/exportar-excel/",
        views.exportar_respostas_excel,
        name="exportar_respostas_excel",
    ),
    path("dashboard/", views.dashboard_auditoria, name="dashboard"),
]
