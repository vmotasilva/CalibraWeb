import os

from django import forms

from .models import DocumentoFornecedor

EXTENSOES_PERMITIDAS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg"}
TAMANHO_MAXIMO_MB = 10


class DocumentoFornecedorForm(forms.ModelForm):
    class Meta:
        model = DocumentoFornecedor
        fields = ["categoria", "arquivo", "data_validade", "observacao"]
        widgets = {
            "data_validade": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "observacao": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_arquivo(self):
        arquivo = self.cleaned_data["arquivo"]
        ext = os.path.splitext(arquivo.name)[1].lower()
        if ext not in EXTENSOES_PERMITIDAS:
            raise forms.ValidationError(
                "Tipo de arquivo não permitido. Use: " + ", ".join(sorted(EXTENSOES_PERMITIDAS)) + "."
            )
        if arquivo.size > TAMANHO_MAXIMO_MB * 1024 * 1024:
            raise forms.ValidationError(f"O arquivo excede {TAMANHO_MAXIMO_MB} MB.")
        return arquivo
