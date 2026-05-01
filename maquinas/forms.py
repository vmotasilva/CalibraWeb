from django import forms

from organization.models import Setor

from .models import CategoriaMaquina, Maquina


def _apply_bootstrap_classes(form):
    for field in form.fields.values():
        widget = field.widget
        current_class = widget.attrs.get("class", "")

        if isinstance(widget, forms.CheckboxInput):
            widget.attrs["class"] = f"{current_class} form-check-input".strip()
            continue

        base_class = "form-select" if isinstance(widget, forms.Select) else "form-control"
        widget.attrs["class"] = f"{current_class} {base_class}".strip()


class CategoriaMaquinaForm(forms.ModelForm):
    class Meta:
        model = CategoriaMaquina
        fields = ["nome", "descricao", "ativo"]
        labels = {
            "ativo": "Categoria ativa",
        }
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_bootstrap_classes(self)


class MaquinaForm(forms.ModelForm):
    class Meta:
        model = Maquina
        fields = ["codigo", "numero_serie", "fabricante", "setor", "categoria", "status"]
        labels = {
            "numero_serie": "Numero de serie",
            "status": "Maquina ativa",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].queryset = CategoriaMaquina.objects.order_by("nome")
        self.fields["categoria"].empty_label = "Sem categoria"
        self.fields["setor"].queryset = Setor.objects.order_by("nome")
        self.fields["setor"].empty_label = "Sem setor"
        _apply_bootstrap_classes(self)