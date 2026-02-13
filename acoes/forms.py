"""
Django Forms para os modelos de Soluções
Inclui ModelForms para todos os 6 tipos de soluções com validações e widgets customizados
"""

from django import forms
from django.forms import ModelForm, inlineformset_factory
from django.utils.translation import gettext_lazy as _
from .models import (
    PlanoAcao, SolucaoA3, Solucao8D, SolucaoRNC,
    SolucaoGestaoDeMudanca, RevisaoGerencial,
    AcaoCorretiva, AcaoComentario, LinhaAcao
)
from rh.models import Colaborador


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def criar_numero_registro():
    """Gera número de registro no formato ANO-SEQUENCIAL"""
    from datetime import datetime
    ano = datetime.now().year
    # TODO: Implementar sequencial por tipo
    return f"{ano}-0001"


def validar_datas_prazo(data_inicio, data_fim):
    """Valida se data_fim é posterior a data_inicio"""
    if data_inicio and data_fim and data_fim < data_inicio:
        raise forms.ValidationError(
            _("A data final deve ser posterior à data inicial.")
        )


# ============================================================================
# PLANO DE AÇÃO FORM
# ============================================================================

class PlanoAcaoForm(ModelForm):
    """Form para criação/edição de Plano de Ação"""
    
    class Meta:
        model = PlanoAcao
        fields = [
            'laboratorio_area_projeto',
            'numero_acao',
            'input_origem',
            'problema',
            'laboratorio',
            'kpi',
            'descricao',
            'classificacao',
            'status',
            'prioridade',
            'responsavel_acao',
            'responsaveis_multiplos',
            'data_primeira_deadline',
            'data_deadline',
            'comentarios',
            'acao_eficaz',
            'resultado',
            'data_conclusao',
        ]
        widgets = {
            'laboratorio_area_projeto': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Laboratório, Área ou Projeto'
            }),
            'numero_acao': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Número da Ação'
            }),
            'input_origem': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Input/Origem'
            }),
            'problema': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descreva o problema identificado'
            }),
            'laboratorio': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Laboratório'
            }),
            'kpi': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'KPI associado'
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descrição detalhada'
            }),
            'classificacao': forms.Select(attrs={
                'class': 'form-control'
            }),
            'status': forms.Select(attrs={
                'class': 'form-control'
            }),
            'prioridade': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'responsavel_acao': forms.Select(attrs={
                'class': 'form-control'
            }),
            'responsaveis_multiplos': forms.CheckboxSelectMultiple(attrs={
                'class': 'form-check-input'
            }),
            'data_primeira_deadline': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'data_deadline': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'comentarios': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Comentários adicionais'
            }),
            'acao_eficaz': forms.Select(attrs={
                'class': 'form-control'
            }),
            'resultado': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Resultado obtido'
            }),
            'data_conclusao': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        data_inicio = cleaned_data.get('data_primeira_deadline')
        data_fim = cleaned_data.get('data_deadline')
        if data_inicio and data_fim:
            validar_datas_prazo(data_inicio, data_fim)
        return cleaned_data


# ============================================================================
# SOLUÇÃO A3 FORM
# ============================================================================

class SolucaoA3Form(ModelForm):
    """Form para criação/edição de Solução A3"""
    
    class Meta:
        model = SolucaoA3
        fields = [
            'a3_numero',
            'data_criacao',
            'laboratorio',
            'lider_projeto',
            'participantes',
            'problema',
            'historico_importancia',
            'observacoes_importantes',
            'ferramenta_fluxograma',
            'ferramenta_brainstorming',
            'ferramenta_ishikawa',
            'ferramenta_5_porques',
            'ferramenta_grafico_pareto',
            'ferramenta_checklist',
            'ferramenta_grafico_geral',
            'ferramenta_carta_tendencia',
            'ferramenta_antes_depois',
            'analise_causas',
            'causa_raiz',
            'objetivo',
            'plano_acao_relacionado',
            'estado_atual',
            'resultados',
        ]
        widgets = {
            'a3_numero': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'A3 Nº'
            }),
            'data_criacao': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'laboratorio': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Laboratório'
            }),
            'lider_projeto': forms.Select(attrs={
                'class': 'form-control'
            }),
            'participantes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Lista de participantes'
            }),
            'problema': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descreva o problema'
            }),
            'historico_importancia': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Histórico e importância'
            }),
            'observacoes_importantes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Observações importantes'
            }),
            'ferramenta_fluxograma': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'ferramenta_brainstorming': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'ferramenta_ishikawa': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'ferramenta_5_porques': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'ferramenta_grafico_pareto': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'ferramenta_checklist': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'ferramenta_grafico_geral': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'ferramenta_carta_tendencia': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'ferramenta_antes_depois': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'analise_causas': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Análise de causas'
            }),
            'causa_raiz': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Causa raiz identificada'
            }),
            'objetivo': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Objetivo'
            }),
            'plano_acao_relacionado': forms.Select(attrs={
                'class': 'form-control'
            }),
            'estado_atual': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Estado atual (Antes)'
            }),
            'resultados': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Resultados (Controle)'
            }),
        }


