# -*- coding: utf-8 -*-
"""
Formulários para upload e mapeamento de templates de lista de presença
"""

from django import forms
from django.forms import modelformset_factory
from procedures.models import TemplateListaPresenca, MapeamentoCampoListaPresenca


class UploadExcelTemplateForm(forms.ModelForm):
    """Formulário para upload de arquivo Excel template"""
    
    class Meta:
        model = TemplateListaPresenca
        fields = ['nome', 'descricao', 'arquivo_excel_template', 'metodo_mapeamento']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Template Treinamento Básico',
                'required': True,
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Descreva para que serve este template',
                'rows': 3,
            }),
            'arquivo_excel_template': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.xlsx',
                'required': True,
            }),
            'metodo_mapeamento': forms.Select(attrs={
                'class': 'form-control',
                'required': True,
            }),
        }
        labels = {
            'nome': 'Nome do Template',
            'descricao': 'Descrição',
            'arquivo_excel_template': 'Arquivo Excel (.xlsx)',
            'metodo_mapeamento': 'Método de Mapeamento Padrão',
        }
        help_texts = {
            'arquivo_excel_template': 'Faça upload de um arquivo Excel em branco (.xlsx) para usar como base do template',
            'metodo_mapeamento': 'Escolha como os campos serão mapeados por padrão',
        }


class MapeamentoCampoForm(forms.ModelForm):
    """Formulário para mapear um campo específico"""
    
    class Meta:
        model = MapeamentoCampoListaPresenca
        fields = ['tipo_campo', 'localizacao', 'metodo', 'pagina', 'obrigatorio', 'permite_imagem_marcacao']
        widgets = {
            'tipo_campo': forms.Select(attrs={
                'class': 'form-control',
                'readonly': True,
            }),
            'localizacao': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: A1, B2, etc',
                'pattern': r'[A-Z]{1,2}\d{1,3}',
                'title': 'Formato válido: A1, B2, Z100, etc',
                'required': True,
            }),
            'metodo': forms.Select(attrs={
                'class': 'form-control',
                'required': True,
            }),
            'pagina': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 10,
                'type': 'number',
            }),
            'obrigatorio': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'type': 'checkbox',
            }),
            'permite_imagem_marcacao': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'type': 'checkbox',
            }),
        }
        labels = {
            'tipo_campo': 'Campo',
            'localizacao': 'Localização (Célula)',
            'metodo': 'Método de Definição',
            'pagina': 'Página',
            'obrigatorio': 'Campo Obrigatório',
            'permite_imagem_marcacao': 'Permite Imagem/Marcação',
        }


class MapeamentoMultiploCamposForm(forms.Form):
    """Formulário para mapear múltiplos campos de uma vez"""
    
    CAMPOS_MAPEAMENTO = [
        ('titulo_treinamento', 'Título do Treinamento'),
        ('categoria_treinamento', 'Categoria do Treinamento'),
        ('metodologia', 'Metodologia'),
        ('area_conhecimento', 'Área de Conhecimento'),
        ('necessita_avaliacao', 'Necessita de Avaliação'),
        ('facilitador_fornecedor', 'Facilitador/Fornecedor'),
        ('data_hora', 'Data e Hora'),
        ('carga_horaria', 'Carga Horária'),
        ('procedimentos_assuntos', 'Procedimentos/Assuntos'),
    ]
    
    metodo_choices = [
        ('clique', 'Clique na Célula'),
        ('referencia', 'Referência de Célula (A1)'),
        ('ambos', 'Ambos os Métodos'),
    ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Criar field para cada campo de mapeamento
        for tipo_campo, label in self.CAMPOS_MAPEAMENTO:
            # Campo de localização
            self.fields[f'{tipo_campo}_localizacao'] = forms.CharField(
                label=f'{label} - Localização',
                required=True,
                widget=forms.TextInput(attrs={
                    'class': 'form-control form-control-sm',
                    'placeholder': 'A1, B2, etc',
                    'pattern': r'[A-Z]{1,2}\d{1,3}',
                    'data-tipo-campo': tipo_campo,
                })
            )
            
            # Campo de método
            self.fields[f'{tipo_campo}_metodo'] = forms.ChoiceField(
                label=f'{label} - Método',
                choices=self.metodo_choices,
                initial='referencia',
                widget=forms.Select(attrs={
                    'class': 'form-control form-control-sm',
                    'data-tipo-campo': tipo_campo,
                })
            )
            
            # Campo de página
            self.fields[f'{tipo_campo}_pagina'] = forms.IntegerField(
                label=f'{label} - Página',
                initial=1,
                min_value=1,
                max_value=10,
                widget=forms.NumberInput(attrs={
                    'class': 'form-control form-control-sm',
                    'data-tipo-campo': tipo_campo,
                })
            )
            
            # Campo obrigatório
            self.fields[f'{tipo_campo}_obrigatorio'] = forms.BooleanField(
                label=f'{label} - Obrigatório',
                required=False,
                initial=True,
                widget=forms.CheckboxInput(attrs={
                    'class': 'form-check-input',
                    'data-tipo-campo': tipo_campo,
                })
            )
            
            # Campo permite imagem
            self.fields[f'{tipo_campo}_permite_imagem'] = forms.BooleanField(
                label=f'{label} - Permite Imagem/Marca',
                required=False,
                initial=False,
                widget=forms.CheckboxInput(attrs={
                    'class': 'form-check-input',
                    'data-tipo-campo': tipo_campo,
                })
            )


# Formset para múltiplos mapeamentos
MapeamentoCampoFormSet = modelformset_factory(
    MapeamentoCampoListaPresenca,
    form=MapeamentoCampoForm,
    extra=0,
    can_delete=True,
)


class ValidarMapeamentoForm(forms.Form):
    """Formulário para validar se todos os campos obrigatórios foram mapeados"""
    
    # Apenas usado para validação, não tem campos reais
    pass
