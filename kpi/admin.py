from django.contrib import admin

from kpi.models import Indicador, Medicao, Motivo


@admin.register(Indicador)
class IndicadorAdmin(admin.ModelAdmin):
    list_display = ('nome', 'area', 'meta', 'sentido', 'periodicidade', 'ativo')
    list_filter = ('area', 'ativo')
    search_fields = ('nome',)


@admin.register(Motivo)
class MotivoAdmin(admin.ModelAdmin):
    list_display = ('indicador', 'data', 'descricao', 'quantidade')
    list_filter = ('indicador',)


@admin.register(Medicao)
class MedicaoAdmin(admin.ModelAdmin):
    list_display = ('indicador', 'periodo', 'valor')
    list_filter = ('indicador',)
