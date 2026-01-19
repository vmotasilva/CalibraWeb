from django.urls import path
from rh.views import views

app_name = 'rh'

urlpatterns = [
    # Detalhe do colaborador
    path('colaborador/<int:colab_id>/', views.detalhe_colaborador_view, name='detalhe_colaborador'),
    
    # Dashboard e gestão
    path('gestao-ferias/', views.gestao_ferias_view, name='gestao_ferias'),
    path('gestao-ferias/atualizar-status/', views.atualizar_status_ferias_view, name='atualizar_status_ferias'),
    path('gestao-ferias/importar/', views.importar_ferias_view, name='importar_ferias'),
    path('gestao-ferias/criar/', views.criar_ferias_view, name='criar_ferias'),
    path('gestao-ferias/criar/<int:colab_id>/', views.criar_ferias_view, name='criar_ferias_colab'),
    path('<int:colab_id>/ferias/<int:ferias_id>/editar/', views.editar_ferias_view, name='editar_ferias'),
    path('<int:colab_id>/ferias/<int:ferias_id>/excluir/', views.excluir_ferias_view, name='excluir_ferias'),
    
    # API Endpoints
    path('api/colaboradores/', views.api_colaboradores, name='api_colaboradores'),
    path('api/setores/', views.api_setores, name='api_setores'),
    path('api/cargos/', views.api_cargos, name='api_cargos'),
    path('api/grupos/', views.api_grupos, name='api_grupos'),
    path('api/lideres/', views.api_lideres, name='api_lideres'),
    path('api/supervisores/', views.api_supervisores, name='api_supervisores'),
]
