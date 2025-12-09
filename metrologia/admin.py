from django.contrib import admin
from .models import (
    CategoriaInstrumento, Instrumento, FaixaMedicao, HistoricoCalibracao,
    ArquivoPadrao, ResultadoFaixaCalibracao, OrdemCalibracao
)
from qms.models import SolicitacaoInstrumento, OcorrenciaInstrumento


class CategoriaInstrumentoAdmin(admin.ModelAdmin):
    list_display = ['nome']
    search_fields = ['nome']
    ordering = ['nome']


class InstrumentoAdmin(admin.ModelAdmin):
    list_display = ['tag', 'descricao', 'categoria', 'ativo', 'data_proxima_calibracao']
    search_fields = ['tag', 'descricao', 'serie']
    list_filter = ['categoria', 'ativo']
    ordering = ['-ativo', 'tag']


class FaixaMedicaoAdmin(admin.ModelAdmin):
    list_display = ['instrumento', 'valor_minimo', 'valor_maximo', 'unidade']
    search_fields = ['instrumento__tag']
    list_filter = ['instrumento__categoria']
    ordering = ['instrumento']


class HistoricoCalibracaoAdmin(admin.ModelAdmin):
    list_display = ['instrumento', 'data_calibracao', 'proxima_calibracao', 'fornecedor']
    search_fields = ['instrumento__tag']
    list_filter = ['data_calibracao']
    ordering = ['-data_calibracao']


class ArquivoPadraoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'descricao', 'data_upload']
    search_fields = ['nome']
    ordering = ['-data_upload']


class ResultadoFaixaCalibraoAdmin(admin.ModelAdmin):
    list_display = ['historico', 'faixa', 'resultado']
    search_fields = ['faixa__instrumento__tag']
    ordering = ['historico']


class SolicitacaoInstrumentoAdmin(admin.ModelAdmin):
    list_display = ['solicitante', 'tipo', 'data_solicitacao', 'status']
    search_fields = ['instrumento_alvo__tag']
    list_filter = ['status']
    ordering = ['-data_solicitacao']


class OcorrenciaInstrumentoAdmin(admin.ModelAdmin):
    list_display = ['instrumento', 'tipo', 'data_ocorrencia']
    search_fields = ['instrumento__tag']
    list_filter = ['tipo']
    ordering = ['-data_ocorrencia']


class OrdemCalibracaoAdmin(admin.ModelAdmin):
    list_display = ['instrumento', 'status', 'fornecedor']
    search_fields = ['instrumento__tag']
    list_filter = ['status']
    ordering = ['-data_prevista']


admin.site.register(CategoriaInstrumento, CategoriaInstrumentoAdmin)
admin.site.register(Instrumento, InstrumentoAdmin)
admin.site.register(FaixaMedicao, FaixaMedicaoAdmin)
admin.site.register(HistoricoCalibracao, HistoricoCalibracaoAdmin)
admin.site.register(ArquivoPadrao, ArquivoPadraoAdmin)
admin.site.register(ResultadoFaixaCalibracao, ResultadoFaixaCalibraoAdmin)
admin.site.register(SolicitacaoInstrumento, SolicitacaoInstrumentoAdmin)
admin.site.register(OcorrenciaInstrumento, OcorrenciaInstrumentoAdmin)
admin.site.register(OrdemCalibracao, OrdemCalibracaoAdmin)
