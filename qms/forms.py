from django import forms
from .models import Colaborador, Instrumento
from datetime import date

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)
    def clean(self, data, initial=None):
        single = super().clean
        if isinstance(data, (list, tuple)): return [single(d, initial) for d in data]
        return single(data, initial)

class CarimboForm(forms.Form):
    # --- DADOS GERAIS ---
    # OBS: Campo 'colaborador' removido.
    
    data_validacao = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label="Data da Validação (Carimbo)"
    )
    
    # OPÇÕES CORRETAS
    STATUS_VALIDACAO = [
        ('Aprovado sem correções', 'Aprovado sem correções'), 
        ('Aprovado com correções', 'Aprovado com correções'), 
        ('Reprovado', 'Reprovado')
    ]
    status_validacao = forms.ChoiceField(
        choices=STATUS_VALIDACAO, 
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Texto do Carimbo"
    )
    
    arquivo_pdf = MultipleFileField(
        label="Selecione os Certificados",
        widget=MultipleFileInput(attrs={'class': 'form-control', 'accept': 'application/pdf', 'onchange': 'handleFileSelect(event)'})
    )
    
    # --- Inputs Ocultos de Posição ---
    x = forms.FloatField(widget=forms.HiddenInput(), required=False, initial=140)
    y = forms.FloatField(widget=forms.HiddenInput(), required=False, initial=250)
    w = forms.FloatField(widget=forms.HiddenInput(), required=False, initial=60)
    h = forms.FloatField(widget=forms.HiddenInput(), required=False, initial=30)
    page_width = forms.FloatField(widget=forms.HiddenInput(), required=False)
    page_height = forms.FloatField(widget=forms.HiddenInput(), required=False)

class ImportacaoInstrumentosForm(forms.Form):
    arquivo_excel = forms.FileField(widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.xlsx, .xls'}))

class ImportacaoColaboradoresForm(forms.Form):
    arquivo_excel = forms.FileField(widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.xlsx, .xls'}))

class ImportacaoProcedimentosForm(forms.Form):
    arquivo_excel = forms.FileField(label="Planilha de Procedimentos", widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.xlsx, .xls'}))

class ImportacaoHierarquiaForm(forms.Form):
    arquivo_excel = forms.FileField(label="Planilha de Hierarquia", widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.xlsx, .xls'}))

class ImportacaoHistoricoForm(forms.Form):
    arquivo_excel = forms.FileField(
        label="Histórico de Calibrações (.xlsx)",
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.xlsx, .xls'}),
        help_text="Colunas obrigatórias: CÓDIGO, DATA CALIBRAÇÃO, DATA APROVAÇÃO, N CERTIFICADO, RESULTADO"
    )