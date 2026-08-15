import json

from django import forms

from .models import (
    ComentarioAuditoria,
    ModeloAuditoria,
    PerguntaAuditoria,
    RegistroAuditoria,
    get_pergunta_resposta_preset,
    get_pergunta_resposta_preset_choices,
    list_pergunta_resposta_presets,
)


class ModeloAuditoriaForm(forms.ModelForm):
    class Meta:
        model = ModeloAuditoria
        fields = [
            "nome",
            "objeto_auditoria",
            "responsaveis",
            "periodicidade",
            "dia_semana",
            "dias_quinzenal",
            "dia_mes",
            "link_sharepoint",
            "preenchimento_grid",
            "grid_rotulo_item",
            "grid_colunas",
            "ativo",
        ]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "objeto_auditoria": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "responsaveis": forms.SelectMultiple(attrs={"class": "form-select"}),
            "periodicidade": forms.Select(attrs={"class": "form-select", "id": "id_periodicidade"}),
            "dia_semana": forms.Select(attrs={"class": "form-select", "id": "id_dia_semana"}),
            "dias_quinzenal": forms.TextInput(attrs={"class": "form-control", "id": "id_dias_quinzenal", "placeholder": "Ex: 1,16 ou 5,20"}),
            "dia_mes": forms.NumberInput(attrs={"class": "form-control", "id": "id_dia_mes", "min": "1", "max": "31", "placeholder": "Dia do mÃªs (1-31)"}),
            "link_sharepoint": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://..."}),
            "preenchimento_grid": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "grid_rotulo_item": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex.: Equipamento"}),
            "grid_colunas": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Uma coluna por linha (ex.: EQP-001)\nEQP-002\nEQP-003",
                }
            ),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        
    def clean(self):
        cleaned_data = super().clean()
        periodicidade = cleaned_data.get('periodicidade')
        dia_semana = cleaned_data.get('dia_semana')
        dias_quinzenal = cleaned_data.get('dias_quinzenal')
        dia_mes = cleaned_data.get('dia_mes')
        
        # Validar campos obrigatÃ³rios baseados na periodicidade
        if periodicidade == 'SEMANAL' and not dia_semana:
            self.add_error('dia_semana', 'Este campo Ã© obrigatÃ³rio para periodicidade semanal.')
        
        if periodicidade == 'QUINZENAL' and not dias_quinzenal:
            self.add_error('dias_quinzenal', 'Este campo Ã© obrigatÃ³rio para periodicidade quinzenal.')
        elif periodicidade == 'QUINZENAL' and dias_quinzenal:
            # Validar formato dos dias quinzenais
            try:
                dias = [int(d.strip()) for d in dias_quinzenal.split(',')]
                if len(dias) != 2:
                    self.add_error('dias_quinzenal', 'Informe exatamente 2 dias separados por vÃ­rgula.')
                elif any(d < 1 or d > 31 for d in dias):
                    self.add_error('dias_quinzenal', 'Os dias devem estar entre 1 e 31.')
                elif abs(dias[0] - dias[1]) < 10:
                    self.add_error('dias_quinzenal', 'Os dias devem estar espaÃ§ados em pelo menos 10 dias.')
            except ValueError:
                self.add_error('dias_quinzenal', 'Formato invÃ¡lido. Use nÃºmeros separados por vÃ­rgula (ex: 1,16).')
        
        if periodicidade in ['MENSAL', 'TRIMESTRAL', 'SEMESTRAL', 'ANUAL'] and not dia_mes:
            self.add_error('dia_mes', f'Este campo Ã© obrigatÃ³rio para periodicidade {periodicidade.lower()}.')
        
        return cleaned_data


