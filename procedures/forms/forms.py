# -*- coding: utf-8 -*-
"""
Forms para o módulo Procedures
Consolida forms de training e procurements
"""

from django import forms
from django.urls import reverse_lazy
from core.models import TURNOS_CHOICES
from procedures.models import (
    Procedimento, RegistroTreinamento, PacoteTreinamento,
    MatrizProcedimento, SubAreaProcedimento, ResponsavelTreinamentoMatriz,
    Fornecedor, AvaliacaoFornecedor, ProcessoCotacao, Orcamento,
    Disciplina, MatrizHabilidade, AvaliacaoHabilidade,
    PerfilTreinamento, GrupoTreinamento, SubGrupoTreinamento,
    ColaboradorPerfil, PlanejamentoTreinamento
)


# ==============================================================================
# PROCEDIMENTOS E TREINAMENTOS
# ==============================================================================

class MatrizProcedimentoForm(forms.ModelForm):
    """Formulário para criar/editar matriz de procedimentos."""

    class Meta:
        model = MatrizProcedimento
        fields = ['nome', 'ativo']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: SURFAÇAGEM'
            }),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SubAreaProcedimentoForm(forms.ModelForm):
    """Formulário para criar sub-áreas dentro de uma matriz de procedimentos."""

    class Meta:
        model = SubAreaProcedimento
        fields = ['nome', 'ativo']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Blocagem'
            }),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ImportacaoMatrizSubAreaForm(forms.Form):
    """Formulário para importação em massa de matrizes e sub-áreas."""

    arquivo = forms.FileField(
        label='Arquivo de Importação',
        help_text='Aceita .xlsx, .xls ou .csv com colunas: matriz, sub_area, ativo_matriz, ativo_sub_area',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.xlsx,.xls,.csv',
        }),
    )


