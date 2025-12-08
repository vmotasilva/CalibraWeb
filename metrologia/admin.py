from django.contrib import admin
from .models import (
    CategoriaInstrumento, Instrumento, FaixaMedicao, HistoricoCalibracao,
    ArquivoPadrao, ResultadoFaixaCalibracao, OrdemCalibracao
)
from qms.models import SolicitacaoInstrumento, OcorrenciaInstrumento, ImportJob

# Register your models here.
admin.site.register(CategoriaInstrumento)
admin.site.register(Instrumento)
admin.site.register(FaixaMedicao)
admin.site.register(HistoricoCalibracao)
admin.site.register(ArquivoPadrao)
admin.site.register(ResultadoFaixaCalibracao)
admin.site.register(SolicitacaoInstrumento)
admin.site.register(OcorrenciaInstrumento)
admin.site.register(OrdemCalibracao)
admin.site.register(ImportJob)
