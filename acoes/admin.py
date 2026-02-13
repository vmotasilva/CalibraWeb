from django.contrib import admin
from .models import (
    AcaoCorretiva, 
    AcaoComentario,
    TemplateSolucao,
    Solucao,
    PlanoAcao,
    LinhaAcao,
    SolucaoA3,
    Solucao8D,
    SolucaoRNC,
    SolucaoGestaoDeMudanca,
    RevisaoGerencial,
    KPIOpcao
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
    list_display = ('numero_acao', 'descricao', 'status', 'responsavel_acao', 'data_deadline')
    list_filter = ('status', 'prioridade', 'classificacao', 'data_deadline')
    search_fields = ('numero_acao', 'descricao', 'problema', 'responsavel_acao__nome_completo')
    readonly_fields = ('criado_em', 'atualizado_em')
    
    fieldsets = (
        ('Identificação', {
            'fields': ('solucao', 'numero_acao', 'numero_registro', 'laboratorio_area_projeto')
        }),
        ('Informações da Ação', {
            'fields': ('input_origem', 'problema', 'laboratorio', 'kpi', 'descricao', 'classificacao')
        }),
        ('Status e Prazos', {
            'fields': ('status', 'prioridade', 'data_primeira_deadline', 'data_deadline', 'data_conclusao')
        }),
        ('Responsabilidades', {
            'fields': ('responsavel_acao',)
        }),
        ('Eficácia', {
            'fields': ('acao_eficaz', 'resultado', 'comentarios')
        }),
        ('Sistema', {
            'fields': ('criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )


class LinhaAcaoAdmin(admin.ModelAdmin):
    list_display = ('plano_acao', 'numero_acao', 'descricao', 'status', 'responsavel_acao', 'data_deadline')
    list_filter = ('status', 'prioridade', 'classificacao', 'data_deadline')
    search_fields = ('numero_acao', 'descricao', 'problema', 'responsavel_acao__nome_completo')
    readonly_fields = ('criado_em', 'atualizado_em')
    
    fieldsets = (
        ('Identificação', {
            'fields': ('plano_acao', 'numero_acao')
        }),
        ('Informações da Ação', {
            'fields': ('input_origem', 'problema', 'kpi', 'descricao', 'classificacao')
        }),
        ('Status e Prazos', {
            'fields': ('status', 'prioridade', 'data_primeira_deadline', 'data_deadline', 'data_conclusao')
        }),
        ('Responsabilidades', {
            'fields': ('responsavel_acao', 'responsaveis_multiplos')
        }),
        ('Eficácia', {
            'fields': ('acao_eficaz', 'comentarios')
        }),
        ('Sistema', {
            'fields': ('criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )



class SolucaoA3Admin(admin.ModelAdmin):
    list_display = ('a3_numero', 'laboratorio', 'lider_projeto', 'data_criacao')
    list_filter = ('data_criacao', 'laboratorio')
    search_fields = ('a3_numero', 'problema', 'laboratorio')
    date_hierarchy = 'data_criacao'
    
    fieldsets = (
        ('Relacionamento', {
            'fields': ('solucao',)
        }),
        ('Identificação', {
            'fields': ('a3_numero', 'data_criacao', 'laboratorio', 'lider_projeto', 'participantes')
        }),
        ('Problema', {
            'fields': ('problema', 'historico_importancia', 'observacoes_importantes')
        }),
        ('Ferramentas de Qualidade Utilizadas', {
            'fields': (
                'ferramenta_fluxograma',
                'ferramenta_brainstorming',
                'ferramenta_ishikawa',
                'ferramenta_5_porques',
                'ferramenta_grafico_pareto',
                'ferramenta_checklist',
                'ferramenta_grafico_geral',
                'ferramenta_carta_tendencia',
                'ferramenta_antes_depois',
            ),
            'classes': ('collapse',)
        }),
        ('A.ANALISAR', {
            'fields': ('analise_causas', 'causa_raiz'),
            'classes': ('collapse',)
        }),
        ('D.DEFINIR', {
            'fields': ('objetivo',)
        }),
        ('I.IMPLEMENTAR (Plano de Ação)', {
            'fields': ('plano_acao_relacionado',)
        }),
        ('M.MEDIR', {
            'fields': ('estado_atual',),
            'classes': ('collapse',)
        }),
        ('C.CONTROLE', {
            'fields': ('resultados',),
            'classes': ('collapse',)
        }),
        ('Métricas', {
            'fields': (
                'total_acoes_planejadas',
                'total_acoes_completas',
                'total_acoes_andamento',
                'total_acoes_prioridade_andamento',
            ),
            'classes': ('collapse',)
        }),
        ('Rastreamento', {
            'fields': ('criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('criado_em', 'atualizado_em')


class Solucao8DAdmin(admin.ModelAdmin):
    list_display = ('numero_formulario', 'lider_8d', 'departamento', 'data_abertura', 'prazo_projeto')
    list_filter = ('data_abertura', 'departamento', 'lider_8d')
    search_fields = ('numero_formulario', 'problema_identificado', 'lider_8d__nome_completo', 'equipe')
    readonly_fields = ('criado_em', 'atualizado_em')
    
    fieldsets = (
        ('Identificação', {
            'fields': ('solucao', 'numero_formulario', 'data_abertura', 'prazo_projeto')
        }),
        ('D1 - Formação da Equipe', {
            'fields': ('lider_8d', 'patrocinador', 'equipe', 'departamento', 'problema_identificado')
        }),
        ('D2 - Descrever o Problema', {
            'fields': ('d2_descricao', 'd2_especificacoes')
        }),
        ('D3 - Conter o Problema', {
            'fields': ('d3_contencao', 'd3_responsavel', 'd3_deadline')
        }),
        ('D4 - Análise de Causa Raiz', {
            'fields': ('d4_analise_causas', 'd4_ferramentas_qualidade', 'd4_causa_raiz')
        }),
        ('D5 - Desenvolvimento de Contramedidas', {
            'fields': ('d5_contramedidas', 'd5_criterios_selecao')
        }),
        ('D6 - Implementação de Contramedidas', {
            'fields': ('d6_implementacao', 'd6_responsavel', 'd6_deadline', 'd6_status')
        }),
        ('D7 - Verificação de Efetividade', {
            'fields': ('d7_verificacao', 'd7_resultado', 'd7_efetivo')
        }),
        ('D8 - Padronização e Fechamento', {
            'fields': ('d8_padronizacao', 'd8_documentos_atualizados', 'd8_treinamento', 'd8_encerramento')
        }),
        ('Análise Geral', {
            'fields': ('analise_causas', 'causa_raiz'),
            'classes': ('collapse',)
        }),
        ('Sistema', {
            'fields': ('criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )


class SolucaoRNCAdmin(admin.ModelAdmin):
    list_display = ('numero_rnc', 'classificacao', 'origem', 'risco', 'data_abertura')
    list_filter = ('classificacao', 'risco', 'frequencia', 'data_abertura')
    search_fields = ('numero_rnc', 'descricao_nc', 'causa_raiz', 'unidade')
    readonly_fields = ('criado_em', 'atualizado_em')
    
    fieldsets = (
        ('Identificação', {
            'fields': ('solucao', 'numero_rnc', 'unidade', 'data_abertura')
        }),
        ('Classificação', {
            'fields': ('origem', 'classificacao', 'requerimento_requisito')
        }),
        ('Não Conformidade', {
            'fields': ('descricao_nc', 'evidencia_nc')
        }),
        ('Gerenciamento de Risco', {
            'fields': ('frequencia', 'risco')
        }),
        ('Tratativas', {
            'fields': ('causa_raiz', 'acao_contencao', 'acao_nc', 'gerar_plano_acao', 'plano_acao_relacionado')
        }),
        ('Ações Associadas', {
            'fields': ('acao_imediata', 'acao_corretiva', 'acao_preventiva')
        }),
        ('Análise', {
            'fields': ('analise_causas', 'plano_verificacao', 'resultado')
        }),
        ('Conclusão', {
            'fields': ('eficacia', 'evidencia_implementacao', 'responsavel', 'data_fechamento')
        }),
        ('Sistema', {
            'fields': ('criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )


class SolucaoGestaoDeMudancaAdmin(admin.ModelAdmin):
    list_display = ('numero_registro', 'tipo_mudanca', 'prioridade_mudanca', 'status', 'data_abertura')
    list_filter = ('status', 'tipo_mudanca', 'prioridade_mudanca', 'data_abertura')
    search_fields = ('numero_registro', 'descricao', 'unidade', 'solicitante')
    readonly_fields = ('criado_em', 'atualizado_em')
    
    fieldsets = (
        ('Identificação', {
            'fields': ('solucao', 'numero_registro', 'unidade', 'solicitante', 'data_abertura')
        }),
        ('Classificação', {
            'fields': ('tipo_mudanca', 'prioridade_mudanca', 'area_impactada', 'area_avaliadora')
        }),
        ('Dados da Mudança', {
            'fields': ('situacao_antes', 'situacao_depois', 'justificativa', 'beneficios', 'data_mudanca', 'evidencia')
        }),
        ('Impactos de EHS', {
            'fields': (
                'impacto_pessoas', 'referencia_pessoas',
                'impacto_ambiente', 'referencia_ambiente',
                'impacto_ativos', 'referencia_ativos',
                'impacto_compliance', 'referencia_compliance'
            )
        }),
        ('Riscos Envolvidos', {
            'fields': (
                'processos_afetados', 'modulos_sistema_afetados',
                'como_afeta_processo', 'consequencia_nao_mudanca',
                'riscos_identificados', 'tratamento_riscos',
                'plano_contingencia', 'areas_implantacao', 'observacoes'
            )
        }),
        ('Plano de Ação', {
            'fields': ('gerar_plano_acao', 'plano_acao_relacionado', 'percentual_conclusao_plano')
        }),
        ('Análise Crítica pelas Áreas', {
            'fields': (
                'sera_implantada',
                'justificativa_area1', 'responsavel_decisao_area1', 'data_area1',
                'justificativa_area2', 'responsavel_decisao_area2', 'data_area2',
                'solicitante_informado', 'data_informada'
            )
        }),
        ('Status e Validação', {
            'fields': ('status', 'plano_validacao', 'resultado_validacao')
        }),
        ('Sistema', {
            'fields': ('criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )


class RevisaoGerencialAdmin(admin.ModelAdmin):
    list_display = ('numero_rg', 'laboratorio', 'data_realizacao', 'status')
    list_filter = ('status', 'data_realizacao', 'laboratorio')
    search_fields = ('numero_rg', 'laboratorio', 'representante_direcao', 'responsavel_unidade')
    date_hierarchy = 'data_realizacao'
    readonly_fields = ('criado_em', 'atualizado_em')
    
    fieldsets = (
        ('Relacionamento', {
            'fields': ('solucao',)
        }),
        ('Identificação', {
            'fields': ('numero_rg', 'data_realizacao', 'laboratorio', 'periodo_inicio', 'periodo_fim', 'status')
        }),
        ('Participantes', {
            'fields': ('representante_direcao', 'responsavel_unidade', 'participantes'),
            'classes': ('collapse',)
        }),
        ('Entradas', {
            'fields': (
                'entradas_acompanhamento',
                'entradas_auditorias',
                'entradas_satisfacao',
                'entradas_desempenho',
                'entradas_pessoal',
                'entradas_fornecedores',
                'entradas_mudancas',
                'entradas_risco',
                'entradas_oportunidades',
            ),
            'classes': ('collapse',)
        }),
        ('Saídas', {
            'fields': (
                'saidas_eficacia_sgq',
                'saidas_melhoria_produto',
                'saidas_necessidades_cliente',
                'saidas_necessidade_recurso',
            ),
            'classes': ('collapse',)
        }),
        ('Análises Críticas', {
            'fields': ('analises_criticas',)
        }),
        ('Plano de Ação Relacionado', {
            'fields': ('plano_acao_relacionado',)
        }),
        ('Métricas', {
            'fields': (
                'total_acoes_planejadas',
                'total_acoes_completas',
                'total_acoes_andamento',
                'total_acoes_prioridade_andamento',
                'percentual_conclusao',
            ),
            'classes': ('collapse',)
        }),
        ('Rastreamento', {
            'fields': ('criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )


class KPIOpcaoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'codigo', 'ativo', 'criado_em')
    list_filter = ('ativo', 'criado_em')
    search_fields = ('nome', 'codigo', 'descricao')
    readonly_fields = ('criado_em', 'atualizado_em')
    
    fieldsets = (
        (None, {
            'fields': ('nome', 'codigo', 'descricao', 'ativo')
        }),
        ('Rastreamento', {
            'fields': ('criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )


# Registrando no admin padrão do Django
admin_site.register(AcaoCorretiva, AcaoCorretivaAdmin)
admin_site.register(AcaoComentario, AcaoComentarioAdmin)
admin_site.register(Solucao, SolucaoAdmin)
admin_site.register(PlanoAcao, PlanoAcaoAdmin)
admin_site.register(LinhaAcao, LinhaAcaoAdmin)
admin_site.register(SolucaoA3, SolucaoA3Admin)
admin_site.register(Solucao8D, Solucao8DAdmin)
admin_site.register(SolucaoRNC, SolucaoRNCAdmin)
admin_site.register(SolucaoGestaoDeMudanca, SolucaoGestaoDeMudancaAdmin)
admin_site.register(RevisaoGerencial, RevisaoGerencialAdmin)
admin_site.register(KPIOpcao, KPIOpcaoAdmin)


@admin.register(TemplateSolucao)
class TemplateSolucaoAdmin(admin.ModelAdmin):
    list_display = ('get_tipo_display', 'descricao', 'data_upload', 'arquivo_pdf', 'ativo')
    list_filter = ('tipo', 'ativo', 'data_upload')
    search_fields = ('descricao', 'tipo')
    readonly_fields = ('data_upload',)
    
    fieldsets = (
        ('Informações', {
            'fields': ('tipo', 'descricao')
        }),
        ('Arquivo', {
            'fields': ('arquivo_pdf', 'data_upload')
        }),
        ('Status', {
            'fields': ('ativo',)
        }),
    )
    
    def get_tipo_display(self, obj):
        return obj.get_tipo_display()
    get_tipo_display.short_description = "Tipo de Solução"
