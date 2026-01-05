"""Forms para criação e edição de listas de presença."""
from django import forms
from django.forms import inlineformset_factory
from procedures.models import ListaPresenca, RegistroTreinamento, Procedimento, ParticipanteExterno
from rh.models import Colaborador


class ParticipanteExternoForm(forms.ModelForm):
    """Form para cadastro rápido de participante externo."""
    
    class Meta:
        model = ParticipanteExterno
        fields = ['nome_completo', 'cpf', 'empresa', 'email', 'telefone', 'observacoes']
        widgets = {
            'nome_completo': forms.TextInput(attrs={'class': 'form-control'}),
            'cpf': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '000.000.000-00'}),
            'empresa': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(00) 00000-0000'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ListaPresencaForm(forms.ModelForm):
    """Form para criar/editar lista de presença."""
    
    class Meta:
        model = ListaPresenca
        fields = [
            'titulo', 'instrutor_nome', 'instrutor', 'data_sessao', 'hora_inicio', 
            'hora_fim', 'carga_horaria', 'local', 'observacoes', 'template'
        ]
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'instrutor_nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Digite o nome do instrutor (livre)'
            }),
            'instrutor': forms.Select(attrs={
                'class': 'form-select',
                'data-toggle': 'tooltip',
                'title': 'Selecione se o instrutor está na base de dados'
            }),
            'data_sessao': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'hora_inicio': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'hora_fim': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'carga_horaria': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.25'}),
            'local': forms.TextInput(attrs={'class': 'form-control'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'template': forms.Select(attrs={
                'class': 'form-select',
                'data-toggle': 'tooltip',
                'title': 'Selecione um template Excel para estruturar a lista de presença'
            }),
        }


class RegistroTreinamentoInlineForm(forms.ModelForm):
    """Form inline para criar registros de treinamento na lista de presença."""
    
    # Campo para escolher tipo de participante
    tipo_participante = forms.ChoiceField(
        choices=[('colaborador', 'Colaborador'), ('externo', 'Externo')],
        widget=forms.Select(attrs={'class': 'form-select tipo-participante-select'}),
        initial='colaborador',
        label='Tipo de Participante'
    )
    
    class Meta:
        model = RegistroTreinamento
        fields = [
            'tipo', 'colaborador_nome', 'colaborador', 'participante_externo', 
            'procedimento', 'titulo_treinamento', 'descricao',
            'data_treinamento', 'observacoes'
        ]
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select tipo-registro-select'}),
            'colaborador_nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Digite o nome do colaborador (livre)'
            }),
            'colaborador': forms.Select(attrs={'class': 'form-select participante-colaborador'}),
            'participante_externo': forms.Select(attrs={'class': 'form-select participante-externo', 'style': 'display:none;'}),
            'procedimento': forms.Select(attrs={'class': 'form-select campo-procedimento'}),
            'titulo_treinamento': forms.TextInput(attrs={'class': 'form-control campo-titulo', 'style': 'display:none;'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control campo-descricao', 'rows': 2, 'style': 'display:none;'}),
            'data_treinamento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'observacoes': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Tornar campos opcionais (validação customizada no model)
        self.fields['colaborador_nome'].required = False
        self.fields['colaborador'].required = False
        self.fields['participante_externo'].required = False
        self.fields['procedimento'].required = False
        self.fields['titulo_treinamento'].required = False


# Formset para múltiplos registros de treinamento
RegistroTreinamentoFormSet = inlineformset_factory(
    ListaPresenca,
    RegistroTreinamento,
    form=RegistroTreinamentoInlineForm,
    extra=1,
    can_delete=True,
    fields=[
        'tipo', 'colaborador_nome', 'colaborador', 'participante_externo',
        'procedimento', 'titulo_treinamento', 'descricao',
        'data_treinamento', 'observacoes'
    ]
)


class ImportacaoTreinamentoForm(forms.Form):
    """Form para importação em massa de treinamentos via Excel."""
    arquivo = forms.FileField(
        label='Arquivo Excel',
        help_text='Formato: .xlsx ou .xls',
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.xlsx,.xls'})
    )
    
    # Tipo de importação (opcional - não usado atualmente)
    tipo_importacao = forms.ChoiceField(
        label='Tipo de dados',
        choices=[
            ('procedimento', 'Treinamentos em Procedimentos'),
            ('geral', 'Alinhamentos/Reuniões Gerais')
        ],
        initial='procedimento',
        required=False,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        help_text='Procedimentos: requer código do procedimento. Geral: requer título.'
    )
    
    # Opções de importação
    criar_listas_automaticamente = forms.BooleanField(
        label='Agrupar em listas de presença automaticamente',
        help_text='Detecta treinamentos da mesma sessão (mesma data, instrutor, horário)',
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    sobrescrever_existentes = forms.BooleanField(
        label='Sobrescrever treinamentos existentes',
        help_text='Se desativado, treinamentos duplicados serão ignorados',
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
