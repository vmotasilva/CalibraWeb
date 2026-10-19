from django.contrib import admin

from kpi.models import Indicador, Medicao


@admin.register(Indicador)
class IndicadorAdmin(admin.ModelAdmin):
    list_display = ('nome', 'area', 'meta', 'sentido', 'periodicidade', 'ativo')
    list_filter = ('area', 'ativo')
    search_fields = ('nome',)


@admin.register(Medicao)
class MedicaoAdmin(admin.ModelAdmin):
    list_display = ('indicador', 'periodo', 'valor')
    list_filter = ('indicador',)
