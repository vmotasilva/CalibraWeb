from django import forms
from django.contrib.auth import get_user_model

from kpi import calculo
from decimal import Decimal, InvalidOperation

from django.db import transaction

from kpi.models import Indicador, Medicao, SetorIndicador


def _linha_setor(s):
    """Linha de texto do setor: "Nome | meta | login" (partes vazias à direita são omitidas)."""
    meta = str(s.meta).replace('.', ',') if s.meta is not None else ''
    login = s.responsavel_analise.username if s.responsavel_analise_id else ''
    if login:
        return f'{s.nome} | {meta} | {login}'
    return f'{s.nome} | {meta}' if meta else s.nome


class IndicadorForm(forms.ModelForm):
    class Meta:
        model = Indicador
        fields = ['nome', 'area', 'unidade', 'meta', 'sentido', 'periodicidade',
                  'exibir_mensal', 'exibir_semanal', 'exibir_diario',
                  'motivos_diario', 'motivos_semanal', 'motivos_mensal',
                  'campos', 'formula', 'responsavel', 'responsavel_analise', 'ordem', 'descricao', 'ativo']
        widgets = {'descricao': forms.Textarea(attrs={'rows': 3}), 'campos': forms.Textarea(attrs={'rows': 3})}

    setores_texto = forms.CharField(
        label='Setores', required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Surfaçagem | 2,5\nAR | 1,8\nExpedição'}),
        help_text='Opcional. Um setor por linha, no formato "Nome | meta | login do responsável pela causa e análise". '
                  'Sem a meta, vale a meta geral; sem responsável, vale o responsável geral do indicador. '
                  'Sem setores, só o acompanhamento geral é usado.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['setores_texto'].initial = '\n'.join(
                _linha_setor(s) for s in self.instance.setores.select_related('responsavel_analise'))
        User = get_user_model()
        self.fields['responsavel_analise'].queryset = User.objects.filter(is_active=True).order_by('first_name', 'username')
        self.fields['responsavel_analise'].label_from_instance = lambda u: f'{u.get_full_name() or u.username} ({u.username})'
        self.fields['responsavel_analise'].empty_label = '— sem responsável —'
        self.fields['responsavel_analise'].label = 'Responsável pela causa e análise'
        for name, f in self.fields.items():
            f.widget.attrs['class'] = 'form-check-input' if name == 'ativo' or name.startswith(('exibir_', 'motivos_')) else 'form-control'
        self.fields['campos'].label = 'Variáveis do indicador'
        self.fields['campos'].help_text = 'Uma variável por linha (ex.: Lentes perdidas). A ordem define Var 01, Var 02... Elas são lançadas a cada dia, semana ou mês. Para uma variável só de tabela (ex.: Motivo), escreva "Motivo | tabela".'
        self.fields['campos'].widget.attrs['placeholder'] = 'Lentes perdidas\nLentes produzidas'
        self.fields['formula'].label = 'Memória de cálculo'
        self.fields['formula'].help_text = 'Use as variáveis pelo nome ou por Var 01, Var 02... Ex.: (Var 01 / Var 02) * 100. Digite para buscar as variáveis.'
        self.fields['formula'].widget.attrs['autocomplete'] = 'off'
        self.fields['ordem'].required = False
        self.fields['sentido'].widget.attrs['class'] = 'form-select'
        self.fields['responsavel_analise'].widget.attrs['class'] = 'form-select'
        self.fields['periodicidade'].widget.attrs['class'] = 'form-select'

    def clean(self):
        dados = super().clean()
        class _I:
            campos = dados.get('campos', '')
        campos = calculo.lista_campos(_I)
        try:
            formula = calculo.resolver_aliases(dados.get('formula', ''), campos)
        except ValueError as e:
            self.add_error('formula', str(e))
            return dados
        erro = calculo.validar_formula(formula, campos)
        if erro:
            self.add_error('formula', erro)
        else:
            dados['formula'] = formula  # grava com os nomes das variáveis (ex.: [Perdidas] / [Produzidas] * 100)
        return dados

    def clean_setores_texto(self):
        itens, vistos = [], set()
        for n, linha in enumerate(self.cleaned_data.get('setores_texto', '').splitlines(), start=1):
            linha = linha.strip()
            if not linha:
                continue
            partes = [x.strip() for x in linha.split('|')] + ['', '']
            nome, meta_txt, login = partes[0], partes[1].replace('%', '').replace(' ', ''), partes[2]
            if not nome or nome.lower() in vistos:
                raise forms.ValidationError(f'Linha {n}: setor vazio ou repetido.')
            vistos.add(nome.lower())
            meta = None
            if meta_txt:
                try:
                    meta = Decimal(meta_txt.replace('.', '').replace(',', '.') if ',' in meta_txt else meta_txt)
                except InvalidOperation:
                    raise forms.ValidationError(f'Linha {n}: meta inválida ("{meta_txt}").')
            resp = None
            if login:
                resp = get_user_model().objects.filter(username__iexact=login, is_active=True).first()
                if resp is None:
                    raise forms.ValidationError(f'Linha {n}: usuário "{login}" não encontrado (use o login).')
            itens.append((nome[:100], meta, resp))
        if self.instance.pk:
            removidos = [s for s in self.instance.setores.all() if s.nome.lower() not in vistos]
            usados = [s.nome for s in removidos if s.medicoes.exists() or s.motivos.exists()]
            if usados:
                raise forms.ValidationError(
                    'Não é possível remover setor com lançamentos: ' + ', '.join(usados) + '. Mantenha-o na lista.')
        return itens

    def save(self, commit=True):
        obj = super().save(commit)
        if commit:
            self.salvar_setores(obj)
        return obj

    def salvar_setores(self, obj):
        itens = self.cleaned_data.get('setores_texto') or []
        with transaction.atomic():
            existentes = {s.nome.lower(): s for s in obj.setores.all()}
            nomes = set()
            for ordem, (nome, meta, resp) in enumerate(itens, start=1):
                nomes.add(nome.lower())
                s = existentes.get(nome.lower())
                if s:
                    SetorIndicador.objects.filter(pk=s.pk).update(nome=nome, meta=meta, ordem=ordem, responsavel_analise=resp)
                else:
                    SetorIndicador.objects.create(indicador=obj, nome=nome, meta=meta, ordem=ordem, responsavel_analise=resp)
            for chave, s in existentes.items():
                if chave not in nomes:
                    s.delete()

    def clean_ordem(self):
        return self.cleaned_data.get('ordem') or 0


class MedicaoForm(forms.ModelForm):
    class Meta:
        model = Medicao
        fields = ['granularidade', 'periodo', 'valor', 'observacao']
