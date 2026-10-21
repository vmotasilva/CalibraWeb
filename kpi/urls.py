from django.urls import path

from kpi import views

app_name = 'kpi'

urlpatterns = [
    path('', views.painel_view, name='painel'),
    path('importar/', views.importar_view, name='importar'),
    path('importar/modelo/<str:tipo>/<str:gran>/', views.modelo_importacao_view, name='modelo_importacao'),
    path('colar/', views.colagem_view, name='colagem'),
    path('colar/modelos/', views.colagem_modelos_view, name='colagem_modelos'),
    path('colar/modelos/novo/', views.colagem_modelo_form_view, name='colagem_modelo_novo'),
    path('colar/modelos/<int:pk>/', views.colagem_modelo_form_view, name='colagem_modelo_editar'),
    path('colar/modelos/<int:pk>/excluir/', views.colagem_modelo_excluir_view, name='colagem_modelo_excluir'),
    path('indicadores/', views.indicadores_view, name='indicadores'),
    path('indicadores/novo/', views.indicador_form_view, name='indicador_novo'),
    path('indicadores/<int:pk>/', views.indicador_detalhe_view, name='indicador_detalhe'),
    path('indicadores/<int:pk>/mover/', views.indicador_mover_view, name='indicador_mover'),
    path('indicadores/<int:pk>/editar/', views.indicador_form_view, name='indicador_editar'),
    path('indicadores/<int:pk>/excluir/', views.indicador_excluir_view, name='indicador_excluir'),
    path('indicadores/<int:pk>/medicao/', views.medicao_salvar_view, name='medicao_salvar'),
    path('medicoes/<int:pk>/excluir/', views.medicao_excluir_view, name='medicao_excluir'),
    path('indicadores/<int:pk>/motivo/', views.motivo_salvar_view, name='motivo_salvar'),
    path('indicadores/<int:pk>/analise/', views.analise_dados_view, name='analise_dados'),
    path('indicadores/<int:pk>/analise/salvar/', views.analise_salvar_view, name='analise_salvar'),
]
