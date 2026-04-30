from django.contrib import admin
from .models import (
    Colaborador, Ferias, Ocorrencia, DocumentoPessoal,
    HistoricoSetor, HistoricoPosto, HistoricoSalario, HistoricoColaborador
)
from qms.admin import admin_site


class ColaboradorAdmin(admin.ModelAdmin):
    list_display = ['matricula', 'nome_completo', 'cargo', 'setor', 'turno', 'is_active', 'afastado']
    search_fields = ['matricula', 'nome_completo', 'cpf']
    list_filter = ['setor', 'turno', 'is_active', 'afastado']
    list_select_related = ['setor']  # FK optimization
    ordering = ['matricula']
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('matricula', 'cpf', 'nome_completo', 'cargo', 'grupo')
        }),
        ('Organização', {
            'fields': ('setor', 'centro_custo', 'turno')
        }),
        ('Hierarquia', {
            'fields': ('lider', 'supervisor', 'gerente')
        }),
        ('Remuneração', {
            'fields': ('salario',)
        }),
        ('Status', {
            'fields': ('is_active', 'em_ferias')
        }),
        ('Afastamento', {
            'fields': ('afastado', 'tipo_afastamento', 'data_inicio_afastamento', 'data_fim_afastamento'),
            'description': 'Marque quando colaborador está afastado (INSS, Licença, etc.)'
        }),
        ('Treinamentos', {
            'fields': ('pacotes_treinamento',)
        }),
    )


class FeriasAdmin(admin.ModelAdmin):
    list_display = ['colaborador', 'data_inicio', 'data_fim', 'dias_solicitados']
    search_fields = ['colaborador__nome_completo']
    list_filter = ['data_inicio']
    ordering = ['-data_inicio']


class OcorrenciaAdmin(admin.ModelAdmin):
    list_display = ['colaborador', 'tipo', 'data_ocorrencia']
    search_fields = ['colaborador__nome_completo', 'tipo']
    list_filter = ['tipo']
    ordering = ['-data_ocorrencia']


class DocumentoPessoalAdmin(admin.ModelAdmin):
    list_display = ['colaborador', 'tipo_documento', 'numero_documento']
    search_fields = ['colaborador__nome_completo', 'numero_documento']
    list_filter = ['tipo_documento']
    ordering = ['colaborador']


class HistoricoSetorAdmin(admin.ModelAdmin):
    list_display = ['colaborador', 'setor_anterior', 'setor_novo', 'data_mudanca', 'data_efetiva']
    search_fields = ['colaborador__nome_completo']
    list_filter = ['data_mudanca', 'setor_novo']
    readonly_fields = ['data_mudanca']
    ordering = ['-data_mudanca']


class HistoricoPostoAdmin(admin.ModelAdmin):
    list_display = ['colaborador', 'cargo_anterior', 'cargo_novo', 'data_mudanca', 'data_efetiva']
    search_fields = ['colaborador__nome_completo']
    list_filter = ['data_mudanca']
    readonly_fields = ['data_mudanca']
    ordering = ['-data_mudanca']


class HistoricoSalarioAdmin(admin.ModelAdmin):
    list_display = ['colaborador', 'salario_anterior', 'salario_novo', 'diferenca', 'data_mudanca', 'data_efetiva']
    search_fields = ['colaborador__nome_completo']
    list_filter = ['data_mudanca']
    readonly_fields = ['data_mudanca', 'diferenca']
    ordering = ['-data_mudanca']


class HistoricoColaboradorAdmin(admin.ModelAdmin):
    list_display = ['colaborador', 'tipo_mudanca', 'data_mudanca', 'data_efetiva', 'aprovado']
    search_fields = ['colaborador__nome_completo']
    list_filter = ['tipo_mudanca', 'data_mudanca', 'aprovado']
    readonly_fields = ['data_mudanca', 'dados_anteriores', 'dados_novos']
    ordering = ['-data_mudanca']


admin_site.register(Colaborador, ColaboradorAdmin)
admin_site.register(Ferias, FeriasAdmin)
admin_site.register(Ocorrencia, OcorrenciaAdmin)
admin_site.register(DocumentoPessoal, DocumentoPessoalAdmin)
admin_site.register(HistoricoSetor, HistoricoSetorAdmin)
admin_site.register(HistoricoPosto, HistoricoPostoAdmin)
admin_site.register(HistoricoSalario, HistoricoSalarioAdmin)
admin_site.register(HistoricoColaborador, HistoricoColaboradorAdmin)