class MatrizResponsabilidadeTreinamentoForm(forms.Form):
    turno_choices = TURNOS_CHOICES

    def __init__(self, *args, matrix_groups=None, matrizes=None, responsabilidades=None, **kwargs):
        super().__init__(*args, **kwargs)
        from rh.models import Colaborador

        if matrix_groups is None and matrizes:
            matrix_groups = [
                {
                    'matriz': matriz,
                    'sections': [
                        {
                            'sub_area': None,
                            'display_name': matriz.nome,
                            'is_general': True,
                            'total_procedimentos': 0,
                        }
                    ],
                }
                for matriz in matrizes
            ]

        self.matrix_groups = list(matrix_groups or [])
        self.turnos = [choice for choice in self.turno_choices if choice[0] != '12X36']
        self.responsabilidades = responsabilidades or {}

        colaboradores = list(
            Colaborador.objects.select_related('setor').order_by('nome_completo')
        )
        self.colaboradores = colaboradores
        self.colaborador_choices = [('', 'Sem responsavel')]
        self.colaborador_choices.extend(
            (str(colaborador.id), self.format_colaborador_label(colaborador))
            for colaborador in self.colaboradores
        )

        for matriz, section in self.iter_sections():
            sub_area = section.get('sub_area')
            sub_area_id = sub_area.id if sub_area else None
            for turno, _ in self.turnos:
                field_name = self.get_field_name(matriz.id, sub_area_id, turno)
                atual = self.responsabilidades.get((matriz.id, sub_area_id, turno))
                self.fields[field_name] = forms.ChoiceField(
                    required=False,
                    choices=self.colaborador_choices,
                    initial=str(atual.colaborador_id) if atual else '',
                    label='',
                    widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
                )

    @staticmethod
    def get_scope_token(sub_area_id):
        return f'sa{sub_area_id}' if sub_area_id else 'geral'

    @classmethod
    def get_field_name(cls, matriz_id, sub_area_id, turno):
        return f"resp_{matriz_id}_{cls.get_scope_token(sub_area_id)}_{turno}"

    @staticmethod
    def format_colaborador_label(colaborador):
        sufixos = []
        if colaborador.cargo:
            sufixos.append(colaborador.cargo)
        if not colaborador.is_active:
            sufixos.append('Inativo')
        if colaborador.afastado:
            sufixos.append('Afastado')
        if colaborador.em_ferias:
            sufixos.append('Ferias')
        if sufixos:
            return f"{colaborador.nome_completo} ({' | '.join(sufixos)})"
        return colaborador.nome_completo

    def iter_sections(self):
        for matrix_group in self.matrix_groups:
            matriz = matrix_group['matriz']
            for section in matrix_group.get('sections', []):
                yield matriz, section

    def build_groups(self, colaboradores_qualificados=None):
        colaboradores_qualificados = colaboradores_qualificados or {}
        groups = []
        for matrix_group in self.matrix_groups:
            matriz = matrix_group['matriz']
            sections = []
            for section in matrix_group.get('sections', []):
                sub_area = section.get('sub_area')
                sub_area_id = sub_area.id if sub_area else None
                cells = []
                for turno, turno_label in self.turnos:
                    field_name = self.get_field_name(matriz.id, sub_area_id, turno)
                    field = self[field_name]
                    cells.append({
                        'turno': turno,
                        'turno_label': turno_label,
                        'field': field,
                        'total_opcoes': colaboradores_qualificados.get((matriz.id, sub_area_id, turno), 0),
                        'responsabilidade': self.responsabilidades.get((matriz.id, sub_area_id, turno)),
                    })
                sections.append({**section, 'cells': cells})
            groups.append({**matrix_group, 'sections': sections})
        return groups

    def build_rows(self, colaboradores_qualificados=None):
        rows = []
        for matrix_group in self.build_groups(colaboradores_qualificados=colaboradores_qualificados):
            matriz = matrix_group['matriz']
            for turno, turno_label in self.turnos:
                for section in matrix_group.get('sections', []):
                    for cell in section.get('cells', []):
                        if cell['turno'] == turno:
                            rows.append({'matriz': matriz, 'sub_area': section.get('sub_area'), 'cells': [cell]})
        return rows

    def clean(self):
        cleaned_data = super().clean()
        from rh.models import Colaborador

        selecionados = {int(value) for value in cleaned_data.values() if value}
        colaboradores = Colaborador.objects.in_bulk(selecionados)

        for matriz, section in self.iter_sections():
            sub_area = section.get('sub_area')
            sub_area_id = sub_area.id if sub_area else None
            for turno, _ in self.turnos:
                field_name = self.get_field_name(matriz.id, sub_area_id, turno)
                colaborador_id = cleaned_data.get(field_name)
                if not colaborador_id:
                    continue

                colaborador = colaboradores.get(int(colaborador_id))
                if not colaborador:
                    self.add_error(field_name, 'Colaborador invalido.')

        return cleaned_data

    def save(self, matriz_id=None):
        from rh.models import Colaborador

        selecionados = {int(value) for value in self.cleaned_data.values() if value}
        colaboradores = Colaborador.objects.in_bulk(selecionados)
        atualizadas = 0
        removidas = 0

        for matriz, section in self.iter_sections():
            if matriz_id is not None and matriz.id != matriz_id:
                continue
            sub_area = section.get('sub_area')
            sub_area_id = sub_area.id if sub_area else None
            for turno, _ in self.turnos:
                field_name = self.get_field_name(matriz.id, sub_area_id, turno)
                colaborador_id = self.cleaned_data.get(field_name)
                responsabilidade = self.responsabilidades.get((matriz.id, sub_area_id, turno))

                if not colaborador_id:
                    if responsabilidade:
                        responsabilidade.delete()
                        removidas += 1
                    continue

                colaborador = colaboradores[int(colaborador_id)]
                if responsabilidade:
                    if responsabilidade.colaborador_id != colaborador.id:
                        responsabilidade.colaborador = colaborador
                        responsabilidade.full_clean()
                        responsabilidade.save(update_fields=['colaborador', 'atualizado_em'])
                        atualizadas += 1
                    continue

                nova_responsabilidade = ResponsavelTreinamentoMatriz(
                    matriz=matriz,
                    sub_area=sub_area,
                    turno=turno,
                    colaborador=colaborador,
                )
                nova_responsabilidade.full_clean()
                nova_responsabilidade.save()
                atualizadas += 1

        return {'atualizadas': atualizadas, 'removidas': removidas}

