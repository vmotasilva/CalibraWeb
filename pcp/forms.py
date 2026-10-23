from django import forms

from organization.models import Setor
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
        fields = ['nome', 'sigla', 'inicio', 'fim', 'ordem', 'ativo']
        widgets = {'inicio': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
                   'fim': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M')}

    def clean(self):
        dados = super().clean()
        if bool(dados.get('inicio')) != bool(dados.get('fim')):
            self.add_error('fim', 'Informe início e fim do turno, ou deixe os dois em branco.')
        return dados


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


class PaginaOrganizacaoForm(_BootstrapMixin, forms.ModelForm):
    """Só o que é organização (grupo, ordem, máquina): pode ser ajustado mesmo em revisão vigente/obsoleta."""
    class Meta:
        model = Pagina
        fields = ['grupo', 'ordem', 'maquina']


class CampoForm(_BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Campo
        fields = ['item', 'etapa', 'descricao', 'especificacao', 'metodo', 'plano_reacao', 'responsavel', 'frequencia', 'frequencia_detalhe',
                  'tipo', 'lista', 'minimo', 'maximo', 'unidade', 'critico', 'ordem', 'ativo']
        widgets = {'especificacao': forms.Textarea(attrs={'rows': 2}), 'plano_reacao': forms.Textarea(attrs={'rows': 2})}
        labels = {'ordem': 'Nº no bloco'}

    def clean(self):
        dados = super().clean()
        if dados.get('tipo') == Campo.LISTA and not dados.get('lista'):
            self.add_error('lista', 'Escolha a lista de opções deste campo.')
        mn, mx = dados.get('minimo'), dados.get('maximo')
        if mn is not None and mx is not None and mn > mx:
            self.add_error('maximo', 'O máximo deve ser maior ou igual ao mínimo.')
        return dados


class ImportarPlanilhaForm(_BootstrapMixin, forms.Form):
    arquivo = forms.FileField(label='Planilha (.xlsx)', widget=forms.ClearableFileInput(attrs={'accept': '.xlsx'}))
    setor = forms.ModelChoiceField(label='Setor', queryset=Setor.objects.all())
    codigo = forms.CharField(label='Código do formulário', required=False, max_length=30,
                             help_text='Deixe em branco para ler do nome do arquivo (ex.: FOR.080.R15 - ... -> FOR.080).')
    revisao = forms.CharField(label='Revisão', required=False, max_length=10,
                              help_text='Deixe em branco para ler do nome do arquivo (ex.: R15).')
    titulo = forms.CharField(label='Título', required=False, max_length=150)
    substituir = forms.BooleanField(label='Substituir a revisão se ela já existir em rascunho', required=False)
    publicar = forms.BooleanField(label='Publicar como vigente ao importar', required=False,
                                  help_text='Por padrão entra como rascunho para você revisar antes de publicar.')

    def clean_arquivo(self):
        arq = self.cleaned_data['arquivo']
        if not arq.name.lower().endswith('.xlsx'):
            raise forms.ValidationError('Envie um arquivo .xlsx.')
        return arq


class ImportarRegistrosForm(_BootstrapMixin, forms.Form):
    arquivo = forms.FileField(label='Planilha com os registros (.xlsx)', widget=forms.ClearableFileInput(attrs={'accept': '.xlsx'}))
    formulario = forms.ModelChoiceField(
        label='Formulário', required=False, queryset=Formulario.objects.all(),
        help_text='Em branco: lido do nome do arquivo (ex.: FOR.080.R15 -> FOR.080).')
    revisao = forms.CharField(label='Revisão', required=False, max_length=10,
                              help_text='Em branco: a do nome do arquivo ou, se não existir, a vigente.')
    ano = forms.IntegerField(label='Ano dos registros', initial=2026, min_value=2000, max_value=2100)
    simular = forms.BooleanField(label='Apenas simular (não grava nada)', required=False, initial=True,
                                 help_text='Recomendado na primeira vez: mostra o que seria importado.')
    ajustar_tipos = forms.BooleanField(
        label='Ajustar o tipo dos itens pelos registros', required=False, initial=True,
        help_text='Itens de lista em que quase tudo o que foi lançado é número passam a ser numéricos. Veja o resultado na simulação.')
    rastreio = forms.BooleanField(label='Atrasos contam desde o primeiro registro importado', required=False,
                                  help_text='Recua a vigência do formulário até o primeiro registro, para o histórico entrar nos atrasos. '
                                            'Sem isso, o histórico fica só para consulta.')

    def clean_arquivo(self):
        arq = self.cleaned_data['arquivo']
        if not arq.name.lower().endswith('.xlsx'):
            raise forms.ValidationError('Envie um arquivo .xlsx.')
        return arq
