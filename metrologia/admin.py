from django.contrib import admin
from .models import (
    CategoriaInstrumento, Instrumento, FaixaMedicao, HistoricoCalibracao,
    ArquivoPadrao, ResultadoFaixaCalibracao, OrdemCalibracao,
    InstrumentoReferencia, FaixaMedicaoPadrao, Cotacao, OcorrenciaCotacao
)
from qms.models import SolicitacaoInstrumento, OcorrenciaInstrumento
from qms.admin import admin_site


class CategoriaInstrumentoAdmin(admin.ModelAdmin):
    list_display = ['nome']
    search_fields = ['nome']
    ordering = ['nome']


class InstrumentoAdmin(admin.ModelAdmin):
    list_display = ['tag', 'descricao', 'categoria', 'ativo', 'data_proxima_calibracao']
    search_fields = ['tag', 'descricao', 'serie']
    list_filter = ['categoria', 'ativo']
    list_select_related = ['categoria', 'responsavel', 'setor']  # FK optimization
    list_prefetch_related = ['processocotacao']  # M2M optimization
    ordering = ['-ativo', 'tag']


class FaixaMedicaoAdmin(admin.ModelAdmin):
    list_display = ['instrumento', 'valor_minimo', 'valor_maximo', 'unidade']
    search_fields = ['instrumento__tag']
    list_filter = ['instrumento__categoria']
    list_select_related = ['instrumento', 'unidade']  # FK optimization
    ordering = ['instrumento']


class HistoricoCalibracaoAdmin(admin.ModelAdmin):
    list_display = ['instrumento', 'data_calibracao', 'proxima_calibracao', 'fornecedor']
    search_fields = ['instrumento__tag']
    list_filter = ['data_calibracao']
    list_select_related = ['instrumento']  # FK optimization
    list_prefetch_related = ['arquivos_padroes']  # M2M optimization
    ordering = ['-data_calibracao']


class ArquivoPadraoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'descricao', 'data_upload']
    search_fields = ['nome']
    ordering = ['-data_upload']


class ResultadoFaixaCalibraoAdmin(admin.ModelAdmin):
    list_display = ['historico', 'faixa', 'resultado']
    search_fields = ['faixa__instrumento__tag']
    list_select_related = ['historico', 'faixa']  # FK optimization
    ordering = ['historico']


class SolicitacaoInstrumentoAdmin(admin.ModelAdmin):
    list_display = ['solicitante', 'tipo', 'data_solicitacao', 'status']
    search_fields = ['instrumento_alvo__tag']
    list_filter = ['status']
    list_select_related = ['solicitante', 'instrumento_alvo']  # FK optimization
    ordering = ['-data_solicitacao']


class OcorrenciaInstrumentoAdmin(admin.ModelAdmin):
    list_display = ['instrumento', 'tipo', 'data_ocorrencia']
    search_fields = ['instrumento__tag']
    list_filter = ['tipo']
    list_select_related = ['instrumento', 'usuario_responsavel']  # FK optimization
    ordering = ['-data_ocorrencia']


class OrdemCalibracaoAdmin(admin.ModelAdmin):
    list_display = ['instrumento', 'status', 'fornecedor']
    search_fields = ['instrumento__tag']
    list_filter = ['status']
    list_select_related = ['instrumento']  # FK optimization
    ordering = ['-data_prevista']


class InstrumentoReferenciaAdmin(admin.ModelAdmin):
    list_display = ['codigo_referencia', 'categoria', 'data_criacao', 'data_atualizacao']
    search_fields = ['codigo_referencia', 'descricao']
    list_filter = ['categoria', 'data_criacao']
    list_select_related = ['categoria']  # FK optimization
    readonly_fields = ['data_criacao', 'data_atualizacao']
    ordering = ['codigo_referencia']


