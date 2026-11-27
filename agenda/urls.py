from django.urls import path

from agenda import views

app_name = "agenda"

urlpatterns = [
    path("", views.calendario_view, name="calendario"),
    path("checklist/", views.checklist_view, name="checklist"),
    path("api/eventos/", views.api_eventos, name="api_eventos"),
    path("api/eventos/salvar/", views.evento_salvar, name="evento_salvar"),
    path("api/eventos/<int:evento_id>/", views.api_evento_detalhe, name="api_evento_detalhe"),
    path("api/eventos/<int:evento_id>/excluir/", views.evento_excluir, name="evento_excluir"),
    path("api/eventos/<int:evento_id>/convite/", views.api_responder_convite, name="api_responder_convite"),
    path("equipe/", views.equipe_view, name="equipe"),
    path("compartilhados/", views.compartilhados_view, name="compartilhados"),
    path("compartilhados/<int:lista_id>/", views.compartilhado_detalhe_view, name="compartilhado_detalhe"),
    path("api/compartilhados/salvar/", views.compartilhado_salvar, name="compartilhado_salvar"),
    path("api/compartilhados/<int:lista_id>/", views.api_compartilhado_detalhe, name="api_compartilhado_detalhe"),
    path("api/compartilhados/<int:lista_id>/excluir/", views.compartilhado_excluir, name="compartilhado_excluir"),
    path("api/compartilhados/tarefas/<int:tarefa_id>/toggle/", views.api_tarefa_toggle, name="api_tarefa_toggle"),
    path("api/compartilhados/tarefas/<int:tarefa_id>/cobrar/", views.api_tarefa_cobrar, name="api_tarefa_cobrar"),
    path("checklists/", views.checklists_view, name="checklists"),
    path("api/notas/", views.api_notas, name="api_notas"),
    path("api/notas/comentario/", views.comentario_salvar, name="comentario_salvar"),
    path("api/notas/comentario/<int:comentario_id>/excluir/", views.comentario_excluir, name="comentario_excluir"),
    path("api/notas/ocorrencia/", views.ocorrencia_criar, name="ocorrencia_criar"),
    path("api/itens-avulsos/criar/", views.item_avulso_criar, name="item_avulso_criar"),
    path("api/itens-avulsos/<int:item_id>/excluir/", views.item_avulso_excluir, name="item_avulso_excluir"),
    path("api/checklists/salvar/", views.checklist_salvar, name="checklist_salvar"),
    path("api/checklists/<int:checklist_id>/", views.api_checklist_detalhe, name="api_checklist_detalhe"),
    path("api/checklists/<int:checklist_id>/excluir/", views.checklist_excluir, name="checklist_excluir"),
    path("api/checklists/<int:checklist_id>/item/<int:item_id>/diario/", views.api_diario_toggle, name="api_diario_toggle"),
    path("api/checklist/<int:evento_id>/item/<int:item_id>/toggle/", views.api_item_toggle, name="api_item_toggle"),
    path("api/checklist/<int:evento_id>/toggle/", views.api_checklist_toggle, name="api_checklist_toggle"),
]
