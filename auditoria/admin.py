from django.contrib import admin

from .models import ModeloAuditoria, PerguntaAuditoria, RegistroAuditoria, RespostaAuditoria


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


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("modelo", "data_auditoria", "periodo_inicio", "periodo_fim", "avaliador")
    list_filter = ("modelo", "data_auditoria")
    search_fields = ("modelo__nome", "avaliador__username", "observacoes")
    inlines = [RespostaAuditoriaInline]
