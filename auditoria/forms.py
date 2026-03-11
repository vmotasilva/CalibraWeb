from django import forms

from .models import ComentarioAuditoria, ModeloAuditoria, PerguntaAuditoria, RegistroAuditoria


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
            "subcategorias",
            "ativo",
        ]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "objeto_auditoria": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "responsaveis": forms.SelectMultiple(attrs={"class": "form-select"}),
            "periodicidade": forms.Select(attrs={"class": "form-select", "id": "id_periodicidade"}),
            "dia_semana": forms.Select(attrs={"class": "form-select", "id": "id_dia_semana"}),
            "dias_quinzenal": forms.TextInput(attrs={"class": "form-control", "id": "id_dias_quinzenal", "placeholder": "Ex: 1,16 ou 5,20"}),
            "dia_mes": forms.NumberInput(attrs={"class": "form-control", "id": "id_dia_mes", "min": "1", "max": "31", "placeholder": "Dia do mês (1-31)"}),
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
            "subcategorias": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Uma sub-categoria por linha (ex.: Segurança)\nQualidade\n5S",
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
        
        # Validar campos obrigatórios baseados na periodicidade
        if periodicidade == 'SEMANAL' and not dia_semana:
            self.add_error('dia_semana', 'Este campo é obrigatório para periodicidade semanal.')
        
        if periodicidade == 'QUINZENAL' and not dias_quinzenal:
            self.add_error('dias_quinzenal', 'Este campo é obrigatório para periodicidade quinzenal.')
        elif periodicidade == 'QUINZENAL' and dias_quinzenal:
            # Validar formato dos dias quinzenais
            try:
                dias = [int(d.strip()) for d in dias_quinzenal.split(',')]
                if len(dias) != 2:
                    self.add_error('dias_quinzenal', 'Informe exatamente 2 dias separados por vírgula.')
                elif any(d < 1 or d > 31 for d in dias):
                    self.add_error('dias_quinzenal', 'Os dias devem estar entre 1 e 31.')
                elif abs(dias[0] - dias[1]) < 10:
                    self.add_error('dias_quinzenal', 'Os dias devem estar espaçados em pelo menos 10 dias.')
            except ValueError:
                self.add_error('dias_quinzenal', 'Formato inválido. Use números separados por vírgula (ex: 1,16).')
        
        if periodicidade in ['MENSAL', 'TRIMESTRAL', 'SEMESTRAL', 'ANUAL'] and not dia_mes:
            self.add_error('dia_mes', f'Este campo é obrigatório para periodicidade {periodicidade.lower()}.')
        
        return cleaned_data


class PerguntaAuditoriaForm(forms.ModelForm):
    class Meta:
        model = PerguntaAuditoria
        fields = [
            "modelo",
            "subcategoria",
            "pergunta",
            "descricao_detalhada",
            "tipo_resposta",
            "preenchimento_semanal",
            "opcoes_resposta",
            "aplicar_no_grid",
            "ordem",
            "obrigatoria",
            "ativo",
        ]
        widgets = {
            "modelo": forms.Select(attrs={"class": "form-select"}),
            "subcategoria": forms.Select(attrs={"class": "form-select"}),
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
                    "placeholder": "Uma opção por linha (ex.: Conforme)\nNão conforme\nN/A",
                }
            ),
            "aplicar_no_grid": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "ordem": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "obrigatoria": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        modelo_id = None
        if self.is_bound:
            modelo_id = (self.data.get("modelo") or "").strip()
        if not modelo_id:
            initial_modelo = (self.initial.get("modelo") if hasattr(self, "initial") else None)
            modelo_id = str(initial_modelo).strip() if initial_modelo else ""
        if not modelo_id and getattr(self.instance, "modelo_id", None):
            modelo_id = str(self.instance.modelo_id)

        current_value = (getattr(self.instance, "subcategoria", "") or "").strip()

        choices = [("", "—")]
        if modelo_id and str(modelo_id).isdigit():
            try:
                modelo = ModeloAuditoria.objects.get(pk=int(modelo_id))
                choices += [(c, c) for c in modelo.subcategorias_list]
            except ModeloAuditoria.DoesNotExist:
                pass

        # Preserve current value even if it's not in the model list
        if current_value:
            existing_lower = {str(v or "").strip().lower() for (v, _label) in choices if v}
            if current_value.lower() not in existing_lower:
                choices.insert(1, (current_value, current_value))

        # Expose the current value to the template/JS to avoid losing it on dynamic refresh
        try:
            self.fields["subcategoria"].widget.attrs["data-current"] = current_value
        except Exception:
            pass

        self.fields["subcategoria"].choices = choices

    def clean(self):
        cleaned_data = super().clean()
        modelo = cleaned_data.get("modelo")
        subcategoria = (cleaned_data.get("subcategoria") or "").strip()
        tipo_resposta = cleaned_data.get("tipo_resposta")
        opcoes_resposta = (cleaned_data.get("opcoes_resposta") or "").strip()

        if modelo and subcategoria:
            allowed = getattr(modelo, "subcategorias_list", []) or []
            if allowed:
                allowed_lower = {a.lower() for a in allowed}
                if subcategoria.lower() not in allowed_lower:
                    self.add_error(
                        "subcategoria",
                        "Sub-categoria inválida para este modelo. Cadastre a sub-categoria no modelo e selecione-a aqui.",
                    )

        if tipo_resposta == "LISTA":
            values = [v.strip() for v in opcoes_resposta.replace("\r\n", "\n").split("\n") if v.strip()]
            if not values:
                self.add_error("opcoes_resposta", "Informe pelo menos 1 opção para o tipo 'Lista (opções)'.")
        return cleaned_data


class RegistroAuditoriaForm(forms.ModelForm):
    class Meta:
        model = RegistroAuditoria
        fields = ["data_auditoria", "periodo_inicio", "periodo_fim", "item_os", "grid_itens", "observacoes"]
        widgets = {
            "data_auditoria": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "periodo_inicio": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "periodo_fim": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "item_os": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ex: OS 12345 / Item 7",
                    "maxlength": 120,
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

    def clean(self):
        cleaned_data = super().clean()
        periodo_inicio = cleaned_data.get("periodo_inicio")
        periodo_fim = cleaned_data.get("periodo_fim")
        if periodo_inicio and periodo_fim and periodo_fim < periodo_inicio:
            self.add_error("periodo_fim", "O período final deve ser maior ou igual ao período inicial.")
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
            raise forms.ValidationError("Informe um comentário.")
        if len(texto) > 8000:
            raise forms.ValidationError("Comentário muito longo (máx. 8000 caracteres).")
        return texto
