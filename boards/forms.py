from django import forms
from boards.models import Board, Card
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
    class Meta:
        model = Card
        fields = ['titulo', 'descricao', 'responsavel', 'prioridade', 'data_entrega']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Título da tarefa'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descrição detalhada...'}),
            'responsavel': forms.Select(attrs={'class': 'form-select'}),
            'prioridade': forms.Select(attrs={'class': 'form-select'}),
            'data_entrega': forms.DateInput(attrs={'class': 'form-control js-week-datepicker', 'type': 'text'}),
        }

    def __init__(self, *args, **kwargs):
        board = kwargs.pop('board', None)
        super().__init__(*args, **kwargs)
        if board:
            # Filtra o responsável apenas para os membros desse quadro + o criador
            membros_ids = list(board.membros.values_list('id', flat=True))
            if board.criado_por:
                membros_ids.append(board.criado_por.id)
            self.fields['responsavel'].queryset = Colaborador.objects.filter(id__in=membros_ids, is_active=True).distinct().order_by('nome_completo')
        else:
            self.fields['responsavel'].queryset = Colaborador.objects.filter(is_active=True).order_by('nome_completo')
        
        self.fields['responsavel'].required = False
        self.fields['data_entrega'].required = False
