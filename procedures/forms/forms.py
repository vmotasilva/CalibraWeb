# -*- coding: utf-8 -*-
"""
Forms para o módulo Procedures
Consolida forms de training e procurements
"""

from django import forms
from procedures.models import (
    Procedimento, RegistroTreinamento, PacoteTreinamento,
    Fornecedor, AvaliacaoFornecedor, ProcessoCotacao, Orcamento,
    Disciplina, MatrizHabilidade, AvaliacaoHabilidade,
    PerfilTreinamento, GrupoTreinamento, SubGrupoTreinamento,
    ColaboradorPerfil, PlanejamentoTreinamento
)


# ==============================================================================
# PROCEDIMENTOS E TREINAMENTOS
# ==============================================================================

class ProcedimentoForm(forms.ModelForm):
    """Formulário para criar/editar procedimentos operacionais."""
    
    class Meta:
        model = Procedimento
        fields = [
            'codigo', 'nome', 'descricao', 'pasta', 'classificacao', 'autor',
            'numero_revisao', 'ultima_revisao', 'data_aprovacao', 'proxima_revisao',
            'data_validade', 'documentos_controlados', 'matriz', 'sub_area', 'criticidade'
        ]
        widgets = {
            'codigo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: POP.001'
            }),
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
            'pasta': forms.TextInput(attrs={'class': 'form-control'}),
            'classificacao': forms.TextInput(attrs={'class': 'form-control'}),
            'autor': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_revisao': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 01'
            }),
            'ultima_revisao': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'data_aprovacao': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'proxima_revisao': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'data_validade': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'documentos_controlados': forms.TextInput(attrs={'class': 'form-control'}),
            'matriz': forms.TextInput(attrs={'class': 'form-control'}),
            'sub_area': forms.TextInput(attrs={'class': 'form-control'}),
            'criticidade': forms.Select(attrs={'class': 'form-select'}),
        }


class RegistroTreinamentoForm(forms.ModelForm):
    """Formulário para registrar treinamentos de colaboradores."""
    
    class Meta:
        model = RegistroTreinamento
        fields = [
            'colaborador', 'procedimento', 'revisao_treinada', 'data_treinamento',
            'validade_treinamento', 'observacoes'
        ]
        widgets = {
            'colaborador': forms.Select(attrs={'class': 'form-select'}),
            'procedimento': forms.Select(attrs={'class': 'form-select'}),
            'revisao_treinada': forms.TextInput(attrs={'class': 'form-control'}),
            'data_treinamento': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'validade_treinamento': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'observacoes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
        }


class PacoteTreinamentoForm(forms.ModelForm):
    """Formulário para criar/editar pacotes de treinamento."""
    
    class Meta:
        model = PacoteTreinamento
        fields = ['nome', 'descricao', 'procedimentos']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
            'procedimentos': forms.CheckboxSelectMultiple(),
        }


class ImportacaoProcedimentosForm(forms.Form):
    """Formulário para importação em massa de procedimentos."""
    
    arquivo_excel = forms.FileField(
        label="Planilha de Procedimentos",
        widget=forms.FileInput(attrs={
            "class": "form-control",
            "accept": ".xlsx, .xls"
        }),
    )


# ==============================================================================
# FORNECEDORES E COTAÇÕES
# ==============================================================================

class FornecedorForm(forms.ModelForm):
    """Formulário para criar/editar fornecedor."""
    
    class Meta:
        model = Fornecedor
        fields = [
            'nome_fantasia', 'razao_social', 'cnpj', 'contato',
            'email', 'telefone', 'escopo_servico', 'status'
        ]
        widgets = {
            'nome_fantasia': forms.TextInput(attrs={'class': 'form-control'}),
            'razao_social': forms.TextInput(attrs={'class': 'form-control'}),
            'cnpj': forms.TextInput(attrs={'class': 'form-control'}),
            'contato': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control'}),
            'escopo_servico': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }


class AvaliacaoFornecedorForm(forms.ModelForm):
    """Formulário para avaliar fornecedor."""
    
    class Meta:
        model = AvaliacaoFornecedor
        fields = [
            'fornecedor', 'nota_tecnica', 'nota_pontualidade',
            'nota_atendimento', 'observacao'
        ]
        widgets = {
            'fornecedor': forms.Select(attrs={'class': 'form-select'}),
            'nota_tecnica': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '10'
            }),
            'nota_pontualidade': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '10'
            }),
            'nota_atendimento': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '10'
            }),
            'observacao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
        }


class ProcessoCotacaoForm(forms.ModelForm):
    """Formulário para criar/editar processo de cotação."""
    
    class Meta:
        model = ProcessoCotacao
        fields = ['titulo', 'prazo_limite', 'instrumentos', 'status', 'responsavel']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'prazo_limite': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'instrumentos': forms.CheckboxSelectMultiple(),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'responsavel': forms.Select(attrs={'class': 'form-select'}),
        }


class OrcamentoForm(forms.ModelForm):
    """Formulário para criar/editar orçamento."""
    
    class Meta:
        model = Orcamento
        fields = [
            'processo', 'fornecedor', 'valor_total', 'prazo_execucao_dias',
            'arquivo_proposta', 'vencedor', 'observacoes'
        ]
        widgets = {
            'processo': forms.Select(attrs={'class': 'form-select'}),
            'fornecedor': forms.Select(attrs={'class': 'form-select'}),
            'valor_total': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'prazo_execucao_dias': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
            'arquivo_proposta': forms.FileInput(attrs={'class': 'form-control'}),
            'vencedor': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'observacoes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
        }


