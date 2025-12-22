# -*- coding: utf-8 -*-
"""
Configuração da aplicação Procedures
Consolida: training (procedimentos/treinamentos) + procurements (fornecedores/cotações)
"""

from django.apps import AppConfig


class ProceduresConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'procedures'
    verbose_name = 'Procedures - Procedimentos, Treinamentos, Fornecedores e Cotações'
    
    def ready(self):
        """Importa signals ao iniciar a aplicação."""
        import procedures.signals
