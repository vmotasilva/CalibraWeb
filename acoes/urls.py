from django.urls import path
from .views import listar_acoes, detalhe_acao
from .views_solucoes import (
    listar_solucoes,
    detalhe_solucao,
    criar_solucao,
    editar_solucao,
)

app_name = 'acoes'

urlpatterns = [
    # Ações Corretivas/Preventivas
    path('', listar_acoes, name='listar_acoes'),
    path('acao/<int:acao_id>/', detalhe_acao, name='detalhe_acao'),
    
    # Soluções
    path('solucoes/', listar_solucoes, name='listar_solucoes'),
    path('solucao/<int:solucao_id>/', detalhe_solucao, name='detalhe_solucao'),
    path('acao/<int:acao_id>/solucao/criar/', criar_solucao, name='criar_solucao'),
    path('solucao/<int:solucao_id>/editar/', editar_solucao, name='editar_solucao'),
]
