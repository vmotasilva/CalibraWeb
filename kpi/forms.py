from django import forms

from kpi import calculo
from kpi.models import Indicador, Medicao


class IndicadorForm(forms.ModelForm):
    class Meta:
        model = Indicador
        fields = ['nome', 'area', 'unidade', 'meta', 'sentido', 'periodicidade',
                  'exibir_mensal', 'exibir_semanal', 'exibir_diario',
                  'motivos_diario', 'motivos_semanal', 'motivos_mensal',
                  'campos', 'formula', 'responsavel', 'ordem', 'descricao', 'ativo']
        widgets = {'descricao': forms.Textarea(attrs={'rows': 3}), 'campos': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, f in self.fields.items():
            f.widget.attrs['class'] = 'form-check-input' if name == 'ativo' or name.startswith(('exibir_', 'motivos_')) else 'form-control'
        self.fields['ordem'].required = False
        self.fields['sentido'].widget.attrs['class'] = 'form-select'
        self.fields['periodicidade'].widget.attrs['class'] = 'form-select'

    def clean(self):
        dados = super().clean()
        class _I:
            campos = dados.get('campos', '')
        erro = calculo.validar_formula(dados.get('formula', ''), calculo.lista_campos(_I))
        if erro:
            self.add_error('formula', erro)
        return dados

    def clean_ordem(self):
        return self.cleaned_data.get('ordem') or 0


class MedicaoForm(forms.ModelForm):
    class Meta:
        model = Medicao
        fields = ['granularidade', 'periodo', 'valor', 'observacao']
