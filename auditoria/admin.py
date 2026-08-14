from django.contrib import admin

from .models import (
    ComentarioAuditoria, ModeloAuditoria, PerguntaAuditoria, RegistroAuditoria, RespostaAuditoria,
    Norma, ItemNorma, BancoPergunta, AuditoriaIso, RespostaEntrevistaIso
)

@admin.register(ModeloAuditoria)
class ModeloAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("nome", "periodicidade", "ativo", "criado_em")
    list_filter = ("periodicidade", "ativo")
    search_fields = ("nome", "objeto_auditoria")


@admin.register(PerguntaAuditoria)
class PerguntaAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("modelo", "ordem", "pergunta", "tipo_resposta", "obrigatoria", "ativo")
    list_filter = ("modelo", "tipo_resposta", "obrigatoria", "ativo")
    search_fields = ("pergunta", "modelo__nome")


class RespostaAuditoriaInline(admin.TabularInline):
    model = RespostaAuditoria
    extra = 0


@admin.register(ComentarioAuditoria)
class ComentarioAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("modelo", "autor", "criado_em")
    list_filter = ("modelo", "criado_em")
    search_fields = ("modelo__nome", "autor__username", "texto")


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("modelo", "data_auditoria", "periodo_inicio", "periodo_fim", "avaliador")
    list_filter = ("modelo", "data_auditoria")
    search_fields = ("modelo__nome", "avaliador__username", "observacoes")
    inlines = [RespostaAuditoriaInline]


# ==========================================
# ADMIN PARA AUDITORIA MODO ENTREVISTA (ISO)
# ==========================================

@admin.register(Norma)
class NormaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "ativa")
    search_fields = ("codigo", "descricao")
    list_filter = ("ativa",)


@admin.register(ItemNorma)
class ItemNormaAdmin(admin.ModelAdmin):
    list_display = ("referencia", "titulo", "norma", "ordem")
    search_fields = ("referencia", "titulo", "norma__codigo")
    list_filter = ("norma",)


@admin.register(BancoPergunta)
class BancoPerguntaAdmin(admin.ModelAdmin):
    list_display = ("texto_pergunta", "ativa")
    search_fields = ("texto_pergunta", "dica_auditor")
    list_filter = ("ativa",)
    filter_horizontal = ("itens_norma",)


class RespostaEntrevistaIsoInline(admin.TabularInline):
    model = RespostaEntrevistaIso
    extra = 0


@admin.register(AuditoriaIso)
class AuditoriaIsoAdmin(admin.ModelAdmin):
    list_display = ("norma", "data_inicio", "status", "criado_em")
    list_filter = ("status", "norma")
    search_fields = ("norma__codigo",)
    filter_horizontal = ("auditores", "escopo_itens")
    inlines = [RespostaEntrevistaIsoInline]
