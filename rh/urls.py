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
    path('api/colaboradores-filtrados/', views.api_colaboradores_filtrados, name='api_colaboradores_filtrados'),
    path('api/colaborador/<int:colab_id>/delete/', views.api_delete_colaborador, name='api_delete_colaborador'),
    path('api/colaboradores/delete-multiple/', views.api_delete_colaboradores_multiple, name='api_delete_colaboradores_multiple'),
    path('api/setores/', views.api_setores, name='api_setores'),
    path('api/cargos/', views.api_cargos, name='api_cargos'),
    path('api/grupos/', views.api_grupos, name='api_grupos'),
    path('api/lideres/', views.api_lideres, name='api_lideres'),
    path('api/supervisores/', views.api_supervisores, name='api_supervisores'),
    
    # Exportação de Férias
    path('gestao-ferias/exportar/', views.exportar_ferias_view, name='exportar_ferias'),
    
    # Seção Usuários - Gerenciamento de Usuários e Permissões
    path('usuarios/', views.listar_usuarios_view, name='listar_usuarios'),
    path('usuarios/criar/', views.criar_usuario_view, name='criar_usuario'),
    path('usuarios/<int:user_id>/', views.detalhe_usuario_view, name='detalhe_usuario'),
    path('api/permissoes/atualizar/', views.api_atualizar_permissao, name='api_atualizar_permissao'),
    path('api/permissoes/atualizar-lote/', views.api_atualizar_permissoes_lote, name='api_atualizar_permissoes_lote'),
    path('api/permissoes/toggle-staff/', views.api_toggle_staff, name='api_toggle_staff'),
    path('api/permissoes/toggle-superuser/', views.api_toggle_superuser, name='api_toggle_superuser'),
    path('api/usuarios/toggle-active/', views.api_toggle_user_active, name='api_toggle_user_active'),
    path('api/usuarios/reset-password/', views.api_reset_password, name='api_reset_password'),
    path('api/usuarios/vincular-colaborador/', views.api_vincular_colaborador, name='api_vincular_colaborador'),
    path('api/colaboradores-sem-vinculo/', views.api_colaboradores_sem_vinculo, name='api_colaboradores_sem_vinculo'),
    path('api/usuarios/criar/', views.api_criar_usuario, name='api_criar_usuario'),
]
