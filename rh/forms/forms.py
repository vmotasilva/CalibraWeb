# -*- coding: utf-8 -*-
"""
Forms para RH Module
"""

from django import forms
from rh.models import Colaborador, Ocorrencia


class ColaboradorForm(forms.ModelForm):
    """Formulário para editar dados de colaborador."""
    
    class Meta:
        model = Colaborador
        fields = "__all__"
        exclude = ["user_django", "criado_em"]
        widgets = {
            "nome_completo": forms.TextInput(attrs={"class": "form-control"}),
            "matricula": forms.TextInput(attrs={"class": "form-control"}),
            "cpf": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "000.000.000-00"
            }),
            "cargo": forms.TextInput(attrs={"class": "form-control"}),
            "grupo": forms.TextInput(attrs={"class": "form-control"}),
            "setor": forms.Select(attrs={"class": "form-select"}),
            "centro_custo": forms.Select(attrs={"class": "form-select"}),
            "turno": forms.Select(attrs={"class": "form-select"}),
            "lider": forms.Select(attrs={"class": "form-select"}),
            "supervisor": forms.Select(attrs={"class": "form-select"}),
            "gerente": forms.Select(attrs={"class": "form-select"}),
            "salario": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "0.01"
            }),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "em_ferias": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "pacotes_treinamento": forms.SelectMultiple(attrs={
                "class": "form-control",
                "style": "height: 150px;"
            }),
        }


class OcorrenciaForm(forms.ModelForm):
    """Formulário para registrar ocorrências de RH."""
    
    class Meta:
        model = Ocorrencia
        fields = ['colaborador', 'data_ocorrencia', 'tipo', 'titulo', 'descricao', 'arquivo_evidencia']
        widgets = {
            'descricao': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control'
            }),
            'titulo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Título da ocorrência'
            }),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'colaborador': forms.Select(attrs={'class': 'form-select'}),
            'data_ocorrencia': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'arquivo_evidencia': forms.FileInput(attrs={
                'class': 'form-control'
            }),
        }


class ImportacaoColaboradoresForm(forms.Form):
    """Formulário para importação em massa de colaboradores."""
    
    arquivo_excel = forms.FileField(
        label="Planilha de Colaboradores",
        widget=forms.FileInput(attrs={
            "class": "form-control",
            "accept": ".xlsx, .xls"
        }),
    )


class ImportacaoHierarquiaForm(forms.Form):
    """Formulário para importação em massa de hierarquia."""
    
    arquivo_excel = forms.FileField(
        label="Planilha de Hierarquia",
        widget=forms.FileInput(attrs={
            "class": "form-control",
            "accept": ".xlsx, .xls"
        }),
    )


class ImportacaoFeriasForm(forms.Form):
    """Formulário para importação em massa de férias."""
    
    arquivo_excel = forms.FileField(
        label="Selecione a Planilha de Férias (.xlsx ou .csv)",
        widget=forms.ClearableFileInput(attrs={"class": "form-control"}),
    )
