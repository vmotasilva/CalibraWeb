"""
Procedures Module Views
"""

from .views import (
    # Procedimentos
    procedimentos_list_view,
    export_procedimentos_excel_view,
    novo_procedimento_view,
    editar_procedimento_view,
    detalhe_procedimento_view,
    # Treinamentos
    treinamentos_list_view,
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

__all__ = [
    # Procedimentos
    'procedimentos_list_view',
    'export_procedimentos_excel_view',
    'novo_procedimento_view',
    'editar_procedimento_view',
    'detalhe_procedimento_view',
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
]
