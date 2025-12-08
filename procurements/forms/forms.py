# -*- coding: utf-8 -*-
"""
Forms para Procurements Module
"""

from django import forms
from qms.models import SolicitacaoInstrumento


class SolicitacaoForm(forms.ModelForm):
    """Formulário para criar solicitações de instrumentos."""
    
    class Meta:
        model = SolicitacaoInstrumento
        fields = ['tipo', 'instrumento_alvo', 'motivo']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'instrumento_alvo': forms.Select(attrs={'class': 'form-select'}),
            'motivo': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4
            }),
        }


class ImportacaoPadroesForm(forms.Form):
    """Formulário para importação de padrões e kits."""
    
    arquivo_excel = forms.FileField(
        label="Planilha de Padrões/Kits",
        widget=forms.FileInput(attrs={
            "class": "form-control",
            "accept": ".xlsx, .xls"
        }),
    )
