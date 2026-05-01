from django import forms

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
        fields = ["nome", "codigo", "categoria", "descricao", "status"]
        labels = {
            "status": "Maquina ativa",
        }
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].queryset = CategoriaMaquina.objects.order_by("nome")
        self.fields["categoria"].empty_label = "Sem categoria"
        _apply_bootstrap_classes(self)