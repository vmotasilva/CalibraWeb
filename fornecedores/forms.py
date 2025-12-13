from django import forms
from .models import Fornecedor

class FornecedorForm(forms.ModelForm):
    class Meta:
        model = Fornecedor
        fields = [
            "empresa", "nome_fantasia", "endereco", "cnpj", "siret", "ein", "telefone", "uf", "tipo", "ativo"
        ]
