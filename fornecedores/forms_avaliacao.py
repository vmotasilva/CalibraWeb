from django import forms
from .models import AvaliacaoFornecedor, RespostaAvaliacao, PerguntaAvaliacao

from django.contrib.auth import get_user_model

User = get_user_model()

class AvaliacaoFornecedorForm(forms.ModelForm):
    data = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
    class Meta:
        model = AvaliacaoFornecedor
        fields = ["data", "nota_fiscal", "tipo_nota", "observacao"]
        widgets = {
            "observacao": forms.Textarea(attrs={"rows": 3}),
        }

class RespostaAvaliacaoForm(forms.ModelForm):
    class Meta:
        model = RespostaAvaliacao
        fields = ["pergunta", "resposta", "observacao"]
        widgets = {"pergunta": forms.HiddenInput()}
