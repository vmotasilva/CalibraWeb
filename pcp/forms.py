from django import forms

from pcp.models import Campo, Formulario, Frequencia, ListaOpcoes, OpcaoLista, Pagina, Turno


class _BootstrapMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nome, campo in self.fields.items():
            w = campo.widget
            if isinstance(w, forms.CheckboxInput):
                w.attrs.setdefault('class', 'form-check-input')
            elif isinstance(w, forms.Select):
                w.attrs.setdefault('class', 'form-select')
            else:
                w.attrs.setdefault('class', 'form-control')


class TurnoForm(_BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Turno
        fields = ['nome', 'sigla', 'ordem', 'ativo']


class FrequenciaForm(_BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Frequencia
        fields = ['nome', 'periodicidade', 'ordem', 'ativo']


class ListaOpcoesForm(_BootstrapMixin, forms.ModelForm):
    opcoes_texto = forms.CharField(
        label='Opções', required=False, widget=forms.Textarea(attrs={'rows': 6}),
        help_text='Uma opção por linha. Termine a linha com " | nok" para marcar a opção como desvio '
                  '(ex.: "Não realizado | nok"). As demais contam como conformes.')

    class Meta:
        model = ListaOpcoes
        fields = ['nome', 'ativo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['opcoes_texto'].initial = '\n'.join(
                o.valor if o.conforme else f'{o.valor} | nok' for o in self.instance.opcoes.all())

    def save(self, commit=True):
        lista = super().save(commit)
        if commit:
            self.salvar_opcoes(lista)
        return lista

    def salvar_opcoes(self, lista):
        existentes = {o.valor: o for o in lista.opcoes.all()}
        mantidas = set()
        for ordem, linha in enumerate(self.cleaned_data.get('opcoes_texto', '').splitlines()):
            valor, _, marca = linha.partition('|')
            valor = valor.strip()
            if not valor or valor in mantidas:
                continue
            mantidas.add(valor)
            conforme = marca.strip().lower() != 'nok'
            op = existentes.get(valor)
            if op:
                op.ordem, op.conforme = ordem, conforme
                op.save(update_fields=['ordem', 'conforme'])
            else:
                OpcaoLista.objects.create(lista=lista, valor=valor, conforme=conforme, ordem=ordem)
        lista.opcoes.exclude(valor__in=mantidas).delete()


class FormularioForm(_BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Formulario
        fields = ['setor', 'codigo', 'titulo', 'ativo']


class NovaRevisaoForm(_BootstrapMixin, forms.Form):
    revisao = forms.CharField(label='Revisão', max_length=10)
    motivo = forms.CharField(label='O que mudou', required=False, widget=forms.Textarea(attrs={'rows': 3}))


class PaginaForm(_BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Pagina
        fields = ['nome', 'codigo_sistema', 'grupo', 'maquina', 'ordem', 'ativo']


class CampoForm(_BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Campo
        fields = ['item', 'descricao', 'especificacao', 'metodo', 'plano_reacao', 'responsavel', 'frequencia',
                  'tipo', 'lista', 'minimo', 'maximo', 'unidade', 'critico', 'ordem', 'ativo']
        widgets = {'especificacao': forms.Textarea(attrs={'rows': 2}), 'plano_reacao': forms.Textarea(attrs={'rows': 2})}

    def clean(self):
        dados = super().clean()
        if dados.get('tipo') == Campo.LISTA and not dados.get('lista'):
            self.add_error('lista', 'Escolha a lista de opções deste campo.')
        mn, mx = dados.get('minimo'), dados.get('maximo')
        if mn is not None and mx is not None and mn > mx:
            self.add_error('maximo', 'O máximo deve ser maior ou igual ao mínimo.')
        return dados
