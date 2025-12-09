from django.contrib import admin
from .models import Colaborador, Ferias, Ocorrencia, DocumentoPessoal
from qms.admin import admin_site


class ColaboradorAdmin(admin.ModelAdmin):
    list_display = ['matricula', 'nome_completo', 'cargo', 'setor', 'turno', 'is_active']
    search_fields = ['matricula', 'nome_completo', 'cpf']
    list_filter = ['setor', 'turno', 'is_active']
    list_select_related = ['setor']  # FK optimization
    ordering = ['matricula']


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


admin_site.register(Colaborador, ColaboradorAdmin)
admin_site.register(Ferias, FeriasAdmin)
admin_site.register(Ocorrencia, OcorrenciaAdmin)
admin_site.register(DocumentoPessoal, DocumentoPessoalAdmin)
