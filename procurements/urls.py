from django.urls import path
from .views import nova_solicitacao

app_name = 'procurements'

urlpatterns = [
    # Procurements URLs
    path("", nova_solicitacao, name="nova_solicitacao"),
]
