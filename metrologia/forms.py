from django import forms
from metrologia.models import FaixaMedicao
from django.core.exceptions import ValidationError


def validate_faixa_range(valor_minimo, valor_maximo):
    """Validate that valor_minimo < valor_maximo"""
    if valor_minimo is not None and valor_maximo is not None:
        if valor_minimo >= valor_maximo:
            raise ValidationError("Valor mínimo deve ser menor que valor máximo")


class FaixaMedicaoFormWithValidation(forms.ModelForm):
    """Enhanced FaixaMedicaoForm with cross-field validation."""
    
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
    
    def clean(self):
        cleaned_data = super().clean()
        valor_minimo = cleaned_data.get('valor_minimo')
        valor_maximo = cleaned_data.get('valor_maximo')
        nominal = cleaned_data.get('nominal')
        
        # Validar min < max
        if valor_minimo is not None and valor_maximo is not None:
            if valor_minimo >= valor_maximo:
                raise ValidationError(
                    "Erro: Valor mínimo (%(min)s) deve ser menor que valor máximo (%(max)s)",
                    code='invalid_range',
                    params={'min': valor_minimo, 'max': valor_maximo},
                )
        
        # Validar nominal dentro da faixa
        if nominal is not None and valor_minimo is not None and valor_maximo is not None:
            if not (valor_minimo <= nominal <= valor_maximo):
                raise ValidationError(
                    "Erro: Valor nominal (%(nominal)s) deve estar entre min (%(min)s) e máx (%(max)s)",
                    code='nominal_out_of_range',
                    params={'nominal': nominal, 'min': valor_minimo, 'max': valor_maximo},
                )
        
        return cleaned_data
