# -*- coding: utf-8 -*-
"""
Admin para o módulo Procedures
Consolida admin de training e procurements
"""

from django.contrib import admin
from .models import (
    Area, Procedimento, ProcedimentoRevisao, PacoteTreinamento, RegistroTreinamento,
    Fornecedor, AvaliacaoFornecedor, ProcessoCotacao, Orcamento
)
from qms.admin import admin_site


# ==============================================================================
# PROCEDIMENTOS E TREINAMENTOS
# ==============================================================================

class AreaAdmin(admin.ModelAdmin):
    list_display = ['nome']
    search_fields = ['nome']
    ordering = ['nome']


class ProcedimentoAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nome', 'numero_revisao', 'ultima_revisao']
    search_fields = ['codigo', 'nome']
    list_filter = ['ultima_revisao']
    ordering = ['codigo']


class ProcedimentoRevisaoAdmin(admin.ModelAdmin):
    list_display = ['procedimento', 'revisao', 'data_revisao']
    search_fields = ['procedimento__nome']
    list_filter = ['data_revisao']
    list_select_related = ['procedimento', 'elaborador', 'revisor', 'aprovador']
    ordering = ['-data_revisao']


class PacoteTreinamentoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'descricao']
    search_fields = ['nome', 'descricao']
    filter_horizontal = ['procedimentos']
    list_prefetch_related = ['procedimentos']
    ordering = ['nome']


class RegistroTreinamentoAdmin(admin.ModelAdmin):
    list_display = ['colaborador', 'procedimento', 'data_treinamento']
    search_fields = ['colaborador__nome_completo', 'procedimento__nome']
    list_filter = ['data_treinamento']
    list_select_related = ['colaborador', 'procedimento', 'revisor_qualidade']
    ordering = ['-data_treinamento']


# ==============================================================================
# FORNECEDORES E COTAÇÕES
# ==============================================================================

class FornecedorAdmin(admin.ModelAdmin):
    list_display = ['nome_fantasia', 'contato', 'email', 'telefone', 'status']
    search_fields = ['nome_fantasia', 'contato', 'email']
    list_filter = ['status']
    ordering = ['nome_fantasia']


class AvaliacaoFornecedorAdmin(admin.ModelAdmin):
    list_display = ['fornecedor', 'data_avaliacao', 'nota_tecnica']
    search_fields = ['fornecedor__nome_fantasia']
    list_filter = ['data_avaliacao']
    list_select_related = ['fornecedor', 'avaliador']
    ordering = ['-data_avaliacao']


class ProcessoCotacaoAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'data_abertura', 'prazo_limite', 'status']
    search_fields = ['titulo']
    list_filter = ['status']
    list_select_related = ['responsavel']
    list_prefetch_related = ['instrumentos']
    ordering = ['-data_abertura']


class OrcamentoAdmin(admin.ModelAdmin):
    list_display = ['processo', 'fornecedor', 'valor_total', 'prazo_execucao_dias']
    search_fields = ['processo__titulo', 'fornecedor__nome_fantasia']
    list_filter = ['processo']
    list_select_related = ['processo', 'fornecedor']
    ordering = ['-processo']


# ==============================================================================
# REGISTRO NO ADMIN
# ==============================================================================

# Procedimentos e Treinamentos
admin_site.register(Area, AreaAdmin)
admin_site.register(Procedimento, ProcedimentoAdmin)
admin_site.register(ProcedimentoRevisao, ProcedimentoRevisaoAdmin)
admin_site.register(PacoteTreinamento, PacoteTreinamentoAdmin)
admin_site.register(RegistroTreinamento, RegistroTreinamentoAdmin)

# Fornecedores e Cotações
admin_site.register(Fornecedor, FornecedorAdmin)
admin_site.register(AvaliacaoFornecedor, AvaliacaoFornecedorAdmin)
admin_site.register(ProcessoCotacao, ProcessoCotacaoAdmin)
admin_site.register(Orcamento, OrcamentoAdmin)
