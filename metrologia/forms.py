from django import forms
from django.core.exceptions import ValidationError
from core.models import UnidadeMedida
from metrologia.models import FaixaMedicao, Cotacao, OcorrenciaCotacao, CategoriaInstrumento


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


# ==============================================================================
# COTAÇÃO
# ==============================================================================

class CotacaoForm(forms.ModelForm):
    """Form para criar e editar cotações"""
    
    class Meta:
        model = Cotacao
        fields = ['fornecedor', 'instrumentos', 'valor', 'observacoes']
        widgets = {
            'fornecedor': forms.Select(attrs={'class': 'form-select'}),
            'instrumentos': forms.CheckboxSelectMultiple(),
            'valor': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Valor em R$'
            }),
            'observacoes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Observações adicionais'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fornecedor'].queryset = self.fields['fornecedor'].queryset.filter(ativo=True)
        self.fields['instrumentos'].queryset = self.fields['instrumentos'].queryset.filter(ativo=True)


class CotacaoAprovarForm(forms.ModelForm):
    """Form para aprovar cotação e definir valor"""
    
    class Meta:
        model = Cotacao
        fields = ['valor', 'observacoes']
        widgets = {
            'valor': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Valor em R$'
            }),
            'observacoes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Observações'
            }),
        }


class OcorrenciaCotacaoForm(forms.ModelForm):
    """Form para registrar ocorrências na cotação"""
    
    class Meta:
        model = OcorrenciaCotacao
        fields = ['tipo', 'descricao', 'acao_tomada']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descreva a ocorrência'
            }),
            'acao_tomada': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Que ação foi tomada?'
            }),
        }


class CategoriaInstrumentoForm(forms.ModelForm):
    """Form para criar e atualizar categorias de instrumentos."""
    
    class Meta:
        model = CategoriaInstrumento
        fields = ['nome', 'descricao']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Ex: Paquímetro, Micrometro, Termômetro, etc',
                'required': 'required',
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Descreva a categoria e suas características principais',
            }),
        }

# ==============================================================================
# UNIDADE DE MEDIDA
# ==============================================================================

class UnidadeMedidaForm(forms.ModelForm):
    """Form para criar e editar unidades de medida."""
    
    class Meta:
        model = UnidadeMedida
        fields = ['nome', 'descricao']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Ex: mm, cm, m, kg, g, etc',
                'required': 'required',
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descrição da unidade de medida (opcional)',
            }),
        }
    
    def clean_nome(self):
        """Validar nome único e sem espaços em branco."""
        nome = self.cleaned_data.get('nome', '').strip()
        
        if not nome:
            raise ValidationError('Nome da unidade é obrigatório')
        
        # Verificar se já existe com mesmo nome (case-insensitive)
        existing = UnidadeMedida.objects.filter(nome__iexact=nome)
        
        if self.instance.pk:
            # Se está editando, excluir a própria instância da verificação
            existing = existing.exclude(pk=self.instance.pk)
        
        if existing.exists():
            raise ValidationError(f'Já existe uma unidade com nome "{nome}"')
        
        return nome
    
    def save(self, commit=True):
        """Garantir que o nome não tenha espaços extras."""
        instance = super().save(commit=False)
        instance.nome = instance.nome.strip()
        if commit:
            instance.save()
        return instance