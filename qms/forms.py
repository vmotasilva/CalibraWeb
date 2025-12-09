from django import forms
from metrologia.models import Instrumento, FaixaMedicao, ResultadoFaixaCalibracao
from qms.models import HistoricoCalibracao


class InstrumentoForm(forms.ModelForm):
    """Form for creating/editing instruments."""
    class Meta:
        model = Instrumento
        fields = [
            'tag', 'codigo', 'descricao', 'categoria', 'modelo', 'serie',
            'setor', 'localizacao', 'ativo', 'responsavel',
            'data_ultima_calibracao', 'data_proxima_calibracao',
        ]
        widgets = {
            'tag': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: LE-02'}),
            'codigo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Código interno'}),
            'descricao': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Descrição completa'}),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Modelo'}),
            'serie': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Série'}),
            'setor': forms.Select(attrs={'class': 'form-select'}),
            'localizacao': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Localização no setor'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'responsavel': forms.Select(attrs={'class': 'form-select'}),
            'data_ultima_calibracao': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'data_proxima_calibracao': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }


class FaixaMedicaoForm(forms.ModelForm):
    """Form for creating/editing measurement ranges."""
    class Meta:
        model = FaixaMedicao
        fields = ['unidade', 'valor_minimo', 'valor_maximo', 'resolucao', 'nominal', 'tolerancia_mais_menos']
        widgets = {
            'unidade': forms.Select(attrs={'class': 'form-select'}),
            'valor_minimo': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.0001',
                'placeholder': 'Valor mínimo da faixa'
            }),
            'valor_maximo': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.0001',
                'placeholder': 'Valor máximo da faixa'
            }),
            'resolucao': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.0001',
                'placeholder': 'Resolução do instrumento (opcional)'
            }),
            'nominal': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.0001',
                'placeholder': 'Valor nominal/central (opcional)'
            }),
            'tolerancia_mais_menos': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.0001',
                'placeholder': 'Tolerância ±X (opcional)'
            }),
        }


class ResultadoFaixaCalibracaoForm(forms.ModelForm):
    """Form for calibration results per measurement range."""
    class Meta:
        model = ResultadoFaixaCalibracao
        fields = ['erro_max', 'erro_min', 'incerteza', 'resultado']
        widgets = {
            'erro_max': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.0001',
                'placeholder': 'Erro máximo encontrado'
            }),
            'erro_min': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.0001',
                'placeholder': 'Erro mínimo encontrado'
            }),
            'incerteza': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.0001',
                'placeholder': 'Incerteza da medição'
            }),
            'resultado': forms.Select(attrs={'class': 'form-select'}),
        }
