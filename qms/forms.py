from django import forms
from .models import Colaborador

# --- Widgets e Campos Personalizados ---
class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result

# --- Formulário de Carimbo ---
class CarimboForm(forms.Form):
    colaborador = forms.ModelChoiceField(
        queryset=Colaborador.objects.filter(is_active=True).order_by('nome_completo'),
        label="Responsável Técnico",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    arquivo_pdf = MultipleFileField(
        label="Selecione os Certificados (Um ou Vários)",
        widget=MultipleFileInput(attrs={
            'class': 'form-control', 
            'accept': 'application/pdf', 
            'onchange': 'carregarPreview(event)'
        })
    )
    
    STATUS_VALIDACAO = [
        ('Aprovado sem correção', 'Aprovado sem correção'),
        ('Aprovado com correção', 'Aprovado com correção'),
        ('Reprovado', 'Reprovado'),
    ]
    status_validacao = forms.ChoiceField(
        choices=STATUS_VALIDACAO, 
        label="Parecer Técnico",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Campos ocultos
    x = forms.FloatField(widget=forms.HiddenInput(), required=False)
    y = forms.FloatField(widget=forms.HiddenInput(), required=False)
    w = forms.FloatField(widget=forms.HiddenInput(), required=False)
    h = forms.FloatField(widget=forms.HiddenInput(), required=False)
    page_width = forms.FloatField(widget=forms.HiddenInput(), required=False)
    page_height = forms.FloatField(widget=forms.HiddenInput(), required=False)

# --- Formulários de Importação ---
class ImportacaoInstrumentosForm(forms.Form):
    arquivo_excel = forms.FileField(
        label="Planilha de Instrumentos (Excel .xlsx)",
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.xlsx, .xls'})
    )

class ImportacaoColaboradoresForm(forms.Form):
    arquivo_excel = forms.FileField(
        label="Planilha de Colaboradores (Excel .xlsx)",
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.xlsx, .xls'})
    )