# ============================================================================
# SOLUÇÃO 8D FORM
# ============================================================================

class Solucao8DForm(ModelForm):
    """Form para criação/edição de Solução 8D"""
    
    class Meta:
        model = Solucao8D
        fields = [
            'numero_formulario',
            'data_abertura',
            'lider_8d',
            'patrocinador',
            'equipe',
            'departamento',
            'problema_identificado',
            'prazo_projeto',
            'd2_descricao',
            'd2_especificacoes',
            'd3_contencao',
            'd3_responsavel',
            'd3_deadline',
            'd4_analise_causas',
            'd4_ferramentas_qualidade',
            'd4_causa_raiz',
            'd5_contramedidas',
            'd5_criterios_selecao',
            'd6_implementacao',
            'd6_responsavel',
            'd6_deadline',
            'd6_status',
            'd7_verificacao',
            'd7_resultado',
            'd7_efetivo',
            'd8_padronizacao',
            'd8_documentos_atualizados',
            'd8_treinamento',
            'd8_encerramento',
        ]
        widgets = {
            'numero_formulario': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Número do Formulário'
            }),
            'data_abertura': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'lider_8d': forms.Select(attrs={'class': 'form-control'}),
            'patrocinador': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Patrocinador'
            }),
            'equipe': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Membros da equipe'
            }),
            'departamento': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Departamento'
            }),
            'problema_identificado': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Problema Identificado'
            }),
            'prazo_projeto': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            # D2
            'd2_descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descrição do Problema'
            }),
            'd2_especificacoes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Especificações Afetadas'
            }),
            # D3
            'd3_contencao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Plano de Contenção'
            }),
            'd3_responsavel': forms.Select(attrs={'class': 'form-control'}),
            'd3_deadline': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            # D4
            'd4_analise_causas': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Análise de Causas'
            }),
            'd4_ferramentas_qualidade': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ferramentas utilizadas'
            }),
            'd4_causa_raiz': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Causa Raiz'
            }),
            # D5
            'd5_contramedidas': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Contramedidas Propostas'
            }),
            'd5_criterios_selecao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Critérios de Seleção'
            }),
            # D6
            'd6_implementacao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Plano de Implementação'
            }),
            'd6_responsavel': forms.Select(attrs={'class': 'form-control'}),
            'd6_deadline': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'd6_status': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Status de Implementação'
            }),
            # D7
            'd7_verificacao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Plano de Verificação'
            }),
            'd7_resultado': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Resultado da Verificação'
            }),
            'd7_efetivo': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            # D8
            'd8_padronizacao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Padronização'
            }),
            'd8_documentos_atualizados': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Documentos Atualizados'
            }),
            'd8_treinamento': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Plano de Treinamento'
            }),
            'd8_encerramento': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Encerramento'
            }),
        }


# ============================================================================
# SOLUÇÃO RNC FORM
# ============================================================================