class PerguntaAuditoriaForm(forms.ModelForm):
    conjunto_resposta_padrao = forms.ChoiceField(
        required=False,
        choices=[("", "â")] + get_pergunta_resposta_preset_choices(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    opcoes_resposta_cores = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = PerguntaAuditoria
        fields = [
            "modelo",
            "topico",
            "pergunta",
            "descricao_detalhada",
            "tipo_resposta",
            "preenchimento_semanal",
            "opcoes_resposta",
            "opcoes_resposta_cores",
            "exibir_grafico",
            "aplicar_no_grid",
            "ordem",
            "obrigatoria",
            "ativo",
        ]
        widgets = {
            "modelo": forms.Select(attrs={"class": "form-select"}),
            "topico": forms.Select(attrs={"class": "form-select"}),
            "pergunta": forms.TextInput(attrs={"class": "form-control"}),
            "descricao_detalhada": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Descreva detalhadamente como responder esta pergunta...",
                }
            ),
            "tipo_resposta": forms.Select(attrs={"class": "form-select"}),
            "preenchimento_semanal": forms.Select(attrs={"class": "form-select"}),
            "opcoes_resposta": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Uma opÃ§Ã£o por linha (ex.: Conforme)\nNÃ£o conforme\nN/A",
                }
            ),
            "exibir_grafico": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "aplicar_no_grid": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "ordem": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "obrigatoria": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.is_bound and getattr(self.instance, "pk", None):
            instance_colors = getattr(self.instance, "opcoes_resposta_cores", {})
            for preset in list_pergunta_resposta_presets():
                if getattr(self.instance, "tipo_resposta", "") != preset["tipo_resposta"]:
                    continue
                if getattr(self.instance, "opcoes_resposta_list", []) != preset["opcoes_resposta"]:
                    continue
                if dict(instance_colors or {}) != preset["opcoes_resposta_cores"]:
                    continue
                if bool(getattr(self.instance, "exibir_grafico", True)) != preset["exibir_grafico"]:
                    continue
                if bool(getattr(self.instance, "aplicar_no_grid", True)) != preset["aplicar_no_grid"]:
                    continue
                self.initial["conjunto_resposta_padrao"] = preset["key"]
                break

        if not self.is_bound:
            current_colors = getattr(self.instance, "opcoes_resposta_cores", {})
            if isinstance(current_colors, dict):
                self.initial["opcoes_resposta_cores"] = json.dumps(current_colors, ensure_ascii=False)

        modelo_id = None
        if self.is_bound:
            modelo_id = (self.data.get("modelo") or "").strip()
        if not modelo_id:
            initial_modelo = (self.initial.get("modelo") if hasattr(self, "initial") else None)
            modelo_id = str(initial_modelo).strip() if initial_modelo else ""
        if not modelo_id and getattr(self.instance, "modelo_id", None):
            modelo_id = str(self.instance.modelo_id)

        current_value = getattr(self.instance, "topico_id", None)

        from .models import TopicoAuditoria
        choices = [("", "-")]
        if modelo_id and str(modelo_id).isdigit():
            try:
                topicos = TopicoAuditoria.objects.filter(modelo_id=int(modelo_id)).order_by("parent__ordem", "ordem", "nome")
                for topico in topicos:
                    choices.append((topico.id, topico.get_full_name()))
            except Exception:
                pass

        # Expose the current value to the template/JS to avoid losing it on dynamic refresh
        try:
            self.fields["topico"].widget.attrs["data-current"] = current_value or ""
        except Exception:
            pass

        self.fields["topico"].choices = choices

    def clean(self):
        cleaned_data = super().clean()
        modelo = cleaned_data.get("modelo")
        topico = cleaned_data.get("topico")
        conjunto_resposta_padrao = (cleaned_data.get("conjunto_resposta_padrao") or "").strip()

        preset = None
        if conjunto_resposta_padrao:
            preset = get_pergunta_resposta_preset(conjunto_resposta_padrao)
            if not preset:
                self.add_error("conjunto_resposta_padrao", "Conjunto padrÃ£o invÃ¡lido.")
            else:
                cleaned_data["tipo_resposta"] = preset["tipo_resposta"]
                cleaned_data["opcoes_resposta"] = preset["opcoes_resposta_texto"]
                cleaned_data["opcoes_resposta_cores"] = dict(preset["opcoes_resposta_cores"])
                cleaned_data["exibir_grafico"] = preset["exibir_grafico"]
                cleaned_data["aplicar_no_grid"] = preset["aplicar_no_grid"]

        tipo_resposta = cleaned_data.get("tipo_resposta")
        opcoes_resposta = (cleaned_data.get("opcoes_resposta") or "").strip()
        opcoes_resposta_cores_value = cleaned_data.get("opcoes_resposta_cores") or ""

        if modelo and topico:
            if topico.modelo_id != modelo.id:
                self.add_error(
                    "topico",
                    "TÃ³pico invÃ¡lido para este modelo.",
                )

        values = [v.strip() for v in opcoes_resposta.replace("\r\n", "\n").split("\n") if v.strip()]
        if tipo_resposta == "LISTA":
            if not values:
                self.add_error("opcoes_resposta", "Informe pelo menos 1 opÃ§Ã£o para o tipo 'Lista (opÃ§Ãµes)'.")

        parsed_colors = {}
        if isinstance(opcoes_resposta_cores_value, dict):
            parsed_colors = dict(opcoes_resposta_cores_value)
        else:
            opcoes_resposta_cores_raw = str(opcoes_resposta_cores_value or "").strip()
            if opcoes_resposta_cores_raw:
                try:
                    raw_map = json.loads(opcoes_resposta_cores_raw)
                    if isinstance(raw_map, dict):
                        parsed_colors = raw_map
                except Exception:
                    self.add_error("opcoes_resposta", "Falha ao processar as cores das opÃ§Ãµes.")

        if tipo_resposta == "SIM_NAO":
            cleaned_data["opcoes_resposta_cores"] = {
                "Sim": "#198754",
                "NÃ£o": "#dc3545",
            }
            return cleaned_data

        if tipo_resposta == "LISTA":
            values_by_key = {
                PerguntaAuditoria._normalize_option_key(v): v
                for v in values
            }
            cleaned_map = {}
            for raw_key, raw_color in parsed_colors.items():
                key = PerguntaAuditoria._normalize_option_key(raw_key)
                color = str(raw_color or "").strip().lower()
                if not key or not color:
                    continue
                if key not in values_by_key:
                    continue
                if not PerguntaAuditoria._is_hex_color(color):
                    self.add_error("opcoes_resposta", f"Cor invÃ¡lida para a opÃ§Ã£o '{values_by_key[key]}'.")
                    continue
                cleaned_map[values_by_key[key]] = color
            cleaned_data["opcoes_resposta_cores"] = cleaned_map
        else:
            cleaned_data["opcoes_resposta_cores"] = {}
        return cleaned_data


