from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import CategoriaLaboratorio, OcorrenciaLaboratorio


class CategoriaLaboratorioForm(forms.ModelForm):
    class Meta:
        model = CategoriaLaboratorio
        fields = ["nome", "impacto", "descricao", "ativo"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex.: Queda de energia"}),
            "impacto": forms.Select(attrs={"class": "form-select"}),
            "descricao": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class OcorrenciaLaboratorioForm(forms.ModelForm):
    impacto = forms.ChoiceField(
        choices=[("", "Selecione")] + CategoriaLaboratorio.IMPACTO_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = OcorrenciaLaboratorio
        fields = [
            "data_abertura",
            "data_encerramento",
            "responsavel",
            "categoria",
            "assunto",
            "impacto",
            "detalhamento",
            "consequencias",
        ]
        widgets = {
            "data_abertura": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
            "data_encerramento": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
            "responsavel": forms.Select(attrs={"class": "form-select"}),
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "assunto": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Selecione uma categoria sugerida ou escreva um assunto livre",
                    "list": "assuntos-categoria",
                }
            ),
            "detalhamento": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            "consequencias": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].required = False
        self.fields["assunto"].required = False
        self.fields["data_encerramento"].required = False
        self.fields["responsavel"].queryset = get_user_model().objects.order_by("first_name", "username")
        self.fields["categoria"].queryset = CategoriaLaboratorio.objects.order_by("nome")

        if user and not self.instance.pk and not self.initial.get("responsavel"):
            self.initial["responsavel"] = user

        for field_name in ("data_abertura", "data_encerramento"):
            valor = getattr(self.instance, field_name, None)
            if valor:
                self.initial[field_name] = timezone.localtime(valor).strftime("%Y-%m-%dT%H:%M")

    def clean(self):
        cleaned_data = super().clean()
        categoria = cleaned_data.get("categoria")
        assunto = (cleaned_data.get("assunto") or "").strip()
        impacto = cleaned_data.get("impacto")
        abertura = cleaned_data.get("data_abertura")
        encerramento = cleaned_data.get("data_encerramento")

        if not assunto and categoria:
            assunto = categoria.nome
            cleaned_data["assunto"] = assunto

        if not assunto:
            self.add_error("assunto", "Informe um assunto ou selecione uma categoria cadastrada.")

        if not impacto and categoria:
            cleaned_data["impacto"] = categoria.impacto
            impacto = categoria.impacto

        if not impacto:
            self.add_error("impacto", "Informe o impacto da ocorrencia.")

        if abertura and encerramento and encerramento < abertura:
            self.add_error("data_encerramento", "O encerramento nao pode ser anterior a abertura.")

        return cleaned_data
