from django import forms
from boards.models import Board, Card, BoardSubSection, BoardLabel
from rh.models import Colaborador

class BoardForm(forms.ModelForm):
    class Meta:
        model = Board
        fields = ['nome', 'descricao', 'membros']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome do Quadro'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Breve descrição do quadro...'}),
            'membros': forms.SelectMultiple(attrs={'class': 'form-select', 'size': 8}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['membros'].queryset = Colaborador.objects.filter(is_active=True).order_by('nome_completo')
        self.fields['membros'].required = False


class CardForm(forms.ModelForm):
    data_entrega = forms.DateField(
        input_formats=['%d/%m/%Y', '%Y-%m-%d'],
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control js-week-datepicker', 'type': 'text', 'autocomplete': 'off'}),
        label="Data de Entrega"
    )
    data_conclusao = forms.DateField(
        input_formats=['%d/%m/%Y', '%Y-%m-%d'],
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control js-week-datepicker', 'type': 'text', 'autocomplete': 'off'}),
        label="Data de Conclusão"
    )
    hora_inicio = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
        label="Hora de Início"
    )
    hora_fim = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
        label="Hora de Fim"
    )

    class Meta:
        model = Card
        fields = ['titulo', 'descricao', 'responsaveis', 'subsecao', 'prioridade', 'data_entrega', 'periodicidade', 'etiquetas', 'data_conclusao', 'hora_inicio', 'hora_fim']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Título da tarefa'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descrição detalhada...'}),
            'responsaveis': forms.SelectMultiple(attrs={'class': 'form-select', 'size': 4}),
            'subsecao': forms.Select(attrs={'class': 'form-select'}),
            'prioridade': forms.Select(attrs={'class': 'form-select'}),
            'periodicidade': forms.Select(attrs={'class': 'form-select'}),
            'etiquetas': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        board = kwargs.pop('board', None)
        column = kwargs.pop('column', None)
        super().__init__(*args, **kwargs)
        
        if column:
            self.fields['subsecao'].queryset = column.subsecoes.all().order_by('nome')
        elif board:
            self.fields['subsecao'].queryset = BoardSubSection.objects.filter(coluna__quadro=board).order_by('coluna__nome', 'nome')
        else:
            self.fields['subsecao'].queryset = BoardSubSection.objects.all().order_by('nome')
            
        self.fields['subsecao'].required = False
        self.fields['subsecao'].label = "Sub-sessão"
        
        if board:
            self.fields['etiquetas'].queryset = board.etiquetas.all().order_by('nome')
        else:
            self.fields['etiquetas'].queryset = BoardLabel.objects.none()
        self.fields['etiquetas'].required = False
        self.fields['etiquetas'].label = "Etiquetas"
        
        if board:
            # Filtra os responsáveis apenas para os membros desse quadro + o criador
            membros_ids = list(board.membros.values_list('id', flat=True))
            if board.criado_por:
                membros_ids.append(board.criado_por.id)
            self.fields['responsaveis'].queryset = Colaborador.objects.filter(id__in=membros_ids, is_active=True).distinct().order_by('nome_completo')
        else:
            self.fields['responsaveis'].queryset = Colaborador.objects.filter(is_active=True).order_by('nome_completo')
        
        self.fields['responsaveis'].required = False
        self.fields['data_entrega'].required = False
        self.fields['periodicidade'].required = False
        self.fields['data_conclusao'].required = False
        self.fields['hora_inicio'].required = False
        self.fields['hora_fim'].required = False

