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
]
