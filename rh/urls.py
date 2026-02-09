from django.urls import path
from rh.views.views import (
    detalhe_colaborador_view,
    criar_colaborador_view,
    gestao_ferias_view,
    atualizar_status_ferias_view,
    importar_ferias_view,
    criar_ferias_view,
    editar_ferias_view,
    excluir_ferias_view,
    api_colaboradores,
    api_colaboradores_filtrados,
    api_delete_colaborador,
    api_delete_colaboradores_multiple,
    api_setores,
    api_cargos,
    api_grupos,
    api_lideres,
    api_supervisores,
    exportar_ferias_view,
    listar_usuarios_view,
    criar_usuario_view,
    detalhe_usuario_view,
    api_atualizar_permissao,
    api_atualizar_permissoes_lote,
    api_toggle_staff,
    api_toggle_superuser,
    api_toggle_user_active,
    api_reset_password,
    api_vincular_colaborador,
    api_colaboradores_sem_vinculo,
    api_criar_usuario,
    atualizar_liderancas_em_massa,
)

app_name = 'rh'

urlpatterns = [
    # Detalhe do colaborador
    path('colaborador/<int:colab_id>/', detalhe_colaborador_view, name='detalhe_colaborador'),
    path('colaborador/criar/', criar_colaborador_view, name='criar_colaborador'),
    
    # Dashboard e gestão
    path('gestao-ferias/', gestao_ferias_view, name='gestao_ferias'),
    path('gestao-ferias/atualizar-status/', atualizar_status_ferias_view, name='atualizar_status_ferias'),
    path('gestao-ferias/importar/', importar_ferias_view, name='importar_ferias'),
    path('gestao-ferias/criar/', criar_ferias_view, name='criar_ferias'),
    path('gestao-ferias/criar/<int:colab_id>/', criar_ferias_view, name='criar_ferias_colab'),
    path('<int:colab_id>/ferias/<int:ferias_id>/editar/', editar_ferias_view, name='editar_ferias'),
    path('<int:colab_id>/ferias/<int:ferias_id>/excluir/', excluir_ferias_view, name='excluir_ferias'),
    
    # API Endpoints
    path('api/colaboradores/', api_colaboradores, name='api_colaboradores'),
    path('api/colaboradores-filtrados/', api_colaboradores_filtrados, name='api_colaboradores_filtrados'),
    path('api/colaborador/<int:colab_id>/delete/', api_delete_colaborador, name='api_delete_colaborador'),
    path('api/colaboradores/delete-multiple/', api_delete_colaboradores_multiple, name='api_delete_colaboradores_multiple'),
    path('api/setores/', api_setores, name='api_setores'),
    path('api/cargos/', api_cargos, name='api_cargos'),
    path('api/grupos/', api_grupos, name='api_grupos'),
    path('api/lideres/', api_lideres, name='api_lideres'),
    path('api/supervisores/', api_supervisores, name='api_supervisores'),
    
    # Atualização em massa
    path('atualizar-liderancas/', atualizar_liderancas_em_massa, name='atualizar_liderancas_em_massa'),
    
    # Exportação de Férias
    path('gestao-ferias/exportar/', exportar_ferias_view, name='exportar_ferias'),
    
    # Seção Usuários - Gerenciamento de Usuários e Permissões
    path('usuarios/', listar_usuarios_view, name='listar_usuarios'),
    path('usuarios/criar/', criar_usuario_view, name='criar_usuario'),
    path('usuarios/<int:user_id>/', detalhe_usuario_view, name='detalhe_usuario'),
    path('api/permissoes/atualizar/', api_atualizar_permissao, name='api_atualizar_permissao'),
    path('api/permissoes/atualizar-lote/', api_atualizar_permissoes_lote, name='api_atualizar_permissoes_lote'),
    path('api/permissoes/toggle-staff/', api_toggle_staff, name='api_toggle_staff'),
    path('api/permissoes/toggle-superuser/', api_toggle_superuser, name='api_toggle_superuser'),
    path('api/usuarios/toggle-active/', api_toggle_user_active, name='api_toggle_user_active'),
    path('api/usuarios/reset-password/', api_reset_password, name='api_reset_password'),
    path('api/usuarios/vincular-colaborador/', api_vincular_colaborador, name='api_vincular_colaborador'),
    path('api/colaboradores-sem-vinculo/', api_colaboradores_sem_vinculo, name='api_colaboradores_sem_vinculo'),
    path('api/usuarios/criar/', api_criar_usuario, name='api_criar_usuario'),
]
