from django import forms
from .models import HistoricoCalibracao, Padrao

class HistoricoCalibracaoForm(forms.ModelForm):
    class Meta:
        model = HistoricoCalibracao
        fields = [
            'data_calibracao',
            'data_aprovacao',
            'numero_certificado',
            'tem_selo_rbc',
            'padroes_utilizados',
            'tipo_calibracao',
            'responsavel',
            'fornecedor',
            'erro_encontrado',
            'incerteza',
            'tolerancia_usada',
            'proxima_calibracao',
            'certificado',
            'resultado',
            'observacoes',
        ]
        widgets = {
            'data_calibracao': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'data_aprovacao': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'numero_certificado': forms.TextInput(attrs={'class': 'form-control'}),
            'tem_selo_rbc': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'padroes_utilizados': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'tipo_calibracao': forms.Select(attrs={'class': 'form-select'}),
            'responsavel': forms.TextInput(attrs={'class': 'form-control'}),
            'fornecedor': forms.TextInput(attrs={'class': 'form-control'}),
            'erro_encontrado': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'incerteza': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'tolerancia_usada': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'proxima_calibracao': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'certificado': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'resultado': forms.Select(attrs={'class': 'form-select'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
