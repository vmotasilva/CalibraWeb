# -*- coding: utf-8 -*-
"""
Forms para Metrologia Module
"""

from django import forms
from metrologia.models import (
    Instrumento, HistoricoCalibracao, FaixaMedicao, Cotacao, OcorrenciaCotacao,
    SolicitacaoCotacao, ItemSolicitacaoCotacao, CotacaoFornecedor,
    ItemCotacao, AtendimentoSolicitacao, CategoriaInstrumento, FaixaMedicaoPadraoCategoria
)
from .widgets import InstrumentosModalWidget


class InstrumentoForm(forms.ModelForm):
    """Formulário para criar/editar instrumentos de calibração."""
    
    class Meta:
        model = Instrumento
        fields = [
            'tag', 'descricao', 'categoria', 'setor', 'fabricante', 'modelo', 
            'serie', 'frequencia_meses', 'tratativa_calibracao', 'ativo'
        ]
        widgets = {
            'tag': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'TAG / Código'
            }),
            'descricao': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Descrição do instrumento'
            }),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'setor': forms.Select(attrs={'class': 'form-select'}),
            'fabricante': forms.TextInput(attrs={'class': 'form-control'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control'}),
            'serie': forms.TextInput(attrs={'class': 'form-control'}),
            'frequencia_meses': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '1'
            }),
            'tratativa_calibracao': forms.Select(attrs={'class': 'form-select'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class HistoricoCalibracaoForm(forms.ModelForm):
    """Formulário para registrar histórico de calibração."""
    
    
    class Meta:
        model = HistoricoCalibracao
        fields = [
            'data_calibracao', 'proxima_calibracao', 'numero_certificado',
            'tipo_calibracao', 'responsavel', 'fornecedor', 'tem_selo_rbc',
            'certificado'
        ]
        widgets = {
            'data_calibracao': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'proxima_calibracao': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'numero_certificado': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: CERT-2024-001'
            }),
            'tipo_calibracao': forms.Select(attrs={'class': 'form-select'}),
            'responsavel': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome do responsável'
            }),
            'fornecedor': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome do laboratório/fornecedor'
            }),
            'tem_selo_rbc': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'certificado': forms.FileInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        """Initialize form with optional instrumento and user parameters."""
        instrumento = kwargs.pop('instrumento', None)
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if not self.is_bound and user is not None:
            first = (getattr(user, 'first_name', '') or '').strip()
            last = (getattr(user, 'last_name', '') or '').strip()
            nome_resp = (first + ' ' + last).strip()
            
            if not nome_resp:
                full_name = (getattr(user, 'get_full_name', lambda: '')() or '').strip()
                nome_resp = full_name or (getattr(user, 'username', '') or '').strip()
            
            if nome_resp:
                self.fields['responsavel'].initial = nome_resp
        
        self.fields['responsavel'].required = True


class ImportacaoInstrumentosForm(forms.Form):
    """Formulário para importação em massa de instrumentos."""
    
    arquivo_excel = forms.FileField(
        label="Planilha de Instrumentos",
        widget=forms.FileInput(attrs={
            "class": "form-control",
            "accept": ".xlsx, .xls, .csv"
        }),
    )


class ImportacaoHistoricoForm(forms.Form):
    """Formulário para importação em massa de históricos de calibração."""
    
    arquivo_excel = forms.FileField(
        label="Histórico de Calibrações",
        widget=forms.FileInput(attrs={
            "class": "form-control",
            "accept": ".xlsx, .xls, .csv"
        }),
        help_text="Colunas obrigatórias: CÓDIGO (ou TAG), DATA CALIBRAÇÃO, DATA APROVAÇÃO, N CERTIFICADO, RESULTADO",
    )


