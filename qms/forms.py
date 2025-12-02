from django import forms

from .models import (Colaborador, Instrumento, Ocorrencia,
                     OcorrenciaInstrumento, OrdemCalibracao, Padrao,
                     SolicitacaoInstrumento, Procedimento, Area, RegistroTreinamento,
                     HistoricoCalibracao, Fornecedor, FaixaMedicao)




# --- FORMULÁRIOS DE IMPORTAÇÃO ---


class ImportacaoInstrumentosForm(forms.Form):
    arquivo_excel = forms.FileField(
        label="Planilha de Instrumentos",
        widget=forms.FileInput(
            attrs={"class": "form-control", "accept": ".xlsx, .xls, .csv"}
        ),
    )


class ImportacaoColaboradoresForm(forms.Form):
    arquivo_excel = forms.FileField(
        label="Planilha de Colaboradores",
        widget=forms.FileInput(
            attrs={"class": "form-control", "accept": ".xlsx, .xls"}
        ),
    )


class ImportacaoProcedimentosForm(forms.Form):
    arquivo_excel = forms.FileField(
        label="Planilha de Procedimentos",
        widget=forms.FileInput(
            attrs={"class": "form-control", "accept": ".xlsx, .xls"}
        ),
    )


class ImportacaoHierarquiaForm(forms.Form):
    arquivo_excel = forms.FileField(
        label="Planilha de Hierarquia",
        widget=forms.FileInput(
            attrs={"class": "form-control", "accept": ".xlsx, .xls"}
        ),
    )


class ImportacaoHistoricoForm(forms.Form):
    arquivo_excel = forms.FileField(
        label="Histórico de Calibrações",
        widget=forms.FileInput(
            attrs={"class": "form-control", "accept": ".xlsx, .xls, .csv"}
        ),
        help_text="Colunas obrigatórias: CÓDIGO (ou TAG), DATA CALIBRAÇÃO, DATA APROVAÇÃO, N CERTIFICADO, RESULTADO",
    )


class ImportacaoPadroesForm(forms.Form):
    arquivo_excel = forms.FileField(
        label="Planilha de Padrões (Kits)",
        widget=forms.FileInput(
            attrs={"class": "form-control", "accept": ".xlsx, .xls, .csv"}
        ),
    )


class ColaboradorForm(forms.ModelForm):
    class Meta:
        model = Colaborador
        fields = "__all__"  # Permite editar tudo (exceto campos automáticos)
        exclude = ["user_django", "criado_em"]  # Protege o login e data de criação
        widgets = {
            "nome_completo": forms.TextInput(attrs={"class": "form-control"}),
            "matricula": forms.TextInput(attrs={"class": "form-control"}),
            "cpf": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "000.000.000-00"}
            ),
            "cargo": forms.TextInput(attrs={"class": "form-control"}),
            "grupo": forms.TextInput(attrs={"class": "form-control"}),
            "setor": forms.Select(attrs={"class": "form-select"}),
            "centro_custo": forms.Select(attrs={"class": "form-select"}),
            "turno": forms.Select(attrs={"class": "form-select"}),
            "lider": forms.Select(attrs={"class": "form-select"}),
            "supervisor": forms.Select(attrs={"class": "form-select"}),
            "gerente": forms.Select(attrs={"class": "form-select"}),
            "salario": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "em_ferias": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "pacotes_treinamento": forms.SelectMultiple(
                attrs={"class": "form-control", "style": "height: 150px;"}
            ),
        }


class ImportacaoFeriasForm(forms.Form):
    arquivo_excel = forms.FileField(
        label="Selecione a Planilha de Férias (.xlsx ou .csv)",
        widget=forms.ClearableFileInput(attrs={"class": "form-control"}),
    )


# --- NOVOS FORMULÁRIOS (VERIFIQUE SE ESTÃO AQUI) ---


class DateInput(forms.DateInput):
    input_type = "date"


class InstrumentoForm(forms.ModelForm):
    class Meta:
        model = Instrumento
        fields = [
            'tag','descricao','categoria','setor','fabricante','modelo','serie','frequencia_meses','ativo'
        ]
        widgets = {
            'tag': forms.TextInput(attrs={'class':'form-control','placeholder':'TAG / Código'}),
            'descricao': forms.TextInput(attrs={'class':'form-control','placeholder':'Descrição do instrumento'}),
            'categoria': forms.Select(attrs={'class':'form-select'}),
            'setor': forms.Select(attrs={'class':'form-select'}),
            'fabricante': forms.TextInput(attrs={'class':'form-control'}),
            'modelo': forms.TextInput(attrs={'class':'form-control'}),
            'serie': forms.TextInput(attrs={'class':'form-control'}),
            'frequencia_meses': forms.NumberInput(attrs={'class':'form-control','min':'0','step':'1'}),
            'ativo': forms.CheckboxInput(attrs={'class':'form-check-input'}),
        }


class SolicitacaoForm(forms.ModelForm):
    class Meta:
        model = SolicitacaoInstrumento
        fields = ["tipo", "instrumento_alvo", "motivo"]
        widgets = {
            "motivo": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": "form-control",
                    "placeholder": "Explique a necessidade...",
                }
            ),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "instrumento_alvo": forms.Select(attrs={"class": "form-select"}),
        }


