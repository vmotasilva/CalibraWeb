from django import forms
from .models import DocumentoFornecedor

class DocumentoFornecedorForm(forms.ModelForm):
    class Meta:
        model = DocumentoFornecedor
        fields = ["categoria", "arquivo", "data_validade", "observacao"]
