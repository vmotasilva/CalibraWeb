from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import (
    CategoriaLaboratorio, 
    OcorrenciaLaboratorio, 
    OcorrenciaLaboratorioAnotacao, 
    TratamentoAntiReflexo,
    RegraTurnoCoating,
    TurnoCoating,
    RegistroCoating
)
from rh.models import Colaborador
from maquinas.models import Maquina


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
    colaborador = forms.ModelChoiceField(
        queryset=Colaborador.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Colaborador (se aplicável)",
    )
    maquina = forms.ModelChoiceField(
        queryset=Maquina.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Máquina (se aplicável)",
    )
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
            "colaborador",
            "maquina",
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
        self.fields["colaborador"].queryset = Colaborador.objects.order_by("nome_completo")
        self.fields["maquina"].queryset = Maquina.objects.order_by("codigo", "fabricante", "numero_serie")

        if user and not self.instance.pk and not self.initial.get("responsavel"):
            self.initial["responsavel"] = user

        for field_name in ("data_abertura", "data_encerramento"):
            valor = getattr(self.instance, field_name, None)
            if valor:
                self.initial[field_name] = timezone.localtime(valor).strftime("%Y-%m-%dT%H:%M")

        # Esconde campos colaborador/maquina por padrão
        self.fields["colaborador"].widget.attrs["style"] = "display:none;"
        self.fields["maquina"].widget.attrs["style"] = "display:none;"

        # Exibe campo conforme categoria (se já selecionada)
        categoria = self.initial.get("categoria") or self.data.get("categoria")
        if categoria:
            cat_obj = CategoriaLaboratorio.objects.filter(pk=categoria).first()
            if cat_obj:
                if cat_obj.exige_colaborador:
                    self.fields["colaborador"].widget.attrs.pop("style", None)
                if cat_obj.exige_maquina:
                    self.fields["maquina"].widget.attrs.pop("style", None)

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


class OcorrenciaAnotacaoForm(forms.ModelForm):
    class Meta:
        model = OcorrenciaLaboratorioAnotacao
        fields = ["texto"]
        widgets = {
            "texto": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 6,
                    "placeholder": "Registre uma nova anotacao de acompanhamento, tratativa ou decisao gerencial.",
                }
            ),
        }


class OcorrenciaEncerramentoForm(forms.ModelForm):
    registrar_medidas = forms.BooleanField(
        required=False,
        label="Medidas",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    class Meta:
        model = OcorrenciaLaboratorio
        fields = [
            "data_encerramento",
            "perda_producao",
            "unidade_perda_producao",
            "horas_indisponibilidade",
            "impacto_financeiro",
            "observacoes_encerramento",
        ]
        widgets = {
            "data_encerramento": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"}
            ),
            "perda_producao": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0", "placeholder": "0.00"}
            ),
            "unidade_perda_producao": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ex.: pecas, lotes, analises, amostras",
                }
            ),
            "horas_indisponibilidade": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0", "placeholder": "0.00"}
            ),
            "impacto_financeiro": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0", "placeholder": "0.00"}
            ),
            "observacoes_encerramento": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": "Descreva o impacto final, tratativa adotada e pendencias remanescentes.",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["data_encerramento"].required = True

        possui_medidas = any(
            valor not in (None, "")
            for valor in (
                self.instance.perda_producao,
                self.instance.unidade_perda_producao,
                self.instance.horas_indisponibilidade,
                self.instance.impacto_financeiro,
            )
        )
        if not self.is_bound:
            self.initial["registrar_medidas"] = possui_medidas

        valor = getattr(self.instance, "data_encerramento", None)
        if valor:
            self.initial["data_encerramento"] = timezone.localtime(valor).strftime("%Y-%m-%dT%H:%M")
        elif not self.is_bound:
            self.initial["data_encerramento"] = timezone.localtime(timezone.now()).strftime("%Y-%m-%dT%H:%M")

    def clean(self):
        cleaned_data = super().clean()
        encerramento = cleaned_data.get("data_encerramento")
        registrar_medidas = cleaned_data.get("registrar_medidas")
        unidade_perda = (cleaned_data.get("unidade_perda_producao") or "").strip()

        if encerramento and self.instance.data_abertura and encerramento <= self.instance.data_abertura:
            self.add_error("data_encerramento", "O encerramento deve ser posterior a abertura.")

        if not registrar_medidas:
            cleaned_data["perda_producao"] = None
            cleaned_data["unidade_perda_producao"] = ""
            cleaned_data["horas_indisponibilidade"] = None
            cleaned_data["impacto_financeiro"] = None
            return cleaned_data

        for field_name in ("perda_producao", "horas_indisponibilidade", "impacto_financeiro"):
            valor = cleaned_data.get(field_name)
            if valor is not None and valor < 0:
                self.add_error(field_name, "Informe um valor maior ou igual a zero.")

        cleaned_data["unidade_perda_producao"] = unidade_perda
        return cleaned_data


