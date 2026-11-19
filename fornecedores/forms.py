import re

from django import forms

from .models import Fornecedor

UF_CHOICES = [("", "---------")] + [(uf, uf) for uf in (
    "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()
)] + [("EX", "EX (Exterior)")]


def cnpj_valido(numeros):
    """Valida os dígitos verificadores de um CNPJ (somente números, 14 dígitos)."""
    if len(numeros) != 14 or len(set(numeros)) == 1:
        return False
    digitos = [int(c) for c in numeros]

    def dv(base, pesos):
        resto = sum(d * p for d, p in zip(base, pesos)) % 11
        return 0 if resto < 2 else 11 - resto

    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1
    return dv(digitos[:12], pesos1) == digitos[12] and dv(digitos[:13], pesos2) == digitos[13]


class FornecedorForm(forms.ModelForm):
    uf = forms.ChoiceField(choices=UF_CHOICES, label="UF")

    class Meta:
        model = Fornecedor
        fields = [
            "empresa", "nome_fantasia", "endereco", "cnpj", "siret", "ein", "telefone", "uf", "tipo", "ativo",
            "licenca_funcionamento", "autorizacao_funcionamento", "certificado_iso"
        ]

    def clean_cnpj(self):
        valor = (self.cleaned_data.get("cnpj") or "").strip()
        if not valor:
            return None
        numeros = re.sub(r"\D", "", valor)
        if not cnpj_valido(numeros):
            raise forms.ValidationError("CNPJ inválido.")
        formatado = f"{numeros[:2]}.{numeros[2:5]}.{numeros[5:8]}/{numeros[8:12]}-{numeros[12:]}"
        duplicados = Fornecedor.objects.filter(cnpj__in=[formatado, numeros])
        if self.instance.pk:
            duplicados = duplicados.exclude(pk=self.instance.pk)
        if duplicados.exists():
            raise forms.ValidationError(f"Já existe um fornecedor com este CNPJ ({duplicados.first().empresa}).")
        return formatado

    def clean_telefone(self):
        return (self.cleaned_data.get("telefone") or "").strip() or None

    def clean_siret(self):
        return (self.cleaned_data.get("siret") or "").strip() or None

    def clean_ein(self):
        return (self.cleaned_data.get("ein") or "").strip() or None