class FaixaMedicaoFormWithValidation(forms.ModelForm):
    """Formulário para criar/editar faixas de medição com validação."""
    
    class Meta:
        model = FaixaMedicao
        fields = ['unidade', 'valor_minimo', 'valor_maximo', 'resolucao', 'nominal', 'tolerancia_mais_menos']
        widgets = {
            'unidade': forms.Select(attrs={'class': 'form-select'}),
            'valor_minimo': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'valor_maximo': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'resolucao': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'nominal': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'tolerancia_mais_menos': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
        }
    
    def clean(self):
        """Validate faixa data."""
        cleaned_data = super().clean()
        valor_minimo = cleaned_data.get('valor_minimo')
        valor_maximo = cleaned_data.get('valor_maximo')
        
        if valor_minimo is not None and valor_maximo is not None:
            if valor_minimo >= valor_maximo:
                raise forms.ValidationError(
                    "Valor mínimo deve ser menor que valor máximo."
                )
        
        return cleaned_data


class CotacaoForm(forms.ModelForm):
    """Formulário para criar/editar cotações."""

    class Meta:
        model = Cotacao
        fields = ['fornecedor', 'instrumentos', 'valor', 'observacoes']
        widgets = {
            'fornecedor': forms.Select(attrs={'class': 'form-select'}),
            'instrumentos': forms.SelectMultiple(attrs={'class': 'form-select', 'size': '10'}),
            'valor': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Valor da cotação'
            }),
            'observacoes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Observações sobre a cotação'
            }),
        }

    def clean_instrumentos(self):
        data = self.cleaned_data.get('instrumentos')
        if isinstance(data, str):
            ids = [int(i) for i in data.split(',') if i.strip().isdigit()]
            return ids
        elif isinstance(data, list):
            return [int(i) for i in data if str(i).strip().isdigit()]
        return data

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        data = self.data
        if data and 'instrumentos_ids' in data:
            val = data.get('instrumentos_ids')
            if isinstance(val, str):
                ids = [int(i) for i in val.split(',') if i.strip().isdigit()]
                self.data = self.data.copy()
                self.data.setlist('instrumentos', [str(i) for i in ids])


class CotacaoAprovarForm(forms.ModelForm):
    """Formulário para aprovar cotações."""
    
    class Meta:
        model = Cotacao
        fields = ['valor', 'observacoes']
        widgets = {
            'valor': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Valor aprovado'
            }),
            'observacoes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Observações da aprovação'
            }),
        }


class OcorrenciaCotacaoForm(forms.ModelForm):
    """Formulário para registrar ocorrências em cotações."""
    
    class Meta:
        model = OcorrenciaCotacao
        fields = ['tipo', 'descricao', 'acao_tomada']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descrição da ocorrência'
            }),
            'acao_tomada': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Ação tomada para resolver'
            }),
        }


class SolicitacaoCotacaoForm(forms.ModelForm):
    """ETAPA 1: Formulário para criar uma Solicitação de Cotação"""

    class Meta:
        model = SolicitacaoCotacao
        fields = ['data_solicitacao_orcamento', 'dias_vencimento', 'responsavel', 'departamento']
        widgets = {
            'data_solicitacao_orcamento': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'dias_vencimento': forms.NumberInput(attrs={
                'class': 'form-control',
                'type': 'number',
                'min': '1',
                'max': '365',
                'value': '30',
                'placeholder': 'Ex: 30'
            }),
            'responsavel': forms.Select(attrs={
                'class': 'form-control',
            }),
            'departamento': forms.Select(attrs={
                'class': 'form-control',
            }),
        }


class ItemSolicitacaoCotacaoForm(forms.ModelForm):
    """ETAPA 1: Formulário para adicionar itens (instrumentos) à solicitação"""
    
    class Meta:
        model = ItemSolicitacaoCotacao
        fields = ['instrumento', 'tipo_pontos', 'faixa_min', 'faixa_centro', 'faixa_max', 'unidade_pontos', 'notas']
        widgets = {
            'instrumento': forms.Select(attrs={'class': 'form-select'}),
            'tipo_pontos': forms.Select(attrs={'class': 'form-select'}),
            'faixa_min': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Faixa Mínima',
                'step': '0.0001'
            }),
            'faixa_centro': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Faixa Centro',
                'step': '0.0001'
            }),
            'faixa_max': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Faixa Máxima',
                'step': '0.0001'
            }),
            'unidade_pontos': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: mm, V, °C'
            }),
            'notas': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Notas adicionais (opcional)'
            }),
        }


