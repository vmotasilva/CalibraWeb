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
    path("checklists/", views.checklists_view, name="checklists"),
    path("api/checklists/salvar/", views.checklist_salvar, name="checklist_salvar"),
    path("api/checklists/<int:checklist_id>/", views.api_checklist_detalhe, name="api_checklist_detalhe"),
    path("api/checklists/<int:checklist_id>/excluir/", views.checklist_excluir, name="checklist_excluir"),
    path("api/checklists/<int:checklist_id>/item/<int:item_id>/diario/", views.api_diario_toggle, name="api_diario_toggle"),
    path("api/checklist/<int:evento_id>/item/<int:item_id>/toggle/", views.api_item_toggle, name="api_item_toggle"),
    path("api/checklist/<int:evento_id>/toggle/", views.api_checklist_toggle, name="api_checklist_toggle"),
]