class TratamentoAntiReflexoForm(forms.ModelForm):
    class Meta:
        model = TratamentoAntiReflexo
        fields = ["nome", "ativo"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nome do tratamento..."}),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class RegraTurnoCoatingForm(forms.ModelForm):
    class Meta:
        model = RegraTurnoCoating
        fields = ["nome", "hora_inicio", "hora_fim", "ativo"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex: Turno 01"}),
            "hora_inicio": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "hora_fim": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class TurnoCoatingForm(forms.ModelForm):
    class Meta:
        model = TurnoCoating
        fields = ["data", "regra", "responsavel"]
        widgets = {
            "data": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "regra": forms.Select(attrs={"class": "form-select"}),
            "responsavel": forms.Select(attrs={"class": "form-select"}),
        }


class NovoLoteCoatingForm(forms.ModelForm):
    data_registro = forms.DateField(
        label="Data do Registro",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    LADO_CHOICES = [
        ('CC', 'Côncavo (CC)'),
        ('CX', 'Convexo (CX)'),
    ]
    lado_entrada = forms.ChoiceField(
        choices=LADO_CHOICES,
        label="Atribuir Entrada a",
        widget=forms.Select(attrs={"class": "form-select"})
    )

    class Meta:
        model = RegistroCoating
        fields = ["maquina", "lote", "tratamento", "hora_entrada"]
        widgets = {
            "maquina": forms.Select(attrs={"class": "form-select"}),
            "lote": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Ex: 12345"}),
            "tratamento": forms.Select(attrs={"class": "form-select"}),
            "hora_entrada": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["maquina"].queryset = Maquina.objects.order_by("codigo", "fabricante")
        self.fields["tratamento"].queryset = TratamentoAntiReflexo.objects.filter(ativo=True).order_by("nome")
        
        # Seta a data de hoje como padrão
        if not self.is_bound and "data_registro" not in self.initial:
            self.initial["data_registro"] = timezone.localdate()


class RegistroCoatingForm(forms.ModelForm):
    class Meta:
        model = RegistroCoating
        fields = [
            "maquina", "lote", "tratamento", "lado", 
            "hora_entrada", "hora_saida", "preparacao", "montagem"
        ]
        widgets = {
            "maquina": forms.Select(attrs={"class": "form-select"}),
            "lote": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Lote..."}),
            "tratamento": forms.Select(attrs={"class": "form-select"}),
            "lado": forms.Select(attrs={"class": "form-select"}),
            "hora_entrada": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "hora_saida": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "preparacao": forms.Select(attrs={"class": "form-select"}),
            "montagem": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["maquina"].queryset = Maquina.objects.order_by("codigo", "fabricante")
        self.fields["tratamento"].queryset = TratamentoAntiReflexo.objects.filter(ativo=True).order_by("nome")
        self.fields["preparacao"].queryset = Colaborador.objects.filter(setor__nome__icontains="laboratorio").order_by("nome_completo")
        self.fields["montagem"].queryset = Colaborador.objects.filter(setor__nome__icontains="laboratorio").order_by("nome_completo")
        
        # Fallback if no matching department for employees
        if not self.fields["preparacao"].queryset.exists():
            self.fields["preparacao"].queryset = Colaborador.objects.all().order_by("nome_completo")
        if not self.fields["montagem"].queryset.exists():
            self.fields["montagem"].queryset = Colaborador.objects.all().order_by("nome_completo")
