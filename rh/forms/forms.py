
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
            "vencimento",
            "descricao"
        ]
        widgets = {
            "status": forms.Select(attrs={"class": "form-select"}),
            "data_inicio": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "data_fim": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "dias_solicitados": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "aprovada": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "vencimento": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "descricao": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
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
            "cpf": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "000.000.000-00"
            }),
            "cargo": forms.TextInput(attrs={"class": "form-control"}),
            "grupo": forms.TextInput(attrs={"class": "form-control"}),
            "setor": forms.Select(attrs={"class": "form-select"}),
            "turno": forms.Select(attrs={"class": "form-select"}),
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
    horas_extras_str = forms.CharField(
        label="Duração de Horas Extras (hh:mm:ss)",
        required=True,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Ex: 02:00:00"
        })
    )

    class Meta:
        from rh.models import PlanejamentoHoraExtra
        model = PlanejamentoHoraExtra
        fields = ["data", "motivo", "colaboradores"]
        widgets = {
            "data": forms.DateInput(attrs={
                "class": "form-control",
                "type": "date"
            }),
            "motivo": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ex: Inventário Anual"
            }),
            "colaboradores": forms.SelectMultiple(attrs={
                "class": "form-select",
                "size": "8"
            })
        }

    def __init__(self, *args, **kwargs):
        usuario_logado = kwargs.pop('usuario_logado', None)
        super().__init__(*args, **kwargs)
        
        # Preencher o valor inicial de horas_extras_str a partir do DurationField
        if self.instance and self.instance.pk and self.instance.horas_extras:
            total_seconds = int(self.instance.horas_extras.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            self.initial['horas_extras_str'] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
        # Filtrar colaboradores com base nas permissões de acesso
        if usuario_logado:
            from rh.views.views import get_colaboradores_acessiveis
            self.fields['colaboradores'].queryset = get_colaboradores_acessiveis(usuario_logado).order_by('nome_completo')
        else:
            from rh.models import Colaborador
            self.fields['colaboradores'].queryset = Colaborador.objects.all().order_by('nome_completo')

    def clean_horas_extras_str(self):
        val = self.cleaned_data.get('horas_extras_str', '').strip()
        if not val:
            raise forms.ValidationError("Duração é obrigatória.")
        
        import re
        from datetime import timedelta
        
        match_hms = re.match(r'^(\d+):([0-5]\d):([0-5]\d)$', val)
        if match_hms:
            hours, minutes, seconds = map(int, match_hms.groups())
            return timedelta(hours=hours, minutes=minutes, seconds=seconds)
        
        match_hm = re.match(r'^(\d+):([0-5]\d)$', val)
        if match_hm:
            hours, minutes = map(int, match_hm.groups())
            return timedelta(hours=hours, minutes=minutes)
            
        raise forms.ValidationError("Formato inválido. Use hh:mm:ss ou hh:mm.")

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.horas_extras = self.cleaned_data['horas_extras_str']
        if commit:
            instance.save()
            self.save_m2m()
        return instance

