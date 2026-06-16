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
    path('cartoes/<int:card_id>/checklist/novo/', views.api_add_checklist_item_view, name='api_add_checklist_item'),
    path('checklist/<int:item_id>/toggle/', views.api_toggle_checklist_item_view, name='api_toggle_checklist_item'),
    path('checklist/<int:item_id>/excluir/', views.api_delete_checklist_item_view, name='api_delete_checklist_item'),
    path('cartoes/<int:card_id>/comentarios/novo/', views.api_add_comment_view, name='api_add_comment'),
    path('comentarios/<int:comment_id>/excluir/', views.api_delete_comment_view, name='api_delete_comment'),
]
