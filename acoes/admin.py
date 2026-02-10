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
    list_display = ['titulo', 'tipo', 'status', 'prioridade', 'responsavel', 'data_vencimento', 'esta_vencida']
    list_filter = ['tipo', 'status', 'prioridade', 'data_criacao']
    search_fields = ['titulo', 'descricao', 'responsavel__nome_completo']
    readonly_fields = ['data_criacao']
    inlines = [AcaoComentarioInline]
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('titulo', 'descricao', 'tipo', 'prioridade', 'origem')
        }),
        ('Status e Prazos', {
            'fields': ('status', 'data_criacao', 'data_vencimento', 'data_conclusao')
        }),
        ('Responsáveis', {
            'fields': ('criado_por', 'responsavel')
        }),
        ('Detalhes Adicionais', {
            'fields': ('meta', 'resultado', 'observacoes'),
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
