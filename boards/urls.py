from django.urls import path
from boards import views

app_name = 'boards'

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('<int:board_id>/', views.board_detail_view, name='board_detail'),
    path('<int:board_id>/editar/', views.edit_board_view, name='edit_board'),
    path('<int:board_id>/excluir/', views.delete_board_view, name='delete_board'),
    path('<int:board_id>/colunas/nova/', views.create_column_view, name='create_column'),
    path('colunas/<int:column_id>/excluir/', views.delete_column_view, name='delete_column'),
    path('colunas/<int:column_id>/cartoes/novo/', views.create_card_view, name='create_card'),
    path('cartoes/mover/', views.api_move_card_view, name='api_move_card'),
    path('cartoes/<int:card_id>/detalhes/', views.api_card_detail_view, name='api_card_detail'),
    path('cartoes/<int:card_id>/excluir/', views.delete_card_view, name='delete_card'),
    path('linhas-acao/<int:linha_id>/detalhes/', views.api_linha_acao_detail_view, name='api_linha_acao_detail'),
    path('cartoes/<int:card_id>/checklist/novo/', views.api_add_checklist_item_view, name='api_add_checklist_item'),
    path('checklist/<int:item_id>/toggle/', views.api_toggle_checklist_item_view, name='api_toggle_checklist_item'),
    path('checklist/<int:item_id>/excluir/', views.api_delete_checklist_item_view, name='api_delete_checklist_item'),
    path('cartoes/<int:card_id>/comentarios/novo/', views.api_add_comment_view, name='api_add_comment'),
    path('comentarios/<int:comment_id>/excluir/', views.api_delete_comment_view, name='api_delete_comment'),
    path('<int:board_id>/arquivar/', views.archive_board_view, name='archive_board'),
    path('<int:board_id>/desarquivar/', views.unarchive_board_view, name='unarchive_board'),
    path('colunas/mover/', views.api_move_column_view, name='api_move_column'),
    path('colunas/<int:column_id>/subsecoes/nova/', views.create_subsection_view, name='create_subsection'),
    path('subsecoes/<int:subsection_id>/excluir/', views.delete_subsection_view, name='delete_subsection'),
    path('<int:board_id>/etiquetas/nova/', views.create_label_view, name='create_label'),
    path('etiquetas/<int:label_id>/excluir/', views.delete_label_view, name='delete_label'),
    path('mencoes/<int:mention_id>/visualizar/', views.read_mention_view, name='read_mention'),
    path('notificacoes/<int:notif_id>/visualizar/', views.read_board_notification_view, name='read_board_notification'),
    path('colunas/<int:column_id>/copiar/', views.copy_column_view, name='copy_column'),
    path('colunas/<int:column_id>/descricao/', views.api_column_description_view, name='api_column_description'),
    path('colunas/<int:column_id>/renomear/', views.api_rename_column_view, name='api_rename_column'),
    path('colunas/<int:column_id>/arquivar/', views.archive_column_view, name='archive_column'),
    path('colunas/<int:column_id>/desarquivar/', views.unarchive_column_view, name='unarchive_column'),
    path('<int:board_id>/colunas/<int:focus_column_id>/foco/', views.board_detail_view, name='column_focus'),
    path('<int:board_id>/links/novo/', views.api_add_board_link_view, name='api_add_board_link'),
    path('links/<int:link_id>/excluir/', views.api_delete_board_link_view, name='api_delete_board_link'),
]

