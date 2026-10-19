from django import forms

from kpi.models import Indicador, Medicao


class IndicadorForm(forms.ModelForm):
    class Meta:
        model = Indicador
        fields = ['nome', 'area', 'unidade', 'meta', 'sentido', 'periodicidade', 'acompanhamento_detalhado',
                  'responsavel', 'ordem', 'descricao', 'ativo']
        widgets = {'descricao': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, f in self.fields.items():
            f.widget.attrs['class'] = 'form-check-input' if name in ('ativo', 'acompanhamento_detalhado') else 'form-control'
        self.fields['ordem'].required = False
        self.fields['sentido'].widget.attrs['class'] = 'form-select'
        self.fields['periodicidade'].widget.attrs['class'] = 'form-select'

    def clean_ordem(self):
        return self.cleaned_data.get('ordem') or 0


class MedicaoForm(forms.ModelForm):
    class Meta:
        model = Medicao
        fields = ['granularidade', 'periodo', 'valor', 'observacao']
