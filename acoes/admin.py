from django.contrib import admin
from .models import (
    AcaoCorretiva, 
    AcaoComentario,
    Solucao,
    PlanoAcao,
    SolucaoA3,
    Solucao8D,
    SolucaoRNC,
    SolucaoGestaoDeMudanca,
    RevisaoGerencial
)
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


class SolucaoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'get_tipo_display', 'acao_corretiva', 'status', 'responsavel', 'data_criacao')
    list_filter = ('tipo', 'status', 'data_criacao')
    search_fields = ('titulo', 'descricao', 'acao_corretiva__numero_registro')
    
    fieldsets = (
        ('Relacionamento', {
            'fields': ('acao_corretiva',)
        }),
        ('Informações Básicas', {
            'fields': ('tipo', 'titulo', 'descricao', 'status')
        }),
        ('Datas', {
            'fields': ('data_inicio', 'data_conclusao')
        }),
        ('Responsáveis', {
            'fields': ('responsavel',)
        }),
        ('Status', {
            'fields': ('ativo',)
        }),
    )
    readonly_fields = ('data_criacao',)


class PlanoAcaoAdmin(admin.ModelAdmin):
    list_display = ('solucao', 'responsavel_acao', 'status', 'data_inicio', 'data_conclusao')
    list_filter = ('status', 'data_conclusao')
    search_fields = ('solucao__titulo', 'acao_proposta')
    
    fieldsets = (
        ('Relacionamento', {
            'fields': ('solucao',)
        }),
        ('Ação', {
            'fields': ('acao_proposta', 'responsavel_acao')
        }),
        ('Datas', {
            'fields': ('data_inicio', 'data_conclusao')
        }),
        ('Acompanhamento', {
            'fields': ('status', 'resultado')
        }),
    )


class SolucaoA3Admin(admin.ModelAdmin):
    list_display = ('solucao', 'get_tipo_display')
    search_fields = ('solucao__titulo', 'problema_descricao', 'causa_raiz')
    
    fieldsets = (
        ('Relacionamento', {
            'fields': ('solucao',)
        }),
        ('Problema', {
            'fields': ('problema_descricao', 'problema_impacto')
        }),
        ('Situação', {
            'fields': ('situacao_atual',)
        }),
        ('Análise', {
            'fields': ('analise_causas', 'causa_raiz')
        }),
        ('Solução', {
            'fields': ('contramedidas', 'resultados_esperados')
        }),
        ('Verificação', {
            'fields': ('plano_verificacao', 'resultado_verificacao')
        }),
    )
    
    def get_tipo_display(self, obj):
        return "A3"


class Solucao8DAdmin(admin.ModelAdmin):
    list_display = ('solucao', 'get_tipo_display')
    search_fields = ('solucao__titulo', 'd2_descricao', 'd4_causa_raiz')
    
    fieldsets = (
        ('Relacionamento', {
            'fields': ('solucao',)
        }),
        ('D1 - Time', {
            'fields': ('d1_time',)
        }),
        ('D2 - Problema', {
            'fields': ('d2_descricao', 'd2_especificacoes')
        }),
        ('D3 - Contenção', {
            'fields': ('d3_contencao',)
        }),
        ('D4 - Causa Raiz', {
            'fields': ('d4_causas', 'd4_causa_raiz')
        }),
        ('D5 - Contramedidas', {
            'fields': ('d5_contramedidas',)
        }),
        ('D6 - Implementação', {
            'fields': ('d6_implementacao',)
        }),
        ('D7 - Verificação', {
            'fields': ('d7_verificacao', 'd7_resultado')
        }),
        ('D8 - Padronização', {
            'fields': ('d8_padronizacao', 'd8_encerramento')
        }),
    )
    
    def get_tipo_display(self, obj):
        return "8D"


class SolucaoRNCAdmin(admin.ModelAdmin):
    list_display = ('solucao', 'nc_tipo', 'get_tipo_display')
    list_filter = ('nc_tipo',)
    search_fields = ('solucao__titulo', 'nc_descricao', 'causa_raiz')
    
    fieldsets = (
        ('Relacionamento', {
            'fields': ('solucao',)
        }),
        ('Não Conformidade', {
            'fields': ('nc_descricao', 'nc_tipo')
        }),
        ('Análise', {
            'fields': ('analise_causas', 'causa_raiz')
        }),
        ('Ações', {
            'fields': ('acao_imediata', 'acao_corretiva', 'acao_preventiva')
        }),
        ('Verificação', {
            'fields': ('plano_verificacao', 'resultado')
        }),
    )
    
    def get_tipo_display(self, obj):
        return "RNC"


class SolucaoGestaoDeMudancaAdmin(admin.ModelAdmin):
    list_display = ('solucao', 'status', 'data_implementacao', 'get_tipo_display')
    list_filter = ('status', 'data_implementacao')
    search_fields = ('solucao__titulo', 'mudanca_descricao', 'motivacao')
    
    fieldsets = (
        ('Relacionamento', {
            'fields': ('solucao',)
        }),
        ('Mudança', {
            'fields': ('mudanca_descricao', 'motivacao')
        }),
        ('Impacto', {
            'fields': ('impacto_processos', 'impacto_sistemas', 'impacto_pessoas')
        }),
        ('Implementação', {
            'fields': ('plano_implementacao', 'data_implementacao')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Validação', {
            'fields': ('plano_validacao', 'resultado_validacao')
        }),
    )
    
    def get_tipo_display(self, obj):
        return "Gestão de Mudança"


class RevisaoGerencialAdmin(admin.ModelAdmin):
    list_display = ('solucao', 'prioridade_implementacao', 'data_alvo_implementacao', 'get_tipo_display')
    list_filter = ('prioridade_implementacao', 'data_alvo_implementacao')
    search_fields = ('solucao__titulo', 'revisao_descricao', 'recomendacoes')
    
    fieldsets = (
        ('Relacionamento', {
            'fields': ('solucao',)
        }),
        ('Revisão', {
            'fields': ('revisao_descricao', 'escopo')
        }),
        ('Achados', {
            'fields': ('achados_principais', 'oportunidades_melhoria')
        }),
        ('Recomendações', {
            'fields': ('recomendacoes', 'prioridade_implementacao')
        }),
        ('Plano de Ação', {
            'fields': ('plano_acao', 'responsavel_implementacao', 'data_alvo_implementacao')
        }),
        ('Acompanhamento', {
            'fields': ('resultado', 'data_conclusao')
        }),
    )
    
    def get_tipo_display(self, obj):
        return "Revisão Gerencial"


# Registrando no admin padrão do Django
admin_site.register(AcaoCorretiva, AcaoCorretivaAdmin)
admin_site.register(AcaoComentario, AcaoComentarioAdmin)
admin_site.register(Solucao, SolucaoAdmin)
admin_site.register(PlanoAcao, PlanoAcaoAdmin)
admin_site.register(SolucaoA3, SolucaoA3Admin)
admin_site.register(Solucao8D, Solucao8DAdmin)
admin_site.register(SolucaoRNC, SolucaoRNCAdmin)
admin_site.register(SolucaoGestaoDeMudanca, SolucaoGestaoDeMudancaAdmin)
admin_site.register(RevisaoGerencial, RevisaoGerencialAdmin)
