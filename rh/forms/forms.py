
from django import forms
from rh.models import Colaborador, Ocorrencia, Ferias

class FeriasForm(forms.ModelForm):
    class Meta:
        model = Ferias
        fields = [
            "status",
            "data_inicio",
            "data_fim",
            "dias_solicitados",
            "aprovada",
            "abono_salarial",
            "adiantamento_13",
            "descricao"
        ]
        widgets = {
            "status": forms.Select(attrs={"class": "form-select"}),
            "data_inicio": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "data_fim": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "dias_solicitados": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "aprovada": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "abono_salarial": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "adiantamento_13": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "descricao": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        data_inicio = cleaned_data.get('data_inicio')
        abono = cleaned_data.get('abono_salarial')
        adiantamento = cleaned_data.get('adiantamento_13')

        if data_inicio:
            from rh.models import ConfiguracaoFerias
            config = ConfiguracaoFerias.get_config()
            mes = data_inicio.month
            if abono and not config.permite_abono(mes):
                self.add_error('abono_salarial', f'Abono Salarial não é permitido para o mês {mes}.')
                cleaned_data['abono_salarial'] = False
            if adiantamento and not config.permite_adiantamento_13(mes):
                self.add_error('adiantamento_13', f'Adiantamento de 13º Salário não é permitido para o mês {mes}.')
                cleaned_data['adiantamento_13'] = False

        return cleaned_data

class VencimentoFeriasForm(forms.ModelForm):
    class Meta:
        from rh.models import VencimentoFerias
        model = VencimentoFerias
        fields = [
            "data_inicio_aquisitivo",
            "data_fim_aquisitivo",
            "data_limite_gozo",
            "dias_direito",
            "observacoes"
        ]
        widgets = {
            "data_inicio_aquisitivo": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "data_fim_aquisitivo": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "data_limite_gozo": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "dias_direito": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

# -*- coding: utf-8 -*-
"""
Forms para RH Module
"""

from django import forms
from rh.models import Colaborador, Ocorrencia


class ColaboradorForm(forms.ModelForm):
    """Formulário para editar dados de colaborador."""
    
    class Meta:
        model = Colaborador
        fields = "__all__"
        exclude = ["user_django", "criado_em", "centro_custo", "pacotes_treinamento"]
        widgets = {
            "nome_completo": forms.TextInput(attrs={"class": "form-control"}),
            "matricula": forms.TextInput(attrs={"class": "form-control"}),
            "matricula_global": forms.TextInput(attrs={"class": "form-control"}),
            "cpf": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "000.000.000-00"
            }),
            "cargo": forms.TextInput(attrs={"class": "form-control"}),
            "posto_trabalho": forms.TextInput(attrs={"class": "form-control"}),
            "grupo": forms.TextInput(attrs={"class": "form-control"}),

            "setor": forms.Select(attrs={"class": "form-select"}),
            "turno": forms.Select(attrs={"class": "form-select"}),
            "posto_lideranca": forms.Select(attrs={"class": "form-select"}),
            "lider": forms.Select(attrs={"class": "form-select"}),
            "supervisor": forms.Select(attrs={"class": "form-select"}),
            "gerente": forms.Select(attrs={"class": "form-select"}),
            "salario": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "0.01"
            }),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "em_ferias": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 1. Filtrar lider (Líder / Superior Direto) para mostrar Colaboradores com posto_lideranca em ["LIDER", "SUPERVISOR", "GERENTE"]
        lider_qs = Colaborador.objects.filter(posto_lideranca__in=["LIDER", "SUPERVISOR", "GERENTE"], is_active=True)
        if self.instance and self.instance.lider_id:
            lider_qs = lider_qs | Colaborador.objects.filter(pk=self.instance.lider_id)
        self.fields['lider'].queryset = lider_qs.distinct().order_by('nome_completo')
        
        # 2. Filtrar supervisor para mostrar Colaboradores com posto_lideranca em ["SUPERVISOR", "GERENTE"]
        supervisor_qs = Colaborador.objects.filter(posto_lideranca__in=["SUPERVISOR", "GERENTE"], is_active=True)
        if self.instance and self.instance.supervisor_id:
            supervisor_qs = supervisor_qs | Colaborador.objects.filter(pk=self.instance.supervisor_id)
        self.fields['supervisor'].queryset = supervisor_qs.distinct().order_by('nome_completo')
        
        # 3. Filtrar gerente (Coordenador / Gerente) para mostrar apenas Colaboradores com posto_lideranca="GERENTE"
        gerente_qs = Colaborador.objects.filter(posto_lideranca="GERENTE", is_active=True)
        if self.instance and self.instance.gerente_id:
            gerente_qs = gerente_qs | Colaborador.objects.filter(pk=self.instance.gerente_id)
        self.fields['gerente'].queryset = gerente_qs.distinct().order_by('nome_completo')


