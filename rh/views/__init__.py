

from .views import (
    modulo_rh_view,
    detalhe_colaborador_view,
    editar_colaborador_view,
    registrar_ocorrencia_view,
    editar_ocorrencia_view,
    deletar_ocorrencia_view,
    listar_ocorrencias_view,
    registrar_ferias_view,
    editar_ferias_view,
    excluir_ferias_view,
    # API endpoints
    api_colaboradores,
    api_setores,
    api_cargos,
    api_grupos,
    api_lideres,
    api_supervisores,
)

__all__ = [
    'modulo_rh_view',
    'detalhe_colaborador_view',
    'editar_colaborador_view',
    'registrar_ocorrencia_view',
    'editar_ocorrencia_view',
    'deletar_ocorrencia_view',
    'listar_ocorrencias_view',
    'registrar_ferias_view',
    'editar_ferias_view',
    'excluir_ferias_view',
    # API endpoints
    'api_colaboradores',
    'api_setores',
    'api_cargos',
    'api_grupos',
    'api_lideres',
    'api_supervisores',
]