# ==============================================================================
# MATRIZ DE HABILIDADES
# ==============================================================================

class DisciplinaForm(forms.ModelForm):
    """Formulário para criar/editar disciplina."""
    
    class Meta:
        model = Disciplina
        fields = ['matriz', 'nome', 'prioridade', 'obrigatoriedade_legal', 'descricao', 'ativo']
        widgets = {
            'matriz': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Calibração de Paquímetro'
            }),
            'prioridade': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Alta, Média, Baixa'
            }),
            'obrigatoriedade_legal': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: NR-10, ISO 9001, etc.'
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Público, Periodicidade, Carga Horária e outras informações'
            }),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class MatrizHabilidadeForm(forms.ModelForm):
    """Formulário para criar/editar matriz de habilidade."""
    
    class Meta:
        model = MatrizHabilidade
        fields = ['nome', 'ativo']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Matriz Calibração Dimensional'
            }),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class AvaliacaoHabilidadeForm(forms.ModelForm):
    """Formulário para avaliar habilidade de colaborador."""
    
    class Meta:
        model = AvaliacaoHabilidade
        fields = ['colaborador', 'disciplina', 'matriz', 'nivel', 'data_avaliacao', 'avaliador', 'observacoes']
        widgets = {
            'colaborador': forms.Select(attrs={'class': 'form-select'}),
            'disciplina': forms.Select(attrs={'class': 'form-select'}),
            'matriz': forms.Select(attrs={'class': 'form-select'}),
            'nivel': forms.Select(attrs={'class': 'form-select'}),
            'data_avaliacao': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'avaliador': forms.Select(attrs={'class': 'form-select'}),
            'observacoes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
        }


# ==============================================================================
# PERFIS E GRUPOS DE TREINAMENTO
# ==============================================================================

class PerfilTreinamentoForm(forms.ModelForm):
    """Formulário para criar/editar perfil de treinamento."""
    
    class Meta:
        model = PerfilTreinamento
        fields = ['nome', 'descricao', 'ativo']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Técnico de Calibração'
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descreva os requisitos e responsabilidades deste perfil'
            }),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class GrupoTreinamentoForm(forms.ModelForm):
    """Formulário para criar/editar grupo de treinamento."""
    
    class Meta:
        model = GrupoTreinamento
        fields = ['nome', 'descricao', 'ordem']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Treinamentos Técnicos, Segurança, Qualidade'
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Descreva o objetivo ou abrangência deste grupo'
            }),
            'ordem': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
        }


class SubGrupoTreinamentoForm(forms.ModelForm):
    """Formulário para criar/editar sub-grupo de treinamento."""
    
    class Meta:
        model = SubGrupoTreinamento
        fields = ['nome', 'descricao', 'ordem']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Calibração de Torquímetros'
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Descreva os procedimentos incluídos neste subgrupo'
            }),
            'ordem': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
        }


class ColaboradorPerfilForm(forms.ModelForm):
    """Formulário para associar colaborador a perfil."""
    
    class Meta:
        model = ColaboradorPerfil
        fields = ['colaborador', 'perfil', 'data_atribuicao', 'ativo', 'observacoes']
        widgets = {
            'colaborador': forms.Select(attrs={'class': 'form-select'}),
            'perfil': forms.Select(attrs={'class': 'form-select'}),
            'data_atribuicao': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'observacoes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
        }


# ==============================================================================
# PLANEJAMENTO DE TREINAMENTOS
# ==============================================================================

class PlanejamentoTreinamentoForm(forms.ModelForm):
    """Formulário para planejar treinamento com 3 tipos de origem."""
    
    class Meta:
        model = PlanejamentoTreinamento
        fields = [
            'titulo', 'procedimentos', 'disciplina', 'colaboradores', 'instrutor',
            'data_prevista', 'data_realizada', 'carga_horaria',
            'local', 'status', 'observacoes'
        ]
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'procedimentos': forms.CheckboxSelectMultiple(attrs={
                'class': 'form-check-input',
                'data-field-type': 'procedimentos'
            }),
            'disciplina': forms.Select(attrs={
                'class': 'form-select',
                'data-field-type': 'disciplina'
            }),
            'colaboradores': forms.CheckboxSelectMultiple(attrs={
                'class': 'form-check-input'
            }),
            'instrutor': forms.Select(attrs={
                'class': 'form-select select2-search',
                'data-placeholder': 'Selecione um instrutor...'
            }),
            'data_prevista': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'data_realizada': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'carga_horaria': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Minutos'
            }),
            'local': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'observacoes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Definir required conforme a instância
        self.fields['titulo'].required = True
        self.fields['data_prevista'].required = True
        # Não forçar colaboradores obrigatório aqui - será validado na view se necessário
        self.fields['colaboradores'].required = False
        
        # Campos opcionais por padrão
        self.fields['procedimentos'].required = False
        self.fields['disciplina'].required = False
        self.fields['status'].required = True
        
        # Ordenar instrutores alfabeticamente
        self.fields['instrutor'].queryset = self.fields['instrutor'].queryset.order_by('nome_completo')
        
        # Adicionar help texts
        self.fields['procedimentos'].help_text = 'Selecione os procedimentos para este planejamento'
        self.fields['disciplina'].help_text = 'Selecione a disciplina (obrigatório para origem "Matriz de Habilidades")'

