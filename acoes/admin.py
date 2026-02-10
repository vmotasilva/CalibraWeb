from django.contrib import admin

from django.contrib import admin
from .models import AcaoCorretiva, AcaoComentario
from qms.admin import admin_site


class AcaoComentarioInline(admin.TabularInline):
    model = AcaoComentario
    extra = 1
    readonly_fields = ('data_criacao', 'autor')
    fields = ('autor', 'conteudo', 'data_criacao')


class AcaoCorretivaAdmin(admin.ModelAdmin):
    list_display = ['numero_registro', 'titulo', 'tipo_solucao', 'status', 'responsavel', 'data_vencimento', 'esta_vencida']
    list_filter = ['tipo', 'status', 'prioridade', 'ano', 'data_abertura']
    search_fields = ['numero_registro', 'titulo', 'descricao', 'responsavel__nome_completo']
    readonly_fields = ['data_abertura']
    inlines = [AcaoComentarioInline]
    
    fieldsets = (
        ('Identificação', {
            'fields': ('numero_registro', 'ano', 'unidade')
        }),
        ('Informações da Ação', {
            'fields': ('titulo', 'descricao', 'tipo', 'tipo_solucao', 'prioridade')
        }),
        ('Origem e Análise', {
            'fields': ('origem', 'causa_raiz')
        }),
        ('Status e Prazos', {
            'fields': ('status', 'data_abertura', 'data_vencimento', 'data_conclusao')
        }),
        ('Responsáveis', {
            'fields': ('criado_por', 'responsavel')
        }),
        ('Detalhes Adicionais', {
            'fields': ('meta', 'resultado', 'observacoes', 'link_registro'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('ativo',)
        }),
    )


class AcaoComentarioAdmin(admin.ModelAdmin):
    list_display = ['acao', 'autor', 'data_criacao']
    list_filter = ['data_criacao']
    search_fields = ['acao__titulo', 'autor__nome_completo']
    readonly_fields = ['data_criacao']


admin_site.register(AcaoCorretiva, AcaoCorretivaAdmin)
admin_site.register(AcaoComentario, AcaoComentarioAdmin)
