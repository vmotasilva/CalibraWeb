from django.urls import path
from . import views

app_name = 'metrologia'

urlpatterns = [
    # Metrologia URLs
    # path('', views.modulo_metrologia_view, name='dashboard'),

    # ==============================================================================
    # NOVO FLUXO DE COTAÇÕES - ETAPAS 1-4
    # ==============================================================================
    
    # ETAPA 1: SOLICITAÇÃO DE COTAÇÃO
    path('solicitacoes/', views.solicitacao_list, name='solicitacao_list'),
    path('solicitacoes/nova/', views.solicitacao_create, name='solicitacao_create'),
    path('solicitacoes/<int:pk>/', views.solicitacao_detail, name='solicitacao_detail'),
    path('solicitacoes/<int:pk>/editar/', views.solicitacao_update, name='solicitacao_update'),
    path('solicitacoes/<int:pk>/deletar/', views.solicitacao_delete, name='solicitacao_delete'),
    path('solicitacoes/<int:pk>/itens/', views.solicitacao_itens, name='solicitacao_itens'),
    path('itens-solicitacao/<int:pk>/editar/', views.item_solicitacao_edit, name='item_solicitacao_edit'),
    path('itens-solicitacao/<int:pk>/deletar/', views.item_solicitacao_delete, name='item_solicitacao_delete'),

    # ETAPA 2: COTAÇÕES DE FORNECEDORES
    path('solicitacoes/<int:solicitacao_pk>/cotacao-fornecedor/nova/', views.cotacao_fornecedor_create, name='cotacao_fornecedor_create'),
    path('cotacao-fornecedor/<int:pk>/', views.cotacao_fornecedor_detail, name='cotacao_fornecedor_detail'),
    path('cotacao-fornecedor/<int:pk>/itens/', views.cotacao_fornecedor_itens, name='cotacao_fornecedor_itens'),
    path('itens-cotacao/<int:pk>/deletar/', views.item_cotacao_delete, name='item_cotacao_delete'),

    # ETAPA 3: ATENDIMENTOS
    path('solicitacoes/<int:solicitacao_pk>/itens/<int:item_pk>/atendimento/novo/', views.atendimento_create, name='atendimento_create'),
    path('atendimentos/<int:pk>/', views.atendimento_detail, name='atendimento_detail'),
    path('atendimentos/<int:pk>/confirmar/', views.atendimento_confirmar, name='atendimento_confirmar'),

    # API ENDPOINTS
    path('api/instrumentos-vencendo/', views.api_instrumentos_vencendo, name='api_instrumentos_vencendo'),
]