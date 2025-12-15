from django.contrib import admin
from .models import (
    CategoriaInstrumento, Instrumento, FaixaMedicao, HistoricoCalibracao,
    ArquivoPadrao, ResultadoFaixaCalibracao, OrdemCalibracao,
    InstrumentoReferencia, FaixaMedicaoPadrao, Cotacao, OcorrenciaCotacao,
    SolicitacaoCotacao, ItemSolicitacaoCotacao, CotacaoFornecedor, 
    ItemCotacao, AtendimentoSolicitacao, ProcessoAutomatizacao
)
from qms.models import SolicitacaoInstrumento, OcorrenciaInstrumento
from qms.admin import admin_site


class CategoriaInstrumentoAdmin(admin.ModelAdmin):
    list_display = ['nome']
    search_fields = ['nome']
    ordering = ['nome']


class InstrumentoAdmin(admin.ModelAdmin):
    list_display = ['tag', 'descricao', 'categoria', 'tratativa_calibracao', 'ativo', 'data_proxima_calibracao']
    search_fields = ['tag', 'descricao', 'serie']
    list_filter = ['categoria', 'tratativa_calibracao', 'ativo']
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


# ==============================================================================
# NOVO FLUXO DE COTAÇÕES - ETAPAS 1-4
# ==============================================================================

class ItemSolicitacaoCotacaoInline(admin.TabularInline):
    model = ItemSolicitacaoCotacao
    extra = 1
    fields = ['instrumento', 'necessidade', 'quantidade', 'notas']


class SolicitacaoCotacaoAdmin(admin.ModelAdmin):
    list_display = ['numero', 'status', 'responsavel', 'data_criacao']
    search_fields = ['numero', 'responsavel__username']
    list_filter = ['status', 'data_criacao', 'departamento']
    readonly_fields = ['numero', 'data_criacao', 'atualizado_em']
    inlines = [ItemSolicitacaoCotacaoInline]
    fieldsets = (
        ('Identificação', {
            'fields': ('numero', 'data_criacao', 'atualizado_em')
        }),
        ('Responsáveis', {
            'fields': ('responsavel', 'departamento')
        }),
        ('Período de Vencimento', {
            'fields': ('dias_vencimento',)
        }),
        ('Status', {
            'fields': ('status',)
        }),
    )
    ordering = ['-data_criacao']


class ItemCotacaoInline(admin.TabularInline):
    model = ItemCotacao
    extra = 1
    fields = ['instrumento', 'pode_atender', 'tipo_servico', 'valor_unitario', 'quantidade', 'valor_total', 'prazo_dias']
    readonly_fields = ['valor_total']


class CotacaoFornecedorAdmin(admin.ModelAdmin):
    list_display = ['numero', 'fornecedor', 'status', 'solicitacao', 'data_criacao']
    search_fields = ['numero', 'fornecedor__empresa', 'observacoes']
    list_filter = ['status', 'data_criacao', 'solicitacao']
    readonly_fields = ['numero', 'data_criacao', 'atualizado_em']
    inlines = [ItemCotacaoInline]
    fieldsets = (
        ('Identificação', {
            'fields': ('numero', 'solicitacao', 'fornecedor', 'data_criacao', 'atualizado_em')
        }),
        ('Datas Importantes', {
            'fields': ('data_envio_para_fornecedor', 'data_proposta_recebida'),
            'classes': ('collapse',)
        }),
        ('Status e Observações', {
            'fields': ('status', 'observacoes')
        }),
        ('Rastreamento', {
            'fields': ('criado_por',),
            'classes': ('collapse',)
        }),
    )
    ordering = ['-data_criacao']


class ItemCotacaoAdmin(admin.ModelAdmin):
    list_display = ['instrumento', 'cotacao_fornecedor', 'pode_atender', 'tipo_servico', 'valor_total', 'prazo_dias']
    search_fields = ['instrumento__tag', 'cotacao_fornecedor__numero', 'descricao_servico']
    list_filter = ['pode_atender', 'tipo_servico', 'data_criacao']
    readonly_fields = ['valor_total', 'data_criacao']
    fieldsets = (
        ('Identificação', {
            'fields': ('cotacao_fornecedor', 'item_solicitacao', 'instrumento', 'data_criacao')
        }),
        ('Capacidade de Atendimento', {
            'fields': ('pode_atender', 'tipo_servico')
        }),
        ('Valores', {
            'fields': ('valor_unitario', 'quantidade', 'valor_total')
        }),
        ('Execução', {
            'fields': ('prazo_dias', 'descricao_servico')
        }),
    )
    ordering = ['-data_criacao']


class AtendimentoSolicitacaoAdmin(admin.ModelAdmin):
    list_display = ['id', 'item_solicitacao', 'item_cotacao', 'status', 'data_prevista_atendimento', 'responsavel']
    search_fields = ['item_solicitacao__instrumento__tag', 'solicitacao__numero']
    list_filter = ['status', 'data_escolha', 'data_prevista_atendimento']
    readonly_fields = ['data_escolha', 'atualizado_em']
    fieldsets = (
        ('Necessidade e Cotação', {
            'fields': ('solicitacao', 'item_solicitacao', 'item_cotacao')
        }),
        ('Atribuição', {
            'fields': ('responsavel', 'data_escolha')
        }),
        ('Execução', {
            'fields': ('data_prevista_atendimento', 'status')
        }),
        ('Observações', {
            'fields': ('observacoes', 'atualizado_em')
        }),
    )
    ordering = ['-data_escolha']


class ProcessoAutomatizacaoAdmin(admin.ModelAdmin):
    list_display = ['id', 'atendimento', 'tipo_processo', 'status', 'data_inicio', 'data_conclusao']
    search_fields = ['atendimento__id', 'observacoes']
    list_filter = ['tipo_processo', 'status', 'data_inicio']
    readonly_fields = ['data_inicio', 'data_conclusao', 'atualizado_em']
    fieldsets = (
        ('Atendimento', {
            'fields': ('atendimento',)
        }),
        ('Processo', {
            'fields': ('tipo_processo', 'status')
        }),
        ('Objeto Criado', {
            'fields': ('nome_modelo_objeto', 'id_objeto_criado')
        }),
        ('Timeline', {
            'fields': ('data_inicio', 'data_conclusao', 'atualizado_em')
        }),
        ('Observações', {
            'fields': ('observacoes',)
        }),
    )
    ordering = ['-data_inicio']


admin_site.register(SolicitacaoCotacao, SolicitacaoCotacaoAdmin)
admin_site.register(ItemSolicitacaoCotacao, admin.ModelAdmin)
admin_site.register(CotacaoFornecedor, CotacaoFornecedorAdmin)
admin_site.register(ItemCotacao, ItemCotacaoAdmin)
admin_site.register(AtendimentoSolicitacao, AtendimentoSolicitacaoAdmin)
admin_site.register(ProcessoAutomatizacao, ProcessoAutomatizacaoAdmin)
