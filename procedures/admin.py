# -*- coding: utf-8 -*-
"""
Admin para o módulo Procedures
Consolida admin de training e procurements
"""

from django.contrib import admin
from django import forms
from django.forms.models import BaseInlineFormSet
from .models import (
    Area, Procedimento, ProcedimentoRevisao, PacoteTreinamento, RegistroTreinamento,
    MatrizProcedimento, SubAreaProcedimento,
    Disciplina, DisciplinaProcedimento, PlanejamentoTreinamento, ListaPresenca,
    TemplateListaPresenca, MapeamentoCampoListaPresenca,
    Fornecedor, AvaliacaoFornecedor, ProcessoCotacao, Orcamento
)
from qms.admin import admin_site


# ==============================================================================
# FORMS E VALIDAÇÕES CUSTOMIZADAS
# ==============================================================================

class MapeamentoFormSet(BaseInlineFormSet):
    """FormSet customizado para validar placeholders duplicados"""
    
    def clean(self):
        super().clean()
        
        if self.forms:
            # Verificar placeholders duplicados
            placeholders_vistos = set()
            
            for form in self.forms:
                if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                    placeholder = form.cleaned_data.get('placeholder', '').strip()
                    
                    # Ignorar linhas vazias
                    if not placeholder:
                        continue
                    
                    if placeholder in placeholders_vistos:
                        raise forms.ValidationError(
                            f"O placeholder '{placeholder}' foi adicionado mais de uma vez. "
                            "Cada placeholder deve ser único no template."
                        )
                    placeholders_vistos.add(placeholder)


# ==============================================================================
# PROCEDIMENTOS E TREINAMENTOS
# ==============================================================================

class AreaAdmin(admin.ModelAdmin):
    list_display = ['nome']
    search_fields = ['nome']
    ordering = ['nome']


class ProcedimentoAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nome', 'numero_revisao', 'ultima_revisao']
    search_fields = ['codigo', 'nome']
    list_filter = ['ultima_revisao']
    ordering = ['codigo']


class MatrizProcedimentoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'ativo', 'criado_em']
    search_fields = ['nome']
    list_filter = ['ativo']
    ordering = ['nome']


class SubAreaProcedimentoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'matriz', 'ativo', 'criado_em']
    search_fields = ['nome', 'matriz__nome']
    list_filter = ['ativo', 'matriz']
    list_select_related = ['matriz']
    ordering = ['matriz__nome', 'nome']


class ProcedimentoRevisaoAdmin(admin.ModelAdmin):
    list_display = ['procedimento', 'revisao', 'data_revisao']
    search_fields = ['procedimento__nome']
    list_filter = ['data_revisao']
    list_select_related = ['procedimento', 'elaborador', 'revisor', 'aprovador']
    ordering = ['-data_revisao']


class PacoteTreinamentoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'descricao']
    search_fields = ['nome', 'descricao']
    filter_horizontal = ['procedimentos']
    list_prefetch_related = ['procedimentos']
    ordering = ['nome']


class RegistroTreinamentoAdmin(admin.ModelAdmin):
    list_display = ['colaborador', 'procedimento', 'data_treinamento', 'ativo']
    search_fields = ['colaborador__nome_completo', 'procedimento__nome']
    list_filter = ['data_treinamento', 'ativo']
    list_select_related = ['colaborador', 'procedimento', 'revisor_qualidade']
    ordering = ['-data_treinamento']
    fields = ['colaborador', 'procedimento', 'revisor_qualidade', 'revisao_treinada', 'data_treinamento', 'validade_treinamento', 'ativo', 'observacoes']


class DisciplinaAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nome', 'matriz', 'obrigatoriedade_legal', 'ativo']
    search_fields = ['codigo', 'nome']
    list_filter = ['matriz', 'obrigatoriedade_legal', 'ativo']
    list_select_related = ['matriz']
    ordering = ['codigo']


class DisciplinaProcedimentoAdmin(admin.ModelAdmin):
    list_display = ['disciplina', 'procedimento', 'obrigatorio', 'ordem']
    search_fields = ['disciplina__nome', 'procedimento__nome']
    list_filter = ['obrigatorio']
    list_select_related = ['disciplina', 'procedimento']
    ordering = ['disciplina', 'ordem']


class PlanejamentoTreinamentoAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'origem', 'data_prevista', 'horario_previsto', 'status']
    search_fields = ['titulo', 'observacoes']
    list_filter = ['origem', 'status', 'data_prevista']
    list_select_related = ['disciplina', 'instrutor']
    filter_horizontal = ['colaboradores', 'procedimentos']
    fieldsets = (
        ('Identificação', {
            'fields': ('titulo', 'origem')
        }),
        ('Relacionamentos', {
            'fields': ('procedimentos', 'disciplina'),
            'description': 'Preenchimento conforme tipo de origem'
        }),
        ('Participantes', {
            'fields': ('colaboradores', 'instrutor')
        }),
        ('Execução', {
            'fields': ('data_prevista', 'horario_previsto', 'data_realizada', 'carga_horaria', 'local')
        }),
        ('Status e Observações', {
            'fields': ('status', 'observacoes')
        }),
    )
    readonly_fields = ['criado_em', 'atualizado_em']
    ordering = ['-data_prevista']


# ==============================================================================
# FORNECEDORES E COTAÇÕES
# ==============================================================================

