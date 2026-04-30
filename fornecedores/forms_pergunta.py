from django import forms
from .models import PerguntaAvaliacao

class PerguntaAvaliacaoForm(forms.ModelForm):
    class Meta:
        model = PerguntaAvaliacao
        fields = ["texto", "tipo", "produto_servico", "ativo", "ordem"]
        widgets = {
            "texto": forms.TextInput(attrs={"class": "form-control"}),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "produto_servico": forms.Select(attrs={"class": "form-select"}),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "ordem": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
        }

    def clean(self):
        cleaned_data = super().clean()
        tipo = cleaned_data.get("tipo")
        produto_servico = cleaned_data.get("produto_servico")
        if tipo == "MONITORAMENTO" and not produto_servico:
            self.add_error("produto_servico", "Obrigatório para perguntas de Monitoramento.")
        return cleaned_data
