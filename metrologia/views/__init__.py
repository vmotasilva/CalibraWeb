# -*- coding: utf-8 -*-
"""
Views for metrologia app - Importa todas as views do módulo
"""

from .views import (
    # Archive/File management
    renomear_arquivo_padrao_view,
    remover_arquivo_padrao_view,
    
    # Import/Export
    imp_instr_view,
    imp_historico_view,
    export_metrologia_view,
    export_etiquetas_view,
    
    # Dashboard and listings
    modulo_metrologia_view,
    
    # Instrument management
    novo_instrumento_view,
    detalhe_instrumento_view,
    
    # Calibration history
    registrar_historico_calibracao_view,
    remover_historico_view,
    anexar_certificado_historico_view,
    download_certificado_view,
    remover_certificado_historico_view,
    preview_certificado_view,
    aplicar_carimbo_certificado_view,
    visualizar_historico_calibracao_view,
    
    # API
    api_faixa_medicao_view,
)

from .novo_fluxo_cotacao import (
    # ETAPA 1: Solicitação de Cotação
    solicitacao_list,
    solicitacao_create,
    solicitacao_detail,
    solicitacao_delete,
    solicitacao_itens,
    item_solicitacao_edit,
    item_solicitacao_delete,
    
    # ETAPA 2: Cotações de Fornecedores
    cotacao_fornecedor_create,
    cotacao_fornecedor_detail,
    cotacao_fornecedor_itens,
    item_cotacao_delete,
    
    # ETAPA 3: Atendimentos
    atendimento_create,
    atendimento_detail,
    atendimento_confirmar,
    
    # API
    api_instrumentos_vencendo,
)

__all__ = [
    'renomear_arquivo_padrao_view',
    'remover_arquivo_padrao_view',
    'imp_instr_view',
    'imp_historico_view',
    'export_metrologia_view',
    'export_etiquetas_view',
    'modulo_metrologia_view',
    'novo_instrumento_view',
    'detalhe_instrumento_view',
    'registrar_historico_calibracao_view',
    'remover_historico_view',
    'anexar_certificado_historico_view',
    'download_certificado_view',
    'remover_certificado_historico_view',
    'preview_certificado_view',
    'aplicar_carimbo_certificado_view',
    'visualizar_historico_calibracao_view',
    'api_faixa_medicao_view',
    # NOVO FLUXO
    'solicitacao_list',
    'solicitacao_create',
    'solicitacao_detail',
    'solicitacao_itens',
    'item_solicitacao_edit',
    'item_solicitacao_delete',
    'cotacao_fornecedor_create',
    'cotacao_fornecedor_detail',
    'cotacao_fornecedor_itens',
    'item_cotacao_delete',
    'atendimento_create',
    'atendimento_detail',
    'atendimento_confirmar',
    'api_instrumentos_vencendo',]