class RegistroAuditoriaForm(forms.ModelForm):
    class Meta:
        model = RegistroAuditoria
        fields = ["nome", "alvo", "periodo_inicio", "periodo_fim", "grid_itens", "observacoes"]
        widgets = {
            "data_auditoria": forms.DateInput(
                format="%d/%m/%Y",
                attrs={
                    "class": "form-control js-week-datepicker",
                    "type": "text",
                    "placeholder": "dd/mm/aaaa",
                    "autocomplete": "off",
                },
            ),
            "periodo_inicio": forms.DateInput(
                format="%d/%m/%Y",
                attrs={
                    "class": "form-control js-week-datepicker",
                    "type": "text",
                    "placeholder": "dd/mm/aaaa",
                    "autocomplete": "off",
                },
            ),
            "periodo_fim": forms.DateInput(
                format="%d/%m/%Y",
                attrs={
                    "class": "form-control js-week-datepicker",
                    "type": "text",
                    "placeholder": "dd/mm/aaaa",
                    "autocomplete": "off",
                },
            ),
            "nome": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ex: Ciclo Semanal - Janeiro",
                    "maxlength": 150,
                }
            ),
            "alvo": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ex: Setor Comercial, Equipamento X",
                    "maxlength": 150,
                }
            ),
            "grid_itens": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Um item por linha (ex.: EQP-001)\nEQP-002\nEQP-003",
                }
            ),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        accepted_formats = ["%d/%m/%Y", "%Y-%m-%d"]
        for field_name in ("periodo_inicio", "periodo_fim"):
            self.fields[field_name].input_formats = accepted_formats

    def clean(self):
        cleaned_data = super().clean()
        periodo_inicio = cleaned_data.get("periodo_inicio")
        periodo_fim = cleaned_data.get("periodo_fim")
        if periodo_inicio and periodo_fim and periodo_fim < periodo_inicio:
            self.add_error("periodo_fim", "O perÃ­odo final deve ser maior ou igual ao perÃ­odo inicial.")
        return cleaned_data


