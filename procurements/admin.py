from django.contrib import admin
from .models import Fornecedor, AvaliacaoFornecedor, ProcessoCotacao, Orcamento


class FornecedorAdmin(admin.ModelAdmin):
    list_display = ['nome_fantasia', 'contato', 'email', 'telefone', 'status']
    search_fields = ['nome_fantasia', 'contato', 'email']
    list_filter = ['status']
    ordering = ['nome_fantasia']


class AvaliacaoFornecedorAdmin(admin.ModelAdmin):
    list_display = ['fornecedor', 'data_avaliacao', 'nota_tecnica']
    search_fields = ['fornecedor__nome_fantasia']
    list_filter = ['data_avaliacao']
    ordering = ['-data_avaliacao']


class ProcessoCotacaoAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'data_abertura', 'prazo_limite', 'status']
    search_fields = ['titulo']
    list_filter = ['status']
    ordering = ['-data_abertura']


class OrcamentoAdmin(admin.ModelAdmin):
    list_display = ['processo', 'fornecedor', 'valor_total', 'prazo_execucao_dias']
    search_fields = ['processo__titulo', 'fornecedor__nome_fantasia']
    list_filter = ['processo']
    ordering = ['-processo']


admin.site.register(Fornecedor, FornecedorAdmin)
admin.site.register(AvaliacaoFornecedor, AvaliacaoFornecedorAdmin)
admin.site.register(ProcessoCotacao, ProcessoCotacaoAdmin)
admin.site.register(Orcamento, OrcamentoAdmin)