class FaixaMedicaoPadraoAdmin(admin.ModelAdmin):
    list_display = ['referencia_instrumento', 'unidade', 'valor_minimo', 'valor_maximo', 'ativa']
    search_fields = ['referencia_instrumento__codigo_referencia']
    list_filter = ['ativa', 'referencia_instrumento__categoria', 'data_criacao']
    list_select_related = ['referencia_instrumento', 'unidade']  # FK optimization
    readonly_fields = ['data_criacao', 'data_atualizacao']
    fieldsets = (
        ('Referência e Unidade', {
            'fields': ('referencia_instrumento', 'unidade')
        }),
        ('Limites de Medição', {
            'fields': ('valor_minimo', 'valor_maximo')
        }),
        ('Parâmetros de Medição', {
            'fields': ('resolucao', 'nominal', 'tolerancia_mais_menos')
        }),
        ('Status e Auditoria', {
            'fields': ('ativa', 'data_criacao', 'data_atualizacao')
        }),
    )
    ordering = ['referencia_instrumento', 'unidade']


# ==============================================================================
# COTAÇÃO
# ==============================================================================

class OcorrenciaCotacaoInline(admin.TabularInline):
    model = OcorrenciaCotacao
    extra = 0
    fields = ['tipo', 'data', 'descricao', 'resolvida']
    readonly_fields = ['data']


class CotacaoAdmin(admin.ModelAdmin):
    list_display = ['id', 'fornecedor', 'status', 'valor', 'data_criacao']
    search_fields = ['fornecedor__empresa', 'observacoes']
    list_filter = ['status', 'data_criacao']
    filter_horizontal = ['instrumentos']
    readonly_fields = ['data_criacao', 'data_envio', 'data_proposta', 'data_decisao', 'atualizado_em']
    inlines = [OcorrenciaCotacaoInline]
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('fornecedor', 'status', 'criado_por')
        }),
        ('Instrumentos e Valor', {
            'fields': ('instrumentos', 'valor')
        }),
        ('Observações', {
            'fields': ('observacoes',)
        }),
        ('Datas', {
            'fields': ('data_criacao', 'data_envio', 'data_proposta', 'data_decisao', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )
    ordering = ['-data_criacao']


class OcorrenciaCotacaoAdmin(admin.ModelAdmin):
    list_display = ['cotacao', 'tipo', 'data', 'resolvida', 'responsavel']
    search_fields = ['cotacao__id', 'descricao']
    list_filter = ['tipo', 'resolvida', 'data']
    readonly_fields = ['data', 'responsavel']
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('cotacao', 'tipo', 'responsavel')
        }),
        ('Descrição', {
            'fields': ('descricao', 'acao_tomada')
        }),
        ('Resolução', {
            'fields': ('resolvida', 'data_resolucao')
        }),
        ('Data', {
            'fields': ('data',),
            'classes': ('collapse',)
        }),
    )
    ordering = ['-data']


admin_site.register(CategoriaInstrumento, CategoriaInstrumentoAdmin)
admin_site.register(Instrumento, InstrumentoAdmin)
admin_site.register(FaixaMedicao, FaixaMedicaoAdmin)
admin_site.register(HistoricoCalibracao, HistoricoCalibracaoAdmin)
admin_site.register(ArquivoPadrao, ArquivoPadraoAdmin)
admin_site.register(ResultadoFaixaCalibracao, ResultadoFaixaCalibraoAdmin)
admin_site.register(SolicitacaoInstrumento, SolicitacaoInstrumentoAdmin)
admin_site.register(OcorrenciaInstrumento, OcorrenciaInstrumentoAdmin)
admin_site.register(OrdemCalibracao, OrdemCalibracaoAdmin)
admin_site.register(InstrumentoReferencia, InstrumentoReferenciaAdmin)
admin_site.register(FaixaMedicaoPadrao, FaixaMedicaoPadraoAdmin)
admin_site.register(Cotacao, CotacaoAdmin)
admin_site.register(OcorrenciaCotacao, OcorrenciaCotacaoAdmin)
