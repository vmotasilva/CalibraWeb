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
    path("api/checklist/<int:evento_id>/toggle/", views.api_checklist_toggle, name="api_checklist_toggle"),
]