class SolucaoRNCForm(ModelForm):
    """Form para criação/edição de Solução RNC"""
    
    class Meta:
        model = SolucaoRNC
        fields = [
            'unidade',
            'numero_rnc',
            'data_abertura',
            'origem',
            'classificacao',
            'requerimento_requisito',
            'descricao_nc',
            'evidencia_nc',
            'frequencia',
            'risco',
            'causa_raiz',
            'acao_contencao',
            'acao_nc',
            'gerar_plano_acao',
            'plano_acao_relacionado',
            'eficacia',
            'evidencia_implementacao',
            'responsavel',
            'data_fechamento',
            'analise_causas',
            'acao_imediata',
            'acao_corretiva',
            'acao_preventiva',
            'plano_verificacao',
            'resultado',
        ]
        widgets = {
            'unidade': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Unidade'
            }),
            'numero_rnc': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nº da RNC'
            }),
            'data_abertura': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'origem': forms.Select(attrs={'class': 'form-control'}),
            'classificacao': forms.Select(attrs={'class': 'form-control'}),
            'requerimento_requisito': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Requerimento/Requisito'
            }),
            'descricao_nc': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descrição da Não Conformidade'
            }),
            'evidencia_nc': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Evidência da Não Conformidade'
            }),
            'frequencia': forms.Select(attrs={'class': 'form-control'}),
            'risco': forms.Select(attrs={'class': 'form-control'}),
            'causa_raiz': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Causa Raiz'
            }),
            'acao_contencao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Ação de Contenção'
            }),
            'acao_nc': forms.Select(attrs={'class': 'form-control'}),
            'gerar_plano_acao': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'plano_acao_relacionado': forms.Select(attrs={
                'class': 'form-control'
            }),
            'eficacia': forms.Select(attrs={'class': 'form-control'}),
            'evidencia_implementacao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Evidência da Implementação'
            }),
            'responsavel': forms.Select(attrs={'class': 'form-control'}),
            'data_fechamento': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'analise_causas': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Análise de Causas'
            }),
            'acao_imediata': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Ação Imediata'
            }),
            'acao_corretiva': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Ação Corretiva'
            }),
            'acao_preventiva': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Ação Preventiva'
            }),
            'plano_verificacao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Plano de Verificação'
            }),
            'resultado': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Resultado'
            }),
        }


# ============================================================================
# SOLUÇÃO GESTÃO DE MUDANÇA FORM
# ============================================================================