class ProcedimentoForm(forms.ModelForm):
    """Formulário para criar/editar procedimentos operacionais."""

    matriz = forms.ModelChoiceField(
        queryset=MatrizProcedimento.objects.none(),
        required=False,
        empty_label='Selecione',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    sub_area = forms.ModelChoiceField(
        queryset=SubAreaProcedimento.objects.none(),
        required=False,
        empty_label='Selecione',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['matriz'].queryset = MatrizProcedimento.objects.filter(ativo=True).order_by('nome')
        self.fields['sub_area'].widget.attrs['data-subareas-url'] = reverse_lazy('procedures:api_subareas_por_matriz')

        matriz_id = None

        if self.is_bound:
            matriz_raw = self.data.get('matriz')
            if matriz_raw and str(matriz_raw).isdigit():
                matriz_id = int(matriz_raw)
        elif self.instance and self.instance.pk and self.instance.matriz:
            matriz_nome = self.instance.matriz.strip()
            matriz_obj, _ = MatrizProcedimento.objects.get_or_create(nome=matriz_nome)
            if matriz_obj:
                matriz_id = matriz_obj.id
                self.initial['matriz'] = matriz_obj

        if matriz_id:
            self.fields['sub_area'].queryset = SubAreaProcedimento.objects.filter(
                matriz_id=matriz_id,
                ativo=True,
            ).order_by('nome')
        else:
            self.fields['sub_area'].queryset = SubAreaProcedimento.objects.none()

        if self.instance and self.instance.pk and self.instance.sub_area:
            sub_area_obj = None
            if matriz_id:
                sub_area_obj, _ = SubAreaProcedimento.objects.get_or_create(
                    matriz_id=matriz_id,
                    nome=self.instance.sub_area.strip(),
                )
            if sub_area_obj:
                self.initial['sub_area'] = sub_area_obj

    def clean_matriz(self):
        matriz_obj = self.cleaned_data.get('matriz')
        if matriz_obj:
            return matriz_obj.nome
        if self.instance and self.instance.pk:
            return self.instance.matriz or ''
        return ''

    def clean_sub_area(self):
        sub_area_obj = self.cleaned_data.get('sub_area')
        if sub_area_obj:
            return sub_area_obj.nome
        if self.instance and self.instance.pk:
            return self.instance.sub_area or ''
        return ''

    def clean(self):
        cleaned_data = super().clean()
        matriz_nome = cleaned_data.get('matriz')
        sub_area_nome = cleaned_data.get('sub_area')

        if matriz_nome and sub_area_nome:
            is_vinculada = SubAreaProcedimento.objects.filter(
                matriz__nome=matriz_nome,
                nome=sub_area_nome,
            ).exists()
            if not is_vinculada:
                self.add_error('sub_area', 'A sub-área selecionada não pertence à matriz informada.')

        return cleaned_data
    
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
            'criticidade': forms.Select(attrs={'class': 'form-select'}),
        }


class RegistroTreinamentoForm(forms.ModelForm):
    """Formulário para registrar treinamentos de colaboradores."""
    
    # Campo explícito para o checkbox funcionar corretamente
    ativo = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Ativo",
        help_text="Define se o treinamento está ativo ou inativo"
    )
    
    class Meta:
        model = RegistroTreinamento
        fields = [
            'colaborador', 'procedimento', 'revisao_treinada', 'data_treinamento',
            'validade_treinamento', 'ativo', 'observacoes'
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
            'data_prevista', 'horario_previsto', 'data_realizada', 'carga_horaria',
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
            'horario_previsto': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
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


# ==============================================================================
# IMPORTAÇÃO EM MASSA
# ==============================================================================

class ImportacaoMatrizHabilidadeForm(forms.Form):
    """Formulário para importar matrizes, disciplinas e colaboradores em massa."""
    
    FORMATO_CHOICES = [
        ('csv', 'CSV (Arquivo de Texto)'),
        ('excel', 'Excel (XLSX)'),
    ]
    
    arquivo = forms.FileField(
        label='Arquivo para Importação',
        help_text='Selecione um arquivo CSV ou Excel (.xlsx)',
        required=True,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv,.xlsx,.xls',
            'id': 'id_arquivo_importacao'
        })
    )
    
    formato = forms.ChoiceField(
        label='Formato do Arquivo',
        choices=FORMATO_CHOICES,
        initial='csv',
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input',
        })
    )
    
    atualizar_existentes = forms.BooleanField(
        label='Atualizar registros existentes',
        required=False,
        initial=True,
        help_text='Se marcado, matrizes e disciplinas duplicadas serão atualizadas. Caso contrário, serão ignoradas.',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    class Meta:
        fields = ['arquivo', 'formato', 'atualizar_existentes']