class OcorrenciaForm(forms.ModelForm):
    """Formulário para registrar ocorrências de RH."""
    
    class Meta:
        model = Ocorrencia
        fields = ['colaborador', 'condutor', 'data_ocorrencia', 'tipo', 'natureza', 'descricao', 'motivo', 'arquivo_evidencia']
        widgets = {
            'colaborador': forms.Select(attrs={'class': 'form-select'}),
            'condutor': forms.Select(attrs={'class': 'form-select'}),
            'data_ocorrencia': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'natureza': forms.Select(attrs={'class': 'form-select'}),
            'descricao': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control',
                'placeholder': 'Descreva a ocorrência em detalhes'
            }),
            'motivo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Motivo da ocorrência'
            }),
            'arquivo_evidencia': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.jpeg,.png,.doc,.docx'
            }),
        }


class ImportacaoColaboradoresForm(forms.Form):
    """Formulário para importação em massa de colaboradores."""
    
    arquivo_excel = forms.FileField(
        label="Planilha de Colaboradores",
        widget=forms.FileInput(attrs={
            "class": "form-control",
            "accept": ".xlsx, .xls"
        }),
    )


class ImportacaoHierarquiaForm(forms.Form):
    """Formulário para importação em massa de hierarquia."""
    
    arquivo_excel = forms.FileField(
        label="Planilha de Hierarquia",
        widget=forms.FileInput(attrs={
            "class": "form-control",
            "accept": ".xlsx, .xls"
        }),
    )


class ImportacaoFeriasForm(forms.Form):
    """Formulário para importação em massa de férias."""
    
    arquivo_excel = forms.FileField(
        label="Selecione a Planilha de Férias (.xlsx ou .csv)",
        widget=forms.ClearableFileInput(attrs={"class": "form-control"}),
    )


class PlanejamentoHoraExtraForm(forms.ModelForm):
    data_hora_inicio = forms.DateTimeField(
        label="Data/Hora Início",
        required=True,
        widget=forms.DateTimeInput(attrs={
            "class": "form-control",
            "type": "datetime-local"
        })
    )
    data_hora_fim = forms.DateTimeField(
        label="Data/Hora Fim",
        required=True,
        widget=forms.DateTimeInput(attrs={
            "class": "form-control",
            "type": "datetime-local"
        })
    )
    motivos = forms.ModelMultipleChoiceField(
        queryset=None,
        widget=forms.CheckboxSelectMultiple(),
        required=False,
        label="Motivos Categorizados"
    )

    class Meta:
        from rh.models import PlanejamentoHoraExtra
        model = PlanejamentoHoraExtra
        fields = ["tipo", "data_hora_inicio", "data_hora_fim", "motivos", "motivo", "colaboradores"]
        widgets = {
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "motivo": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Detalhamento adicional / descrição livre..."
            }),
            "colaboradores": forms.SelectMultiple(attrs={
                "class": "form-select",
                "size": "8"
            })
        }

    def __init__(self, *args, **kwargs):
        usuario_logado = kwargs.pop('usuario_logado', None)
        super().__init__(*args, **kwargs)
        
        # Carregar queryset de motivos
        from rh.models import MotivoPlanejamento
        self.fields['motivos'].queryset = MotivoPlanejamento.objects.all()
        
        # Preencher o valor inicial formatado para datetime-local
        if self.instance and self.instance.pk:
            if self.instance.data_hora_inicio:
                self.initial['data_hora_inicio'] = self.instance.data_hora_inicio.strftime('%Y-%m-%dT%H:%M')
            if self.instance.data_hora_fim:
                self.initial['data_hora_fim'] = self.instance.data_hora_fim.strftime('%Y-%m-%dT%H:%M')
            
        # Filtrar colaboradores com base nas permissões de acesso e status ativo
        if usuario_logado:
            from rh.views.views import get_colaboradores_acessiveis
            qs = get_colaboradores_acessiveis(usuario_logado)
        else:
            from rh.models import Colaborador
            qs = Colaborador.objects.all()

        from django.db.models import Q
        q_filter = Q(is_active=True, afastado=False)
        if self.instance and self.instance.pk:
            q_filter |= Q(id__in=self.instance.colaboradores.values_list('id', flat=True))
            
        self.fields['colaboradores'].queryset = qs.filter(q_filter).order_by('nome_completo')

    def clean(self):
        cleaned_data = super().clean()
        inicio = cleaned_data.get('data_hora_inicio')
        fim = cleaned_data.get('data_hora_fim')
        
        if inicio and fim and fim <= inicio:
            raise forms.ValidationError("A data/hora de fim deve ser posterior à data/hora de início.")
        return cleaned_data


class MotivoPlanejamentoForm(forms.ModelForm):
    class Meta:
        from rh.models import MotivoPlanejamento
        model = MotivoPlanejamento
        fields = ["nome", "tipo"]
        widgets = {
            "nome": forms.TextInput(attrs={
                "class": "form-control", 
                "placeholder": "Ex: Inventário, Treinamento, etc."
            }),
            "tipo": forms.Select(attrs={
                "class": "form-select"
            }),
        }