class SolucaoGestaoDeMudancaForm(ModelForm):
    """Form para criação/edição de Solução Gestão de Mudança"""
    
    class Meta:
        model = SolucaoGestaoDeMudanca
        fields = [
            'unidade',
            'data_abertura',
            'solicitante',
            'numero_registro',
            'tipo_mudanca',
            'prioridade_mudanca',
            'area_impactada',
            'area_avaliadora',
            'situacao_antes',
            'situacao_depois',
            'justificativa',
            'beneficios',
            'data_mudanca',
            'evidencia',
            'impacto_pessoas',
            'referencia_pessoas',
            'impacto_ambiente',
            'referencia_ambiente',
            'impacto_ativos',
            'referencia_ativos',
            'impacto_compliance',
            'referencia_compliance',
            'processos_afetados',
            'plano_acao_relacionado',
            'status',
        ]
        widgets = {
            'unidade': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Unidade'
            }),
            'data_abertura': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'solicitante': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Solicitante'
            }),
            'numero_registro': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nº do Registro'
            }),
            'tipo_mudanca': forms.Select(attrs={'class': 'form-control'}),
            'prioridade_mudanca': forms.Select(attrs={'class': 'form-control'}),
            'area_impactada': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Área(s) Impactada(s)'
            }),
            'area_avaliadora': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Área Avaliadora (setores/departamentos)'
            }),
            'situacao_antes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Situação Atual (Antes da Mudança)'
            }),
            'situacao_depois': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Situação Projetada (Após Mudança)'
            }),
            'justificativa': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Justificativa'
            }),
            'beneficios': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Benefícios'
            }),
            'data_mudanca': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'evidencia': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Evidência (imagens e/ou informações antes da mudança)'
            }),
            'impacto_pessoas': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Saúde, Segurança Química/Elétrica, Ergonomia'
            }),
            'referencia_pessoas': forms.Select(attrs={'class': 'form-control'}),
            'impacto_ambiente': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Emissões, Resíduos, Energia'
            }),
            'referencia_ambiente': forms.Select(attrs={'class': 'form-control'}),
            'impacto_ativos': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Instalações, Equipamentos'
            }),
            'referencia_ativos': forms.Select(attrs={'class': 'form-control'}),
            'impacto_compliance': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Regulamentos'
            }),
            'referencia_compliance': forms.Select(attrs={'class': 'form-control'}),
            'processos_afetados': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Processos Afetados'
            }),
            'plano_acao_relacionado': forms.Select(attrs={
                'class': 'form-control'
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }


# ============================================================================
# REVISÃO GERENCIAL FORM
# ============================================================================

class RevisaoGerencialForm(ModelForm):
    """Form para criação/edição de Revisão Gerencial"""
    
    class Meta:
        model = RevisaoGerencial
        fields = [
            'numero_rg',
            'data_realizacao',
            'laboratorio',
            'periodo_inicio',
            'periodo_fim',
            'representante_direcao',
            'responsavel_unidade',
            'participantes',
            'entradas_acompanhamento',
            'entradas_auditorias',
            'entradas_satisfacao',
            'entradas_desempenho',
            'entradas_pessoal',
            'entradas_fornecedores',
            'entradas_mudancas',
            'entradas_risco',
            'entradas_oportunidades',
            'saidas_eficacia_sgq',
            'saidas_melhoria_produto',
            'saidas_necessidades_cliente',
            'saidas_necessidade_recurso',
            'analises_criticas',
            'plano_acao_relacionado',
            'status',
        ]
        widgets = {
            'numero_rg': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nº Registro'
            }),
            'data_realizacao': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'laboratorio': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Laboratório'
            }),
            'periodo_inicio': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Início do Período'
            }),
            'periodo_fim': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Fim do Período'
            }),
            'representante_direcao': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Representante da Direção'
            }),
            'responsavel_unidade': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Responsável pela Unidade'
            }),
            'participantes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Lista de participantes'
            }),
            # Entradas
            'entradas_acompanhamento': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Ações de acompanhamento de análises anteriores'
            }),
            'entradas_auditorias': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Resultados de auditorias'
            }),
            'entradas_satisfacao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Satisfação de clientes'
            }),
            'entradas_desempenho': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Desempenho de processos e conformidade'
            }),
            'entradas_pessoal': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Adequação de recursos (pessoal)'
            }),
            'entradas_fornecedores': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Desempenho de fornecedores'
            }),
            'entradas_mudancas': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Alterações e mudanças'
            }),
            'entradas_risco': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Avaliação de risco'
            }),
            'entradas_oportunidades': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Oportunidades de melhoria'
            }),
            # Saídas
            'saidas_eficacia_sgq': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Melhoria da eficácia do SGQ e de seus processos'
            }),
            'saidas_melhoria_produto': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Melhoria do produto em relação aos requisitos'
            }),
            'saidas_necessidades_cliente': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Atendimento de necessidades de partes interessadas'
            }),
            'saidas_necessidade_recurso': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Necessidade de recursos'
            }),
            'analises_criticas': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Análises Críticas Realizadas'
            }),
            'plano_acao_relacionado': forms.Select(attrs={
                'class': 'form-control'
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }


# ============================================================================
# LEGACY FORMS (Compatibilidade com código anterior)
# ============================================================================

class AcaoCorretivaForm(ModelForm):
    """Form para criação/edição de Ação Corretiva (Legacy)"""
    
    class Meta:
        model = AcaoCorretiva
        fields = [
            'numero_registro',
            'tipo',
            'unidade',
            'descricao',
            'status',
            'prioridade',
            'responsavel',
            'data_conclusao',
            'resultado',
        ]
        widgets = {
            'numero_registro': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'unidade': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'prioridade': forms.Select(attrs={'class': 'form-control'}),
            'responsavel': forms.Select(attrs={'class': 'form-control'}),
            'data_conclusao': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'resultado': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
        }


class AcaoCorretivaModalForm(ModelForm):
    """Form completo para criar/editar Ação Corretiva via Modal"""

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.titulo:
            base = instance.numero_registro or (instance.descricao or "").strip()
            instance.titulo = (base[:200] if base else "Ação Corretiva")
        if not instance.tipo:
            instance.tipo = "corretiva"
        if commit:
            instance.save()
        return instance
    
    class Meta:
        model = AcaoCorretiva
        fields = [
            'data_abertura',
            'ano',
            'unidade',
            'numero_registro',
            'tipo_solucao',
            'origem',
            'descricao',
            'causa_raiz',
            'responsavel',
            'observacoes',
            'link_registro',
            'data_vencimento',
            'data_conclusao',
            'status',
        ]
        widgets = {
            'data_abertura': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'ano': forms.NumberInput(attrs={
                'class': 'form-control',
                'type': 'number'
            }),
            'unidade': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Tecnolens'
            }),
            'numero_registro': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: PA-TEC-001/2026'
            }),
            'tipo_solucao': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Melhoria, RNC, A3'
            }),
            'origem': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Processo, Auditoria'
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descrição da NC e/ou Melhoria'
            }),
            'causa_raiz': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Análise de causa raiz'
            }),
            'responsavel': forms.Select(attrs={
                'class': 'form-control'
            }),
            'observacoes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Observações adicionais'
            }),
            'link_registro': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://link-do-registro.com'
            }),
            'data_vencimento': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'data_conclusao': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'status': forms.Select(attrs={
                'class': 'form-control'
            }),
        }