class OcorrenciaForm(forms.ModelForm):
    class Meta:
        model = Ocorrencia
        fields = ['colaborador', 'data_ocorrencia', 'tipo', 'titulo', 'descricao', 'arquivo_evidencia']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'colaborador': forms.Select(attrs={'class': 'form-select'}),
            'data_ocorrencia': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class ProcedimentoForm(forms.ModelForm):
    class Meta:
        model = Procedimento
        fields = [
            'codigo', 'nome', 'descricao', 'pasta', 'classificacao', 'autor',
            'numero_revisao', 'ultima_revisao', 'data_aprovacao', 'proxima_revisao',
            'data_validade', 'documentos_controlados', 'matriz', 'sub_area'
        ]
        widgets = {
            'codigo': forms.TextInput(attrs={'class':'form-control','placeholder':'Ex: POP.001'}),
            'nome': forms.TextInput(attrs={'class':'form-control'}),
            'descricao': forms.Textarea(attrs={'class':'form-control','rows':2}),
            'pasta': forms.TextInput(attrs={'class':'form-control'}),
            'classificacao': forms.TextInput(attrs={'class':'form-control'}),
            'autor': forms.TextInput(attrs={'class':'form-control'}),
            'numero_revisao': forms.TextInput(attrs={'class':'form-control','placeholder':'Ex: 01'}),
            'ultima_revisao': forms.DateInput(attrs={'class':'form-control','type':'date'}),
            'data_aprovacao': forms.DateInput(attrs={'class':'form-control','type':'date'}),
            'proxima_revisao': forms.DateInput(attrs={'class':'form-control','type':'date'}),
            'data_validade': forms.DateInput(attrs={'class':'form-control','type':'date'}),
            'documentos_controlados': forms.TextInput(attrs={'class':'form-control'}),
            'matriz': forms.TextInput(attrs={'class':'form-control'}),
            'sub_area': forms.TextInput(attrs={'class':'form-control'}),
        }


class HistoricoCalibracaoForm(forms.ModelForm):
    """
    Formulário para registrar histórico de calibração.
    Agora suporta múltiplas faixas (dados de faixas são processados separadamente na view).
    """
    
    class Meta:
        model = HistoricoCalibracao
        fields = [
            'data_calibracao', 'proxima_calibracao', 'numero_certificado',
            'tipo_calibracao', 'responsavel', 'fornecedor', 'tem_selo_rbc',
            'certificado'
        ]
        widgets = {
            'data_calibracao': forms.DateInput(attrs={'class':'form-control','type':'date'}),
            'proxima_calibracao': forms.DateInput(attrs={'class':'form-control','type':'date'}),
            'numero_certificado': forms.TextInput(attrs={'class':'form-control','placeholder':'Ex: CERT-2024-001'}),
            'tipo_calibracao': forms.Select(attrs={'class':'form-select'}),
            'responsavel': forms.TextInput(attrs={'class':'form-control','placeholder':'Nome do responsável'}),
            'fornecedor': forms.TextInput(attrs={'class':'form-control','placeholder':'Nome do laboratório/fornecedor'}),
            'tem_selo_rbc': forms.CheckboxInput(attrs={'class':'form-check-input'}),
            'certificado': forms.FileInput(attrs={'class':'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        # Aceita instrumento e user (mantém compatibilidade)
        instrumento = kwargs.pop('instrumento', None)
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Pré-preencher automaticamente o responsável com FIRST_NAME + LAST_NAME do usuário logado (somente GET)
        if not self.is_bound and user is not None:
            first = (getattr(user, 'first_name', '') or '').strip()
            last = (getattr(user, 'last_name', '') or '').strip()
            nome_resp = (first + ' ' + last).strip()
            # fallback para full_name ou username
            if not nome_resp:
                full_name = (getattr(user, 'get_full_name', lambda: '')() or '').strip()
                nome_resp = full_name or (getattr(user, 'username', '') or '').strip()
            if nome_resp:
                self.fields['responsavel'].initial = nome_resp
        # Campo deve ser obrigatório para garantir que o carimbo tenha um nome
        self.fields['responsavel'].required = True


class RegistroTreinamentoForm(forms.ModelForm):
    class Meta:
        model = RegistroTreinamento
        fields = [
            'colaborador', 'procedimento', 'revisao_treinada', 'data_treinamento', 'validade_treinamento', 'observacoes'
        ]
        widgets = {
            'colaborador': forms.Select(attrs={'class':'form-select'}),
            'procedimento': forms.Select(attrs={'class':'form-select'}),
            'revisao_treinada': forms.TextInput(attrs={'class':'form-control'}),
            'data_treinamento': forms.DateInput(attrs={'class':'form-control','type':'date'}),
            'validade_treinamento': forms.DateInput(attrs={'class':'form-control','type':'date'}),
            'observacoes': forms.Textarea(attrs={'class':'form-control','rows':2}),
        }
