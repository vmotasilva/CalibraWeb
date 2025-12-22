# -*- coding: utf-8 -*-
"""
Forms para o módulo Procedures
Consolida forms de training e procurements
"""

from django import forms
from procedures.models import (
    Procedimento, RegistroTreinamento, PacoteTreinamento,
    Fornecedor, AvaliacaoFornecedor, ProcessoCotacao, Orcamento
)


# ==============================================================================
# PROCEDIMENTOS E TREINAMENTOS
# ==============================================================================

class ProcedimentoForm(forms.ModelForm):
    """Formulário para criar/editar procedimentos operacionais."""
    
    class Meta:
        model = Procedimento
        fields = [
            'codigo', 'nome', 'descricao', 'pasta', 'classificacao', 'autor',
            'numero_revisao', 'ultima_revisao', 'data_aprovacao', 'proxima_revisao',
            'data_validade', 'documentos_controlados', 'matriz', 'sub_area'
        ]
        widgets = {
            'codigo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: POP.001'
            }),
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
            'pasta': forms.TextInput(attrs={'class': 'form-control'}),
            'classificacao': forms.TextInput(attrs={'class': 'form-control'}),
            'autor': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_revisao': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 01'
            }),
            'ultima_revisao': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'data_aprovacao': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'proxima_revisao': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'data_validade': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'documentos_controlados': forms.TextInput(attrs={'class': 'form-control'}),
            'matriz': forms.TextInput(attrs={'class': 'form-control'}),
            'sub_area': forms.TextInput(attrs={'class': 'form-control'}),
        }


class RegistroTreinamentoForm(forms.ModelForm):
    """Formulário para registrar treinamentos de colaboradores."""
    
    class Meta:
        model = RegistroTreinamento
        fields = [
            'colaborador', 'procedimento', 'revisao_treinada', 'data_treinamento',
            'validade_treinamento', 'observacoes'
        ]
        widgets = {
            'colaborador': forms.Select(attrs={'class': 'form-select'}),
            'procedimento': forms.Select(attrs={'class': 'form-select'}),
            'revisao_treinada': forms.TextInput(attrs={'class': 'form-control'}),
            'data_treinamento': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'validade_treinamento': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'observacoes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
        }


class PacoteTreinamentoForm(forms.ModelForm):
    """Formulário para criar/editar pacotes de treinamento."""
    
    class Meta:
        model = PacoteTreinamento
        fields = ['nome', 'descricao', 'procedimentos']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
            'procedimentos': forms.CheckboxSelectMultiple(),
        }


class ImportacaoProcedimentosForm(forms.Form):
    """Formulário para importação em massa de procedimentos."""
    
    arquivo_excel = forms.FileField(
        label="Planilha de Procedimentos",
        widget=forms.FileInput(attrs={
            "class": "form-control",
            "accept": ".xlsx, .xls"
        }),
    )


# ==============================================================================
# FORNECEDORES E COTAÇÕES
# ==============================================================================

class FornecedorForm(forms.ModelForm):
    """Formulário para criar/editar fornecedor."""
    
    class Meta:
        model = Fornecedor
        fields = [
            'nome_fantasia', 'razao_social', 'cnpj', 'contato',
            'email', 'telefone', 'escopo_servico', 'status'
        ]
        widgets = {
            'nome_fantasia': forms.TextInput(attrs={'class': 'form-control'}),
            'razao_social': forms.TextInput(attrs={'class': 'form-control'}),
            'cnpj': forms.TextInput(attrs={'class': 'form-control'}),
            'contato': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control'}),
            'escopo_servico': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }


class AvaliacaoFornecedorForm(forms.ModelForm):
    """Formulário para avaliar fornecedor."""
    
    class Meta:
        model = AvaliacaoFornecedor
        fields = [
            'fornecedor', 'nota_tecnica', 'nota_pontualidade',
            'nota_atendimento', 'observacao'
        ]
        widgets = {
            'fornecedor': forms.Select(attrs={'class': 'form-select'}),
            'nota_tecnica': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '10'
            }),
            'nota_pontualidade': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '10'
            }),
            'nota_atendimento': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '10'
            }),
            'observacao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
        }


class ProcessoCotacaoForm(forms.ModelForm):
    """Formulário para criar/editar processo de cotação."""
    
    class Meta:
        model = ProcessoCotacao
        fields = ['titulo', 'prazo_limite', 'instrumentos', 'status', 'responsavel']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'prazo_limite': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'instrumentos': forms.CheckboxSelectMultiple(),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'responsavel': forms.Select(attrs={'class': 'form-select'}),
        }


class OrcamentoForm(forms.ModelForm):
    """Formulário para criar/editar orçamento."""
    
    class Meta:
        model = Orcamento
        fields = [
            'processo', 'fornecedor', 'valor_total', 'prazo_execucao_dias',
            'arquivo_proposta', 'vencedor', 'observacoes'
        ]
        widgets = {
            'processo': forms.Select(attrs={'class': 'form-select'}),
            'fornecedor': forms.Select(attrs={'class': 'form-select'}),
            'valor_total': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'prazo_execucao_dias': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
            'arquivo_proposta': forms.FileInput(attrs={'class': 'form-control'}),
            'vencedor': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'observacoes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
        }