class ComentarioAuditoriaForm(forms.ModelForm):
    class Meta:
        model = ComentarioAuditoria
        fields = ["texto"]
        widgets = {
            "texto": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
        }

    def clean_texto(self):
        texto = (self.cleaned_data.get("texto") or "").strip()
        if not texto:
            raise forms.ValidationError("Informe um comentÃ¡rio.")
        if len(texto) > 8000:
            raise forms.ValidationError("ComentÃ¡rio muito longo (mÃ¡x. 8000 caracteres).")
        return texto
from django.urls import path
from .models import (
    Norma,
    ItemNorma,
    BancoPergunta,
    AuditoriaIso,
    AgendaAuditoriaIso,
)

# ==========================================
# FORMS ISO 13485
# ==========================================

class NormaIsoForm(forms.ModelForm):
    class Meta:
        model = Norma
        fields = ['codigo', 'descricao']
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: ISO 13485:2016'}),
            'descricao': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Sistemas de Gestão da Qualidade'}),
        }


class ItemNormaIsoForm(forms.ModelForm):
    class Meta:
        model = ItemNorma
        fields = ['norma', 'referencia', 'titulo', 'descricao', 'ordem']
        widgets = {
            'norma': forms.Select(attrs={'class': 'form-select'}),
            'referencia': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 4.1.1'}),
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'ordem': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class BancoPerguntaIsoForm(forms.ModelForm):
    class Meta:
        model = BancoPergunta
        fields = ['texto_pergunta', 'dica_auditor', 'itens_norma']
        widgets = {
            'texto_pergunta': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Como a organização...?'}),
            'dica_auditor': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Verifique o documento X...'}),
            'itens_norma': forms.SelectMultiple(attrs={'class': 'form-select', 'size': 6}),
        }


class AgendaAuditoriaIsoForm(forms.ModelForm):
    class Meta:
        model = AgendaAuditoriaIso
        fields = ['titulo', 'data', 'hora_inicio', 'hora_fim', 'itens_norma']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Entrevista com a Diretoria'}),
            'data': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'hora_inicio': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'hora_fim': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'itens_norma': forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input iso-item-checkbox'}),
        }

class AgendaPerguntasForm(forms.ModelForm):
    class Meta:
        model = AgendaAuditoriaIso
        fields = ['perguntas']
        widgets = {
            'perguntas': forms.SelectMultiple(attrs={'class': 'form-select select2-multiple'}),
        }

class AuditoriaIsoForm(forms.ModelForm):
    class Meta:
        model = AuditoriaIso
        fields = ['norma', 'auditores', 'data_inicio', 'data_fim', 'escopo_itens']
        widgets = {
            'norma': forms.Select(attrs={'class': 'form-select'}),
            'auditores': forms.SelectMultiple(attrs={'class': 'form-select select2-multiple'}),
            'data_inicio': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'data_fim': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'escopo_itens': forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input iso-item-checkbox'}),
        }
