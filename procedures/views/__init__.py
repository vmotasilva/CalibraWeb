"""
Procedures Module Views
"""

from .views import (
    # Procedimentos
    procedimentos_list_view,
    export_procedimentos_excel_view,
    download_template_procedimentos_view,
    importar_procedimentos_view,
    procedimento_matrizes_list_view,
    procedimento_matriz_detalhe_view,
    procedimento_responsabilidades_treinamento_view,
    importar_matrizes_subareas_view,
    download_template_matrizes_subareas_view,
    novo_procedimento_view,
    editar_procedimento_view,
    detalhe_procedimento_view,
    # API
    api_subareas_por_matriz_view,
    api_procedimentos_list,
    # Treinamentos
    treinamentos_list_view,
    treinamentos_historico_view,
    treinamentos_exportar_excel_view,
    treinamentos_detalhe_view,
    novo_treinamento_view,
    editar_treinamento_view,
    # Fornecedores
    fornecedores_list_view,
    novo_fornecedor_view,
    editar_fornecedor_view,
    detalhe_fornecedor_view,
    # Avaliações
    nova_avaliacao_fornecedor_view,
    # Cotações
    cotacoes_list_view,
    nova_cotacao_view,
    editar_cotacao_view,
    detalhe_cotacao_view,
    # Orçamentos
    novo_orcamento_view,
    editar_orcamento_view,
)

from . import (
    habilidades_views,
    perfis_views,
    avaliacoes_views,
    planejamento_views,
    gap_analysis_views,
    lista_presenca_views,
    validacao_views,
    template_mapeamento_views,
    avaliacao_eficacia_views,
    perguntas_avaliacao_views,
)

__all__ = [
    # Procedimentos
    'procedimentos_list_view',
    'export_procedimentos_excel_view',
    'download_template_procedimentos_view',
    'importar_procedimentos_view',
    'procedimento_matrizes_list_view',
    'procedimento_matriz_detalhe_view',
    'procedimento_responsabilidades_treinamento_view',
    'importar_matrizes_subareas_view',
    'download_template_matrizes_subareas_view',
    'novo_procedimento_view',
    'editar_procedimento_view',
    'detalhe_procedimento_view',
    # API
    'api_subareas_por_matriz_view',
    'api_procedimentos_list',
    # Treinamentos
    'treinamentos_list_view',
    'treinamentos_detalhe_view',
    'novo_treinamento_view',
    'editar_treinamento_view',
    # Fornecedores
    'fornecedores_list_view',
    'novo_fornecedor_view',
    'editar_fornecedor_view',
    'detalhe_fornecedor_view',
    # Avaliações
    'nova_avaliacao_fornecedor_view',
    # Cotações
    'cotacoes_list_view',
    'nova_cotacao_view',
    'editar_cotacao_view',
    'detalhe_cotacao_view',
    # Orçamentos
    'novo_orcamento_view',
    'editar_orcamento_view',
    # Submódulos de views
    'habilidades_views',
    'perfis_views',
    'avaliacoes_views',
    'planejamento_views',
    'gap_analysis_views',
    'lista_presenca_views',
    'validacao_views',
    'template_mapeamento_views',
    'avaliacao_eficacia_views',
    'perguntas_avaliacao_views',
]

from .avaliacao_eficacia_views import (
    avaliacao_eficacia_list_view,
    avaliacao_eficacia_registrar_view,
    avaliacao_eficacia_registrar_massa_view,
    avaliacao_eficacia_alterar_gestor_massa_view,
    avaliacao_eficacia_export_excel_view,
    exportar_avaliacao_eficacia_for142_view,
    exportar_avaliacao_eficacia_for142_massa_view,
    avaliacao_eficacia_search_options_api,
)

from .planejamento_views import (
    exportar_planejamento_for133_view,
    exportar_auto_avaliacao_for141_view,
)

from .perguntas_avaliacao_views import (
    perguntas_avaliacao_list_view,
    obter_perguntas_procedimento_api,
    salvar_perguntas_procedimento_api,
    exportar_preview_for141_procedimento_view,
)

__all__ += [
    'avaliacao_eficacia_list_view',
    'avaliacao_eficacia_registrar_view',
    'avaliacao_eficacia_registrar_massa_view',
    'avaliacao_eficacia_alterar_gestor_massa_view',
    'avaliacao_eficacia_export_excel_view',
    'exportar_avaliacao_eficacia_for142_view',
    'exportar_avaliacao_eficacia_for142_massa_view',
    'avaliacao_eficacia_search_options_api',
    'exportar_planejamento_for133_view',
    'exportar_auto_avaliacao_for141_view',
    'perguntas_avaliacao_list_view',
    'obter_perguntas_procedimento_api',
    'salvar_perguntas_procedimento_api',
    'exportar_preview_for141_procedimento_view',
]


