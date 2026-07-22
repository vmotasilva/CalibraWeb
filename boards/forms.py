from django import forms
from boards.models import Board, Card, BoardSubSection, BoardLabel
from rh.models import Colaborador

class BoardForm(forms.ModelForm):
    class Meta:
        model = Board
        fields = ['nome', 'descricao', 'membros', 'todos_colaboradores']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome do Quadro'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Breve descrição do quadro...'}),
            'membros': forms.SelectMultiple(attrs={'class': 'form-select', 'size': 8}),
            'todos_colaboradores': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['membros'].queryset = Colaborador.objects.all().order_by('nome_completo')
        self.fields['membros'].required = False


class CardForm(forms.ModelForm):
    data_entrega = forms.DateField(
        input_formats=['%d/%m/%Y', '%Y-%m-%d'],
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control js-week-datepicker', 'type': 'text', 'autocomplete': 'off'}),
        label="Data de Entrega"
    )
    datetime_inicio = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        label="Data/Hora de Início"
    )
    datetime_fim = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        label="Data/Hora de Fim"
    )
    data_conclusao = forms.DateField(
        input_formats=['%d/%m/%Y', '%Y-%m-%d'],
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control js-week-datepicker', 'type': 'text', 'autocomplete': 'off'}),
        label="Data de Conclusão"
    )

    class Meta:
        model = Card
        fields = ['titulo', 'descricao', 'link_anexo', 'responsaveis', 'subsecao', 'prioridade', 'data_entrega', 'periodicidade', 'etiquetas', 'datetime_inicio', 'datetime_fim', 'data_conclusao']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Título da tarefa'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descrição detalhada...'}),
            'link_anexo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: https://...'}),
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
        
        from django.db.models import Q
        if board:
            # Todos os colaboradores ativos + os que já estão associados aos cartões deste quadro
            responsaveis_atuais_ids = list(Card.objects.filter(coluna__quadro=board).values_list('responsaveis__id', flat=True))
            responsaveis_atuais_ids = [r_id for r_id in responsaveis_atuais_ids if r_id is not None]
            self.fields['responsaveis'].queryset = Colaborador.objects.filter(
                Q(is_active=True) | Q(id__in=responsaveis_atuais_ids)
            ).distinct().order_by('nome_completo')
        else:
            self.fields['responsaveis'].queryset = Colaborador.objects.filter(is_active=True).order_by('nome_completo')
        
        self.fields['responsaveis'].required = False
        self.fields['data_entrega'].required = False
        self.fields['periodicidade'].required = False
        self.fields['data_conclusao'].required = False
        self.fields['datetime_inicio'].required = False
        self.fields['datetime_fim'].required = False