class CotacaoFornecedorForm(forms.ModelForm):
    """ETAPA 2: Formulário para criar uma Cotação do Fornecedor"""
    
    class Meta:
        model = CotacaoFornecedor
        fields = ['fornecedor', 'data_solicitacao', 'data_retorno_fornecedor', 'aprovada']
        widgets = {
            'fornecedor': forms.Select(attrs={
                'class': 'form-select',
            }),
            'data_solicitacao': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'data_retorno_fornecedor': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'aprovada': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }


class ItemCotacaoForm(forms.ModelForm):
    """ETAPA 2: Formulário para adicionar itens (instrumentos) à cotação do fornecedor"""
    
    class Meta:
        model = ItemCotacao
        fields = ['item_solicitacao', 'instrumento', 'pode_atender', 'tipo_servico', 
                  'valor_unitario', 'quantidade', 'local_atendimento', 'prazo_dias', 'descricao_servico']
        widgets = {
            'item_solicitacao': forms.Select(attrs={'class': 'form-select'}),
            'instrumento': forms.Select(attrs={'class': 'form-select'}),
            'pode_atender': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'tipo_servico': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'valor_unitario': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'R$ 0,00'
            }),
            'quantidade': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'value': '1'
            }),
            'local_atendimento': forms.Select(attrs={
                'class': 'form-select',
            }),
            'prazo_dias': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'placeholder': 'Dias para executar'
            }),
            'descricao_servico': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Detalhe do serviço, normas aplicáveis, etc.'
            }),
        }


class AtendimentoSolicitacaoForm(forms.ModelForm):
    """ETAPA 3: Formulário para selecionar qual cotação atenderá cada necessidade"""
    
    class Meta:
        model = AtendimentoSolicitacao
        fields = ['item_cotacao', 'data_prevista_atendimento', 'observacoes']
        widgets = {
            'item_cotacao': forms.Select(attrs={'class': 'form-select'}),
            'data_prevista_atendimento': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'observacoes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Observações sobre a escolha (opcional)'
            }),
        }


class CategoriaInstrumentoForm(forms.ModelForm):
    """Formulário para criar e atualizar categorias de instrumentos."""
    
    class Meta:
        model = CategoriaInstrumento
        fields = ['nome', 'descricao', 'unidade_padrao']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Ex: Paquímetro, Micrometro, Termômetro, etc',
                'required': 'required',
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Descreva a categoria e suas características principais',
            }),
            'unidade_padrao': forms.Select(attrs={
                'class': 'form-select',
            }),
        }


class FaixaMedicaoPadraoCategoriForm(forms.ModelForm):
    """Formulário para criar e atualizar faixas padrão de categorias."""
    
    class Meta:
        model = FaixaMedicaoPadraoCategoria
        fields = ['unidade', 'valor_minimo', 'valor_maximo', 'resolucao', 'nominal', 'tolerancia_mais_menos', 'ativa']
        widgets = {
            'unidade': forms.Select(attrs={'class': 'form-select'}),
            'valor_minimo': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.0001',
                'placeholder': 'Valor mínimo'
            }),
            'valor_maximo': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.0001',
                'placeholder': 'Valor máximo'
            }),
            'resolucao': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.0001',
                'placeholder': 'Resolução (opcional)'
            }),
            'nominal': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.0001',
                'placeholder': 'Valor nominal (opcional)'
            }),
            'tolerancia_mais_menos': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.0001',
                'placeholder': 'Tolerância ±X (opcional)'
            }),
            'ativa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        valor_minimo = cleaned_data.get('valor_minimo')
        valor_maximo = cleaned_data.get('valor_maximo')
        
        if valor_minimo is not None and valor_maximo is not None:
            if valor_minimo >= valor_maximo:
                raise forms.ValidationError(
                    "Valor mínimo deve ser menor que valor máximo."
                )
        
        return cleaned_data
