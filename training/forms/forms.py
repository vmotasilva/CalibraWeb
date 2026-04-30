# -*- coding: utf-8 -*-
"""
Forms para Training Module
"""

from django import forms
from procedures.models import Procedimento, RegistroTreinamento


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


class ImportacaoProcedimentosForm(forms.Form):
    """Formulário para importação em massa de procedimentos."""
    
    arquivo_excel = forms.FileField(
        label="Planilha de Procedimentos",
        widget=forms.FileInput(attrs={
            "class": "form-control",
            "accept": ".xlsx, .xls"
        }),
    )
