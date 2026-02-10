from django.urls import path
from .views import listar_acoes, detalhe_acao

app_name = 'acoes'

urlpatterns = [
    path('', listar_acoes, name='listar_acoes'),
    path('acao/<int:acao_id>/', detalhe_acao, name='detalhe_acao'),
]
