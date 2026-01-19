"""
Procedures Module Views
"""

from .views import (
    # Procedimentos
    procedimentos_list_view,
    export_procedimentos_excel_view,
    download_template_procedimentos_view,
    importar_procedimentos_view,
    novo_procedimento_view,
    editar_procedimento_view,
    detalhe_procedimento_view,
    # API
    api_procedimentos_list,
    # Treinamentos
    treinamentos_list_view,
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
)

__all__ = [
    # Procedimentos
    'procedimentos_list_view',
    'export_procedimentos_excel_view',
    'download_template_procedimentos_view',
    'importar_procedimentos_view',
    'novo_procedimento_view',
    'editar_procedimento_view',
    'detalhe_procedimento_view',
    # API
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
]
