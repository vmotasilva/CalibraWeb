from django.contrib import admin

from .models import (
    CategoriaInsumo,
    ComentarioInsumos,
    ModeloAuditoria,
    PerguntaAuditoria,
    RegistroAuditoria,
    RespostaAuditoria,
)


@admin.register(CategoriaInsumo)
class CategoriaInsumoAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativo", "atualizado_em")
    list_filter = ("ativo",)
    search_fields = ("nome", "descricao")


@admin.register(ModeloAuditoria)
class ModeloAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("nome", "categoria", "tipo_maquina", "periodicidade", "ativo", "criado_em")
    list_filter = ("categoria", "tipo_maquina", "periodicidade", "ativo")
    search_fields = ("nome", "objeto_auditoria")
    filter_horizontal = ("responsaveis",)
    exclude = ("maquinas",)


@admin.register(PerguntaAuditoria)
class PerguntaAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("modelo", "ordem", "pergunta", "tipo_resposta", "obrigatoria", "ativo")
    list_filter = ("modelo", "tipo_resposta", "obrigatoria", "ativo")
    search_fields = ("pergunta", "modelo__nome")


class RespostaAuditoriaInline(admin.TabularInline):
    model = RespostaAuditoria
    extra = 0


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("modelo", "data_auditoria", "periodo_inicio", "periodo_fim", "avaliador")
    list_filter = ("modelo", "data_auditoria")
    search_fields = ("modelo__nome", "avaliador__username", "observacoes")
    inlines = [RespostaAuditoriaInline]


@admin.register(ComentarioInsumos)
class ComentarioInsumosAdmin(admin.ModelAdmin):
    list_display = ("modelo", "autor", "criado_em")
    list_filter = ("modelo", "criado_em")
    search_fields = ("texto", "modelo__nome", "autor__username", "autor__first_name", "autor__last_name")

