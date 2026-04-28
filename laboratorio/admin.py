from django.contrib import admin

from .models import CategoriaLaboratorio, OcorrenciaLaboratorio


@admin.register(CategoriaLaboratorio)
class CategoriaLaboratorioAdmin(admin.ModelAdmin):
    list_display = ("nome", "impacto", "ativo", "atualizado_em")
    list_filter = ("impacto", "ativo")
    search_fields = ("nome", "descricao")


@admin.register(OcorrenciaLaboratorio)
class OcorrenciaLaboratorioAdmin(admin.ModelAdmin):
    list_display = (
        "assunto",
        "categoria",
        "impacto",
        "responsavel",
        "data_abertura",
        "data_encerramento",
    )
    list_filter = ("impacto", "categoria", "data_abertura")
    search_fields = ("assunto", "detalhamento", "consequencias")
    autocomplete_fields = ("categoria", "responsavel")