class AcaoComentarioForm(ModelForm):
    """Form para criação de Comentários em Ações"""
    
    class Meta:
        model = AcaoComentario
        fields = ['conteudo']
        widgets = {
            'conteudo': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Adicionar comentário...'
            }),
        }


# ============================================================================
# ORIGEM DE PROBLEMA / KPI FORM
# ============================================================================

from .models import OrigemProblema, KPIOpcao


class OrigemProblemaForm(ModelForm):
    """Form para criação/edição de Origens de Problema"""
    
    class Meta:
        model = OrigemProblema
        fields = ['nome', 'codigo', 'descricao', 'ativo']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Auditoria, Cliente, Indicador...',
                'required': True
            }),
            'codigo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: AUD, CLI, IND...',
                'maxlength': '20'
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descrição da origem do problema...'
            }),
            'ativo': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }


class KPIOpcaoForm(ModelForm):
    """Form para criação/edição de opções de KPI"""

    class Meta:
        model = KPIOpcao
        fields = ['nome', 'codigo', 'descricao', 'ativo']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Retrabalho, Taxa de Atendimento, SLA...',
                'required': True
            }),
            'codigo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: RET, SLA, TAXA...',
                'maxlength': '20'
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descrição do KPI...'
            }),
            'ativo': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }


class ImportacaoControleRegistrosForm(forms.Form):
    """Formulário para importação de Controle de Registros"""

    arquivo_excel = forms.FileField(
        label="Planilha de Controle de Registros",
        widget=forms.FileInput(attrs={
            "class": "form-control",
            "accept": ".xlsx, .xls"
        }),
    )


class LinhaAcaoForm(ModelForm):
    """Form para criação/edição de Linha de Ação"""
    
    class Meta:
        model = LinhaAcao
        fields = [
            'numero_acao',
            'input_origem',
            'problema',
            'kpi',
            'descricao',
            'classificacao',
            'status',
            'prioridade',
            'responsavel_acao',
            'responsaveis_multiplos',
            'data_primeira_deadline',
            'data_deadline',
            'comentarios',
            'acao_eficaz',
            'data_conclusao',
        ]
        widgets = {
            'numero_acao': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Número da Ação'
            }),
            'input_origem': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Input/Origem'
            }),
            'problema': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descreva o problema identificado'
            }),
            'kpi': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'KPI associado'
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Descrição detalhada da ação'
            }),
            'classificacao': forms.Select(attrs={
                'class': 'form-select'
            }),
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
            'prioridade': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'responsavel_acao': forms.Select(attrs={
                'class': 'form-select'
            }),
            'responsaveis_multiplos': forms.SelectMultiple(attrs={
                'class': 'form-select',
                'size': '5'
            }),
            'data_primeira_deadline': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'data_deadline': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'comentarios': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Comentários e observações adicionais'
            }),
            'acao_eficaz': forms.Select(attrs={
                'class': 'form-select'
            }),
            'data_conclusao': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            })
        }
