from django import forms

from kpi.models import Indicador, Medicao


class IndicadorForm(forms.ModelForm):
    class Meta:
        model = Indicador
        fields = ['nome', 'area', 'unidade', 'meta', 'sentido', 'periodicidade', 'responsavel', 'descricao', 'ativo']
        widgets = {'descricao': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, f in self.fields.items():
            f.widget.attrs['class'] = 'form-check-input' if name == 'ativo' else 'form-control'
        self.fields['sentido'].widget.attrs['class'] = 'form-select'
        self.fields['periodicidade'].widget.attrs['class'] = 'form-select'


class MedicaoForm(forms.ModelForm):
    class Meta:
        model = Medicao
        fields = ['periodo', 'valor', 'observacao']
        widgets = {'periodo': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs['class'] = 'form-control'
