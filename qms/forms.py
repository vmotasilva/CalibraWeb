from django import forms
from .models import Colaborador, Instrumento

# --- WIDGET PARA MÚLTIPLOS ARQUIVOS (CARIMBO) ---
class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single = super().clean
        if isinstance(data, (list, tuple)):
            result = [single(d, initial) for d in data]
        else:
            result = single(data, initial)
        return result

# --- FORMULÁRIO DE VALIDAÇÃO (CARIMBO) ---
class CarimboForm(forms.Form):
    data_validacao = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label="Data da Validação (Carimbo)"
    )
    
    # Opções alinhadas com a View
    STATUS_VALIDACAO = [
        ('Aprovado sem correções', 'Aprovado sem correções'), 
        ('Aprovado com correções', 'Aprovado com correções'), 
        ('Reprovado', 'Reprovado')
    ]
    status_validacao = forms.ChoiceField(
        choices=STATUS_VALIDACAO, 
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Status / Texto do Carimbo"
    )
    
    arquivo_pdf = MultipleFileField(
        label="Selecione os Certificados (PDF)",
        widget=MultipleFileInput(attrs={
            'class': 'form-control', 
            'accept': 'application/pdf', 
            'multiple': True
        })
    )
    
    # Campos ocultos para posição do carimbo (Javascript preenche isso)
    x = forms.FloatField(widget=forms.HiddenInput(), required=False, initial=0)
    y = forms.FloatField(widget=forms.HiddenInput(), required=False, initial=0)
    w = forms.FloatField(widget=forms.HiddenInput(), required=False, initial=0)
    h = forms.FloatField(widget=forms.HiddenInput(), required=False, initial=0)
    page_width = forms.FloatField(widget=forms.HiddenInput(), required=False)
    page_height = forms.FloatField(widget=forms.HiddenInput(), required=False)

# --- FORMULÁRIOS DE IMPORTAÇÃO ---

class ImportacaoInstrumentosForm(forms.Form):
    # Adicionei .csv no accept
    arquivo_excel = forms.FileField(
        label="Planilha de Instrumentos",
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.xlsx, .xls, .csv'})
    )

class ImportacaoColaboradoresForm(forms.Form):
    arquivo_excel = forms.FileField(
        label="Planilha de Colaboradores",
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.xlsx, .xls'})
    )

class ImportacaoProcedimentosForm(forms.Form):
    arquivo_excel = forms.FileField(
        label="Planilha de Procedimentos",
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.xlsx, .xls'})
    )

class ImportacaoHierarquiaForm(forms.Form):
    arquivo_excel = forms.FileField(
        label="Planilha de Hierarquia",
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.xlsx, .xls'})
    )

class ImportacaoHistoricoForm(forms.Form):
    arquivo_excel = forms.FileField(
        label="Histórico de Calibrações",
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.xlsx, .xls'}),
        help_text="Colunas obrigatórias: CÓDIGO (ou TAG), DATA CALIBRAÇÃO, DATA APROVAÇÃO, N CERTIFICADO, RESULTADO"
    )