# -*- coding: utf-8 -*-
"""
Forms para Metrologia Module
"""

from django import forms
from metrologia.models import Instrumento, HistoricoCalibracao, FaixaMedicao


class InstrumentoForm(forms.ModelForm):
    """Formulário para criar/editar instrumentos de calibração."""
    
    class Meta:
        model = Instrumento
        fields = [
            'tag', 'descricao', 'categoria', 'setor', 'fabricante', 'modelo', 
            'serie', 'frequencia_meses', 'ativo'
        ]
        widgets = {
            'tag': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'TAG / Código'
            }),
            'descricao': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Descrição do instrumento'
            }),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'setor': forms.Select(attrs={'class': 'form-select'}),
            'fabricante': forms.TextInput(attrs={'class': 'form-control'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control'}),
            'serie': forms.TextInput(attrs={'class': 'form-control'}),
            'frequencia_meses': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '1'
            }),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class HistoricoCalibracaoForm(forms.ModelForm):
    """Formulário para registrar histórico de calibração."""
    
    
    class Meta:
        model = HistoricoCalibracao
        fields = [
            'data_calibracao', 'proxima_calibracao', 'numero_certificado',
            'tipo_calibracao', 'responsavel', 'fornecedor', 'tem_selo_rbc',
            'certificado'
        ]
        # arquivos_padroes NÃO deve estar aqui!
        widgets = {
            'data_calibracao': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'proxima_calibracao': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'numero_certificado': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: CERT-2024-001'
            }),
            'tipo_calibracao': forms.Select(attrs={'class': 'form-select'}),
            'responsavel': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome do responsável'
            }),
            'fornecedor': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome do laboratório/fornecedor'
            }),
            'tem_selo_rbc': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'certificado': forms.FileInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        """Initialize form with optional instrumento and user parameters."""
        instrumento = kwargs.pop('instrumento', None)
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Pré-preencher responsável com nome do usuário logado
        if not self.is_bound and user is not None:
            first = (getattr(user, 'first_name', '') or '').strip()
            last = (getattr(user, 'last_name', '') or '').strip()
            nome_resp = (first + ' ' + last).strip()
            
            if not nome_resp:
                full_name = (getattr(user, 'get_full_name', lambda: '')() or '').strip()
                nome_resp = full_name or (getattr(user, 'username', '') or '').strip()
            
            if nome_resp:
                self.fields['responsavel'].initial = nome_resp
        
        # responsável é obrigatório
        self.fields['responsavel'].required = True


class ImportacaoInstrumentosForm(forms.Form):
    """Formulário para importação em massa de instrumentos."""
    
    arquivo_excel = forms.FileField(
        label="Planilha de Instrumentos",
        widget=forms.FileInput(attrs={
            "class": "form-control",
            "accept": ".xlsx, .xls, .csv"
        }),
    )


class ImportacaoHistoricoForm(forms.Form):
    """Formulário para importação em massa de históricos de calibração."""
    
    arquivo_excel = forms.FileField(
        label="Histórico de Calibrações",
        widget=forms.FileInput(attrs={
            "class": "form-control",
            "accept": ".xlsx, .xls, .csv"
        }),
        help_text="Colunas obrigatórias: CÓDIGO (ou TAG), DATA CALIBRAÇÃO, DATA APROVAÇÃO, N CERTIFICADO, RESULTADO",
    )


class FaixaMedicaoFormWithValidation(forms.ModelForm):
    """Formulário para criar/editar faixas de medição com validação."""
    
    class Meta:
        model = FaixaMedicao
        fields = ['unidade', 'valor_minimo', 'valor_maximo', 'resolucao', 'nominal', 'tolerancia_mais_menos']
        widgets = {
            'unidade': forms.Select(attrs={'class': 'form-select'}),
            'valor_minimo': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'valor_maximo': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'resolucao': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'nominal': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'tolerancia_mais_menos': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
        }
    
    def clean(self):
        """Validate faixa data."""
        cleaned_data = super().clean()
        valor_minimo = cleaned_data.get('valor_minimo')
        valor_maximo = cleaned_data.get('valor_maximo')
        
        if valor_minimo is not None and valor_maximo is not None:
            if valor_minimo >= valor_maximo:
                raise forms.ValidationError(
                    "Valor mínimo deve ser menor que valor máximo."
                )
        
        return cleaned_data
