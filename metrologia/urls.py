from django.urls import path
from . import views
from metrologia.views import cotacao

app_name = 'metrologia'

urlpatterns = [
    # Metrologia URLs
    # path('', views.modulo_metrologia_view, name='dashboard'),
    
    # Cotação URLs
    path('cotacoes/', cotacao.cotacao_list, name='cotacao_list'),
    path('cotacoes/nova/', cotacao.cotacao_create, name='cotacao_create'),
    path('cotacoes/<int:pk>/', cotacao.cotacao_detail, name='cotacao_detail'),
    path('cotacoes/<int:pk>/enviar/', cotacao.cotacao_enviar, name='cotacao_enviar'),
    path('cotacoes/<int:pk>/receber-proposta/', cotacao.cotacao_receber_proposta, name='cotacao_receber_proposta'),
    path('cotacoes/<int:pk>/aprovar/', cotacao.cotacao_aprovar, name='cotacao_aprovar'),
    path('cotacoes/<int:pk>/reprovar/', cotacao.cotacao_reprovar, name='cotacao_reprovar'),
    path('cotacoes/<int:pk>/cancelar/', cotacao.cotacao_cancelar, name='cotacao_cancelar'),
    
    # Ocorrência URLs
    path('cotacoes/<int:cotacao_id>/ocorrencia/nova/', cotacao.ocorrencia_create, name='ocorrencia_create'),
    path('ocorrencias/<int:ocorrencia_id>/editar/', cotacao.ocorrencia_edit, name='ocorrencia_edit'),
    path('ocorrencias/<int:ocorrencia_id>/resolver/', cotacao.ocorrencia_resolver, name='ocorrencia_resolver'),
    path('ocorrencias/<int:ocorrencia_id>/deletar/', cotacao.ocorrencia_delete, name='ocorrencia_delete'),
]