class FornecedorAdmin(admin.ModelAdmin):
    list_display = ['nome_fantasia', 'contato', 'email', 'telefone', 'status']
    search_fields = ['nome_fantasia', 'contato', 'email']
    list_filter = ['status']
    ordering = ['nome_fantasia']


class AvaliacaoFornecedorAdmin(admin.ModelAdmin):
    list_display = ['fornecedor', 'data_avaliacao', 'nota_tecnica']
    search_fields = ['fornecedor__nome_fantasia']
    list_filter = ['data_avaliacao']
    list_select_related = ['fornecedor', 'avaliador']
    ordering = ['-data_avaliacao']


class ProcessoCotacaoAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'data_abertura', 'prazo_limite', 'status']
    search_fields = ['titulo']
    list_filter = ['status']
    list_select_related = ['responsavel']
    list_prefetch_related = ['instrumentos']
    ordering = ['-data_abertura']


class OrcamentoAdmin(admin.ModelAdmin):
    list_display = ['processo', 'fornecedor', 'valor_total', 'prazo_execucao_dias']
    search_fields = ['processo__titulo', 'fornecedor__nome_fantasia']
    list_filter = ['processo']
    list_select_related = ['processo', 'fornecedor']
    ordering = ['-processo']


# ==============================================================================
# LISTAS DE PRESENÇA E TEMPLATES
# ==============================================================================

class ListaPresencaAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'titulo', 'data_sessao', 'instrutor', 'local']
    search_fields = ['codigo', 'titulo', 'instrutor_nome']
    list_filter = ['data_sessao', 'local']
    list_select_related = ['instrutor', 'criado_por']
    readonly_fields = ['codigo', 'criado_em', 'atualizado_em']
    ordering = ['-data_sessao', '-codigo']


class MapeamentoCampoListaPresencaInline(admin.TabularInline):
    model = MapeamentoCampoListaPresenca
    extra = 0
    fields = ['placeholder', 'campo_dados', 'formato', 'obrigatorio']
    readonly_fields = ['placeholder']
    ordering = ['placeholder']
    formset = MapeamentoFormSet


class TemplateListaPresencaAdmin(admin.ModelAdmin):
    list_display = ['nome', 'tipo_arquivo', 'tem_pagina_assinatura', 'mapeamento_completo', 'ativo']
    search_fields = ['nome', 'descricao']
    list_filter = ['tipo_arquivo', 'ativo', 'tem_pagina_assinatura', 'mapeamento_completo']
    readonly_fields = ['criado_em', 'atualizado_em', 'mapeamento_completo', 'placeholders_mapeados']
    inlines = [MapeamentoCampoListaPresencaInline]
    
    fieldsets = (
        ('Identificação', {
            'fields': ('nome', 'descricao', 'ativo')
        }),
        ('Arquivo PDF Template', {
            'fields': ('tipo_arquivo', 'arquivo_pdf_template'),
            'description': 'Upload do PDF base com placeholders como {{titulo}}, {{data}}, {{facilitador}}, etc.'
        }),
        ('Mapeamento de Placeholders', {
            'fields': ('mapeamento_completo', 'placeholders_mapeados'),
            'description': 'Placeholders detectados e configurados no template',
            'classes': ('collapse',)
        }),
        ('Configuração de Página de Assinatura', {
            'fields': ('tem_pagina_assinatura', 'num_linhas_assinatura')
        }),
        ('Metadados', {
            'fields': ('criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )
    
    change_form_template = 'admin/procedures/templatelistapresenca_change_form.html'
    
    def get_urls(self):
        """Adiciona URLs customizadas para mapeamento de placeholders"""
        from django.urls import path
        from importlib import import_module
        
        # Importação dinâmica para evitar circular imports
        template_mapeamento_views = import_module('procedures.views.template_mapeamento_views')
        mapear_placeholders_view = template_mapeamento_views.mapear_placeholders_view
        
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:pk>/mapear-placeholders/',
                self.admin_site.admin_view(mapear_placeholders_view),
                name='procedures_templatelistapresenca_mapear_placeholders',
            ),
        ]
        return custom_urls + urls
    
    ordering = ['-ativo', '-atualizado_em']



# ==============================================================================
# REGISTRO NO ADMIN
# ==============================================================================

# Procedimentos e Treinamentos
admin_site.register(Area, AreaAdmin)
admin_site.register(Procedimento, ProcedimentoAdmin)
admin_site.register(MatrizProcedimento, MatrizProcedimentoAdmin)
admin_site.register(SubAreaProcedimento, SubAreaProcedimentoAdmin)
admin_site.register(ProcedimentoRevisao, ProcedimentoRevisaoAdmin)
admin_site.register(PacoteTreinamento, PacoteTreinamentoAdmin)
admin_site.register(RegistroTreinamento, RegistroTreinamentoAdmin)
admin_site.register(Disciplina, DisciplinaAdmin)
admin_site.register(DisciplinaProcedimento, DisciplinaProcedimentoAdmin)
admin_site.register(PlanejamentoTreinamento, PlanejamentoTreinamentoAdmin)
admin_site.register(ListaPresenca, ListaPresencaAdmin)
admin_site.register(TemplateListaPresenca, TemplateListaPresencaAdmin)

# Fornecedores e Cotações
admin_site.register(Fornecedor, FornecedorAdmin)
admin_site.register(AvaliacaoFornecedor, AvaliacaoFornecedorAdmin)
admin_site.register(ProcessoCotacao, ProcessoCotacaoAdmin)
admin_site.register(Orcamento, OrcamentoAdmin)
