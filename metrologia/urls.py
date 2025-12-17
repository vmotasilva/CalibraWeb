from django.urls import path
from . import views
from .views import categorias

app_name = 'metrologia'

urlpatterns = [
    # Metrologia URLs
    # path('', views.modulo_metrologia_view, name='dashboard'),

    # ==============================================================================
    # GERENCIAMENTO DE CATEGORIAS
    # ==============================================================================
    path('categorias/', categorias.categorias_list_view, name='categorias_list'),
    path('categorias/nova/', categorias.categoria_create_view, name='categoria_create'),
    path('categorias/<int:categoria_id>/', categorias.categoria_detail_view, name='categoria_detail'),
    path('categorias/<int:categoria_id>/editar/', categorias.categoria_update_view, name='categoria_update'),
    path('categorias/<int:categoria_id>/deletar/', categorias.categoria_delete_view, name='categoria_delete'),
    path('api/categorias/', categorias.categorias_api_view, name='categorias_api'),
    
    # Faixas padrão de categorias
    path('categorias/<int:categoria_id>/faixa/nova/', categorias.faixa_categoria_create_view, name='faixa_categoria_create'),
    path('categorias/<int:categoria_id>/faixa/adicionar-instrumento/', categorias.faixa_categoria_add_to_instrument_view, name='faixa_categoria_add_to_instrument'),
    path('categorias/<int:categoria_id>/faixa-instrumento/<int:faixa_id>/remover/', categorias.faixa_instrumento_delete_view, name='faixa_instrumento_delete'),
    path('categorias/<int:categoria_id>/faixa-instrumento/<int:faixa_id>/substituir/', categorias.faixa_instrumento_replace_view, name='faixa_instrumento_replace'),
    path('categorias/<int:categoria_id>/faixa-instrumento/remover-em-massa/', categorias.faixa_instrumento_bulk_delete_view, name='faixa_instrumento_bulk_delete'),
    path('categorias/<int:categoria_id>/faixa-instrumento/substituir-em-massa/', categorias.faixa_instrumento_bulk_replace_view, name='faixa_instrumento_bulk_replace'),
    path('categorias/<int:categoria_id>/instrumento/alterar-categoria-em-massa/', categorias.instrumento_bulk_change_category_view, name='instrumento_bulk_change_category'),
    path('faixa/<int:faixa_id>/editar/', categorias.faixa_categoria_update_view, name='faixa_categoria_update'),
    path('faixa/<int:faixa_id>/deletar/', categorias.faixa_categoria_delete_view, name='faixa_categoria_delete'),
    path('api/categorias/<int:categoria_id>/faixas/', categorias.faixas_categoria_api_view, name='faixas_categoria_api'),

    # ==============================================================================
    # NOVO FLUXO DE COTAÇÕES - ETAPAS 1-4
    # ==============================================================================
    
    # ETAPA 1: SOLICITAÇÃO DE COTAÇÃO
    path('solicitacoes/', views.solicitacao_list, name='solicitacao_list'),
    path('solicitacoes/nova/', views.solicitacao_create, name='solicitacao_create'),
    path('solicitacoes/<int:pk>/', views.solicitacao_detail, name='solicitacao_detail'),
    path('solicitacoes/<int:pk>/editar/', views.solicitacao_update, name='solicitacao_update'),
    path('solicitacoes/<int:pk>/deletar/', views.solicitacao_delete, name='solicitacao_delete'),
    path('itens-solicitacao/<int:pk>/editar/', views.item_solicitacao_edit, name='item_solicitacao_edit'),
    path('itens-solicitacao/<int:pk>/deletar/', views.item_solicitacao_delete, name='item_solicitacao_delete'),
    path('solicitacoes/<int:pk>/concluir/', views.solicitacao_marcar_concluida, name='solicitacao_concluir'),
    path('solicitacoes/<int:pk>/cancelar/', views.solicitacao_marcar_cancelada, name='solicitacao_cancelar'),
    path('solicitacoes/<int:pk>/reativar/', views.solicitacao_reativar, name='solicitacao_reativar'),
    path('solicitacoes/<int:pk>/reabrir/', views.solicitacao_reabrir, name='solicitacao_reabrir'),

    # ETAPA 2: COTAÇÕES DE FORNECEDORES
    path('solicitacoes/<int:solicitacao_pk>/cotacao-fornecedor/nova/', views.cotacao_fornecedor_create, name='cotacao_fornecedor_create'),
    path('cotacao-fornecedor/<int:pk>/', views.cotacao_fornecedor_detail, name='cotacao_fornecedor_detail'),
    path('cotacao-fornecedor/<int:pk>/editar/', views.cotacao_fornecedor_update, name='cotacao_fornecedor_update'),

    # ETAPA 3: ATENDIMENTOS
    path('solicitacoes/<int:solicitacao_pk>/itens/<int:item_pk>/atendimento/novo/', views.atendimento_create, name='atendimento_create'),
    path('cotacao-fornecedor/<int:cotacao_id>/atendimento/criar/', views.atendimento_create_from_cotacao, name='atendimento_create_from_cotacao'),
    path('atendimentos/<int:pk>/', views.atendimento_detail, name='atendimento_detail'),
    path('atendimentos/<int:pk>/confirmar/', views.atendimento_confirmar, name='atendimento_confirmar'),
    path('api/atendimento/atualizar-dados/', views.atendimento_atualizar_dados, name='atendimento_atualizar_dados'),
    path('api/atendimento/atualizar-cotacao/', views.atendimento_atualizar_cotacao, name='atendimento_atualizar_cotacao'),
    
    # NEW: Atualizar dados de atendimento (Calibração, Rastreio, Substituição)
    path('atendimento/<int:pk>/atualizar-data/', views.atendimento_atualizar_data_calibracao, name='atendimento_atualizar_data_calibracao'),
    path('atendimento/<int:pk>/atualizar-chegada/', views.atendimento_atualizar_chegada, name='atendimento_atualizar_chegada'),
    path('atendimento/<int:pk>/atualizar-rastreio/', views.atendimento_atualizar_rastreio, name='atendimento_atualizar_rastreio'),
    path('atendimento/<int:atendimento_id>/registrar-historico/', views.atendimento_registrar_historico, name='atendimento_registrar_historico'),
    path('atendimento/<int:atendimento_id>/iniciar-substituicao/', views.atendimento_iniciar_substituicao, name='atendimento_iniciar_substituicao'),

    # API ENDPOINTS
    path('api/instrumentos-vencendo/', views.api_instrumentos_vencendo, name='api_instrumentos_vencendo'),
]