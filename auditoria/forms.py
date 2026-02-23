from django import forms

from .models import ModeloAuditoria, PerguntaAuditoria, RegistroAuditoria


class ModeloAuditoriaForm(forms.ModelForm):
    class Meta:
        model = ModeloAuditoria
        fields = ["nome", "objeto_auditoria", "responsavel", "periodicidade", "dia_semana", "dias_quinzenal", "dia_mes", "link_sharepoint", "ativo"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "objeto_auditoria": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "responsavel": forms.Select(attrs={"class": "form-select"}),
            "periodicidade": forms.Select(attrs={"class": "form-select", "id": "id_periodicidade"}),
            "dia_semana": forms.Select(attrs={"class": "form-select", "id": "id_dia_semana"}),
            "dias_quinzenal": forms.TextInput(attrs={"class": "form-control", "id": "id_dias_quinzenal", "placeholder": "Ex: 1,16 ou 5,20"}),
            "dia_mes": forms.NumberInput(attrs={"class": "form-control", "id": "id_dia_mes", "min": "1", "max": "31", "placeholder": "Dia do mês (1-31)"}),
            "link_sharepoint": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://..."}),
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
        fields = ["modelo", "pergunta", "tipo_resposta", "preenchimento_semanal", "ordem", "obrigatoria", "ativo"]
        widgets = {
            "modelo": forms.Select(attrs={"class": "form-select"}),
            "pergunta": forms.TextInput(attrs={"class": "form-control"}),
            "tipo_resposta": forms.Select(attrs={"class": "form-select"}),
            "preenchimento_semanal": forms.Select(attrs={"class": "form-select"}),
            "ordem": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "obrigatoria": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class RegistroAuditoriaForm(forms.ModelForm):
    class Meta:
        model = RegistroAuditoria
        fields = ["data_auditoria", "periodo_inicio", "periodo_fim", "observacoes"]
        widgets = {
            "data_auditoria": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "periodo_inicio": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "periodo_fim": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        periodo_inicio = cleaned_data.get("periodo_inicio")
        periodo_fim = cleaned_data.get("periodo_fim")
        if periodo_inicio and periodo_fim and periodo_fim < periodo_inicio:
            self.add_error("periodo_fim", "O período final deve ser maior ou igual ao período inicial.")
        return cleaned_data
