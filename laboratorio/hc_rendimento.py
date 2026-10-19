"""Regras de negócio do Rendimento HC: cadastros padrão, formulário dinâmico, cálculos do dashboard e sincronizações."""
import unicodedata
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django import forms
from django.core.validators import MinValueValidator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from rh.models import Colaborador

from .models import (
    EquipeCoating,
    EquipeHC,
    HCCadastro,
    HCCampoFormulario,
    RegraTurnoCoating,
    RendimentoHCConfig,
    RendimentoHCItem,
    RendimentoHCRegistro,
    TratamentoAntiReflexo,
)

# --------------------------------------------------------------------------- cadastros padrão (vindos da planilha)
GARRAS_PADRAO = [
    ("Lente Nova", 1),
    ("1º Retrabalho", 2),
    ("2º Retrabalho", None),
    ("3º Retrabalho", None),
    ("Lente de Teste", None),
]
MATERIAIS_PADRAO = [
    "Orma / Orgânico / CR39",
    "Airwear / TFL / Poly",
    "Stylis 1.67 / Stylis 1.74",
    "Poly Blue UV",
    "Lista Negra / Terceiros (Outros Fabricantes)",
]
MOTIVOS_PADRAO = [
    "Ponto de Verniz",
    "Escorrido de Verniz",
    "Risco",
    "Mal Destratada",
    "Mancha/Embaçamento",
    "Queda na Máquina",
    "Sujeira não Identificada",
    "Empenada",
    "Trinca/Estrias de Verniz",
    "Ponto Poly Blue / Blue Cut",
    "Outros",
]
# chave, rótulo, tipo, obrigatório, visível
CAMPOS_PADRAO = [
    ("data", "Data", "DATA", True, True),
    ("turno", "Turno", "SELECAO", True, True),
    ("colaborador", "Colaborador", "SELECAO", True, True),
    ("numero_garra", "Número da Garra", "TEXTO", False, True),
    ("tipo_garra", "Tipo de Garra", "SELECAO", True, True),
    ("tratamento", "Tratamento", "SELECAO", False, False),
    ("qtd_lentes", "Quantidade de Lentes", "NUMERO", True, True),
    ("producao_materiais", "Quantidade de Lentes por Material", "NUMERO", False, True),
    ("teve_retrabalho", "Teve Retrabalho?", "SIM_NAO", True, True),
    ("retrabalho_materiais", "Quantidade de Retrabalho por Material", "NUMERO", False, True),
    ("retrabalho_motivos", "Retrabalho por Motivo", "NUMERO", False, True),
    ("observacoes", "Observações", "TEXTO_LONGO", False, True),
]


def garantir_padroes():
    """Cria (sem sobrescrever) os cadastros e campos padrão. Idempotente."""
    for i, (nome, passo) in enumerate(GARRAS_PADRAO):
        HCCadastro.objects.get_or_create(tipo=HCCadastro.TIPO_GARRA, nome=nome, defaults={"ordem": i, "passo": passo})
    for i, nome in enumerate(MATERIAIS_PADRAO):
        HCCadastro.objects.get_or_create(tipo=HCCadastro.TIPO_MATERIAL, nome=nome, defaults={"ordem": i})
    for i, nome in enumerate(MOTIVOS_PADRAO):
        HCCadastro.objects.get_or_create(tipo=HCCadastro.TIPO_MOTIVO, nome=nome, defaults={"ordem": i})
    for i, (chave, rotulo, tipo, obrig, visivel) in enumerate(CAMPOS_PADRAO):
        HCCampoFormulario.objects.get_or_create(
            chave=chave,
            defaults={"rotulo": rotulo, "tipo": tipo, "obrigatorio": obrig, "visivel": visivel, "ordem": i * 10, "sistema": True},
        )
    RendimentoHCConfig.get()


def norm(texto):
    t = unicodedata.normalize("NFKD", texto or "")
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).upper().split())


# --------------------------------------------------------------------------- formulário dinâmico
def colaboradores_hc():
    """Colaboradores selecionáveis: equipe HC ativa; se ainda vazia, todos os colaboradores ativos do RH."""
    ids = list(EquipeHC.objects.filter(ativo=True).values_list("colaborador_id", flat=True))
    qs = Colaborador.objects.filter(pk__in=ids) if ids else Colaborador.objects.filter(is_active=True)
    return qs.order_by("nome_completo")


_PREFIXOS_BLOCO = {"producao_materiais": "pm_", "retrabalho_materiais": "rm_", "retrabalho_motivos": "rt_"}
_TIPO_POR_PREFIXO = {
    "pm_": RendimentoHCItem.PROD_MATERIAL,
    "rm_": RendimentoHCItem.RET_MATERIAL,
    "rt_": RendimentoHCItem.RET_MOTIVO,
}


class RegistroHCForm(forms.Form):
    """Formulário montado a partir da configuração (campos, materiais, motivos...)."""

    def __init__(self, *args, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        garantir_padroes()
        self.campos = [c for c in HCCampoFormulario.objects.all()
                       if c.visivel or c.chave in HCCampoFormulario.CHAVES_OBRIGATORIAS]
        self.materiais = list(HCCadastro.objects.filter(tipo=HCCadastro.TIPO_MATERIAL, ativo=True))
        self.motivos = list(HCCadastro.objects.filter(tipo=HCCadastro.TIPO_MOTIVO, ativo=True))
        self.blocos = []
        for campo in self.campos:
            self._montar(campo)
        if instance is not None and not self.is_bound:
            self._carregar(instance)

    @staticmethod
    def _num(label):
        return forms.IntegerField(label=label, required=False, min_value=0,
                                  widget=forms.NumberInput(attrs={"class": "form-control", "min": 0, "inputmode": "numeric"}))

    def _montar(self, c):
        k = c.chave
        sel = {"class": "form-select"}
        txt = {"class": "form-control"}
        if k == "data":
            self.fields[k] = forms.DateField(label=c.rotulo, required=True, widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"))
        elif k == "turno":
            self.fields[k] = forms.ModelChoiceField(label=c.rotulo, required=c.obrigatorio, queryset=RegraTurnoCoating.objects.filter(ativo=True), widget=forms.Select(attrs=sel))
        elif k == "colaborador":
            self.fields[k] = forms.ModelChoiceField(label=c.rotulo, required=c.obrigatorio, queryset=colaboradores_hc(), widget=forms.Select(attrs=sel))
        elif k == "tipo_garra":
            self.fields[k] = forms.ModelChoiceField(label=c.rotulo, required=c.obrigatorio, queryset=HCCadastro.objects.filter(tipo=HCCadastro.TIPO_GARRA, ativo=True), widget=forms.Select(attrs=sel))
        elif k == "tratamento":
            self.fields[k] = forms.ModelChoiceField(label=c.rotulo, required=c.obrigatorio, queryset=TratamentoAntiReflexo.objects.filter(ativo=True), widget=forms.Select(attrs=sel))
        elif k == "numero_garra":
            self.fields[k] = forms.CharField(label=c.rotulo, required=c.obrigatorio, max_length=10, widget=forms.TextInput(attrs=txt))
        elif k == "qtd_lentes":
            self.fields[k] = forms.IntegerField(label=c.rotulo, required=True, validators=[MinValueValidator(1)],
                                                widget=forms.NumberInput(attrs={"class": "form-control", "min": 1, "inputmode": "numeric"}))
        elif k == "teve_retrabalho":
            self.fields[k] = forms.ChoiceField(label=c.rotulo, required=True, choices=[("0", "Não"), ("1", "Sim")], initial="0", widget=forms.Select(attrs=sel))
        elif k == "observacoes":
            self.fields[k] = forms.CharField(label=c.rotulo, required=c.obrigatorio, widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}))
        elif k in _PREFIXOS_BLOCO:
            pref = _PREFIXOS_BLOCO[k]
            for m in (self.motivos if pref == "rt_" else self.materiais):
                self.fields[f"{pref}{m.pk}"] = self._num(m.nome)
            campos = [self[n] for n in self.fields if n.startswith(pref)]
            self.blocos.append({"campo": c, "grupo": True, "campos": campos, "so_retrabalho": k != "producao_materiais"})
            return
        else:
            self.fields[f"x_{k}"] = self._campo_extra(c, sel, txt)
        nome = f"x_{k}" if f"x_{k}" in self.fields else k
        self.fields[nome].help_text = c.ajuda
        self.blocos.append({"campo": c, "grupo": False, "campos": [self[nome]], "so_retrabalho": False})

    @staticmethod
    def _campo_extra(c, sel, txt):
        kw = {"label": c.rotulo, "required": c.obrigatorio}
        if c.tipo == c.TIPO_NUMERO:
            return forms.DecimalField(widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}), **kw)
        if c.tipo == c.TIPO_DATA:
            return forms.DateField(widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"), **kw)
        if c.tipo == c.TIPO_SELECAO:
            return forms.ChoiceField(choices=[("", "---------")] + [(o, o) for o in c.lista_opcoes], widget=forms.Select(attrs=sel), **kw)
        if c.tipo == c.TIPO_SIM_NAO:
            return forms.ChoiceField(choices=[("", "---------"), ("Sim", "Sim"), ("Não", "Não")], widget=forms.Select(attrs=sel), **kw)
        if c.tipo == c.TIPO_TEXTO_LONGO:
            return forms.CharField(widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}), **kw)
        return forms.CharField(max_length=255, widget=forms.TextInput(attrs=txt), **kw)

    def _carregar(self, r):
        ini = {
            "data": r.data, "turno": r.turno_id, "colaborador": r.colaborador_id, "numero_garra": r.numero_garra,
            "tipo_garra": r.tipo_garra_id, "tratamento": r.tratamento_id, "qtd_lentes": r.qtd_lentes,
            "teve_retrabalho": "1" if r.teve_retrabalho else "0", "observacoes": r.observacoes,
        }
        for item in r.itens.all():
            ini[f"{item.tipo.lower()}_{item.cadastro_id}"] = item.quantidade
        for k, v in (r.extras or {}).items():
            ini[f"x_{k}"] = v
        for nome, valor in ini.items():
            if nome in self.fields:
                self.initial[nome] = valor

    # -- validação
    def _soma(self, prefixo):
        return sum((self.cleaned_data.get(n) or 0) for n in self.fields if n.startswith(prefixo))

    def clean(self):
        dados = super().clean()
        if self.errors:
            return dados
        qtd = dados.get("qtd_lentes") or 0
        if dados.get("teve_retrabalho") == "1":
            por_motivo, por_material = self._soma("rt_"), self._soma("rm_")
            total = por_motivo or por_material
            if not total:
                raise forms.ValidationError("Informe a quantidade retrabalhada (por motivo ou por material).")
            if por_motivo and por_material and por_motivo != por_material:
                raise forms.ValidationError(
                    f"A soma por motivo ({por_motivo}) difere da soma por material ({por_material}). Confira os valores."
                )
            if total > qtd:
                raise forms.ValidationError(f"O retrabalho ({total}) não pode ser maior que a quantidade de lentes ({qtd}).")
            dados["_total_retrabalho"] = total
        else:
            dados["_total_retrabalho"] = 0
        return dados

    # -- persistência
    @transaction.atomic
    def save(self, usuario=None):
        d = self.cleaned_data
        r = self.instance or RendimentoHCRegistro(origem=RendimentoHCRegistro.ORIGEM_FORM, usuario=usuario)
        r.data = d["data"]
        r.turno = d.get("turno")
        r.turno_nome = r.turno.nome if r.turno else ""
        r.colaborador = d.get("colaborador")
        r.colaborador_nome = r.colaborador.nome_completo if r.colaborador else ""
        r.numero_garra = d.get("numero_garra") or ""
        r.tipo_garra = d.get("tipo_garra")
        r.tratamento = d.get("tratamento")
        r.qtd_lentes = d["qtd_lentes"]
        r.teve_retrabalho = d.get("teve_retrabalho") == "1"
        r.qtd_retrabalho = d["_total_retrabalho"]
        r.observacoes = d.get("observacoes") or ""
        extras = dict(r.extras or {})
        for nome in self.fields:
            if nome.startswith("x_"):
                v = d.get(nome)
                extras[nome[2:]] = v.isoformat() if isinstance(v, date) else (float(v) if isinstance(v, Decimal) else v)
        r.extras = extras
        r.save()
        r.itens.all().delete()
        itens = []
        for nome in self.fields:
            pref = nome[:3]
            if pref in _TIPO_POR_PREFIXO:
                tipo = _TIPO_POR_PREFIXO[pref]
                q = d.get(nome) or 0
                if tipo != RendimentoHCItem.PROD_MATERIAL and not r.teve_retrabalho:
                    q = 0
                if q:
                    itens.append(RendimentoHCItem(registro=r, tipo=tipo, cadastro_id=int(nome[3:]), quantidade=q))
        RendimentoHCItem.objects.bulk_create(itens)
        return r


# --------------------------------------------------------------------------- cálculos
def pct(num, den, casas=2):
    return round(num / den * 100, casas) if den else None


def rend(prod, ret, casas=2):
    return round((1 - ret / prod) * 100, casas) if prod else None


def _n(v):
    return v or 0


def _base(inicio, fim):
    return RendimentoHCRegistro.objects.filter(data__gte=inicio, data__lte=fim)


def _agg_passos():
    p1, p2 = Q(tipo_garra__passo=1), Q(tipo_garra__passo=2)
    return dict(
        prod=Sum("qtd_lentes"), ret=Sum("qtd_retrabalho"),
        p1=Sum("qtd_lentes", filter=p1), r1=Sum("qtd_retrabalho", filter=p1),
        p2=Sum("qtd_lentes", filter=p2), r2=Sum("qtd_retrabalho", filter=p2),
    )


def _linha_passos(row):
    prod, ret = _n(row.get("prod")), _n(row.get("ret"))
    p1, r1, p2, r2 = _n(row.get("p1")), _n(row.get("r1")), _n(row.get("p2")), _n(row.get("r2"))
    return {
        "produzidas": prod, "retrabalho": ret, "pct_retrabalho": pct(ret, prod), "rendimento": rend(prod, ret),
        "prod1": p1, "ret1": r1, "pct_ret1": pct(r1, p1), "rend1": rend(p1, r1),
        "prod2": p2, "ret2": r2, "pct_ret2": pct(r2, p2), "rend2": rend(p2, r2),
    }


def meta():
    return float(RendimentoHCConfig.get().meta_rendimento)


def _dias(inicio, fim):
    dia = inicio
    while dia <= fim:
        yield dia
        dia += timedelta(days=1)


def consolidado(inicio, fim):
    """Aba Consolidado: uma linha por dia do período + total."""
    por_dia = {r["data"]: r for r in _base(inicio, fim).values("data").annotate(**_agg_passos())}
    linhas = []
    for dia in _dias(inicio, fim):
        linha = _linha_passos(por_dia.get(dia, {}))
        linha["data"] = dia
        linhas.append(linha)
    return {"linhas": linhas, "total": _linha_passos(_base(inicio, fim).aggregate(**_agg_passos())), "meta": meta()}


def hora_registro(r):
    """Hora (0-23) do lançamento, ou None se não for confiável.

    O modelo só guarda `data` e `criado_em`; a hora de `criado_em` vale quando a garra foi lançada pelo formulário
    no próprio dia. Importações e lançamentos retroativos ficam sem hora.
    """
    if r.origem != RendimentoHCRegistro.ORIGEM_FORM or not r.criado_em:
        return None
    local = timezone.localtime(r.criado_em)
    return local.hour if local.date() == r.data else None


def por_hora(dia):
    """Mesmos indicadores do consolidado (1º/2º passo e geral), por hora de lançamento no dia."""
    chaves = ("prod", "ret", "p1", "r1", "p2", "r2")
    acc = defaultdict(lambda: dict.fromkeys(chaves, 0))
    for r in RendimentoHCRegistro.objects.filter(data=dia).select_related("tipo_garra"):
        a = acc[hora_registro(r)]
        a["prod"] += r.qtd_lentes
        a["ret"] += r.qtd_retrabalho
        passo = r.tipo_garra.passo if r.tipo_garra_id else None
        if passo in (1, 2):
            a[f"p{passo}"] += r.qtd_lentes
            a[f"r{passo}"] += r.qtd_retrabalho
    horas = sorted(h for h in acc if h is not None)
    linhas = []
    for h in (range(horas[0], horas[-1] + 1) if horas else []):
        l = _linha_passos(acc.get(h, {}))
        l["hora"], l["rotulo"] = h, f"{h:02d}h"
        linhas.append(l)
    sem_hora = _linha_passos(acc[None]) if None in acc else None
    if sem_hora:
        sem_hora["rotulo"] = "Sem horário"
    total = _linha_passos({k: sum(a[k] for a in acc.values()) for k in chaves})
    return {"linhas": linhas, "sem_hora": sem_hora, "total": total, "meta": meta(), "dia": dia}


def _soma_por_cadastro(itens_qs, tipo_item, tipo_cadastro):
    """[(cadastro, soma)] — cadastros ativos mais os inativos que tenham movimento."""
    somas = dict(itens_qs.filter(tipo=tipo_item).values_list("cadastro_id").annotate(q=Sum("quantidade")))
    cadastros = HCCadastro.objects.filter(tipo=tipo_cadastro).filter(Q(ativo=True) | Q(pk__in=somas))
    return [(c, somas.get(c.pk, 0)) for c in cadastros]


def _tabela_material(inicio, fim):
    itens = RendimentoHCItem.objects.filter(registro__data__gte=inicio, registro__data__lte=fim)
    prod_total = _n(_base(inicio, fim).aggregate(s=Sum("qtd_lentes"))["s"])
    prod = {c.pk: q for c, q in _soma_por_cadastro(itens, RendimentoHCItem.PROD_MATERIAL, HCCadastro.TIPO_MATERIAL)}
    return [
        {"nome": c.nome, "prod": _n(prod.get(c.pk)), "pct_prod": pct(_n(prod.get(c.pk)), prod_total),
         "ret": ret, "pct_ret": pct(ret, _n(prod.get(c.pk))), "rend": rend(_n(prod.get(c.pk)), ret)}
        for c, ret in _soma_por_cadastro(itens, RendimentoHCItem.RET_MATERIAL, HCCadastro.TIPO_MATERIAL)
    ]


def _por_colaborador(qs, prod_total):
    acc = defaultdict(lambda: [0, 0])
    for r in qs.values("colaborador__nome_completo", "colaborador_nome").annotate(prod=Sum("qtd_lentes"), ret=Sum("qtd_retrabalho")):
        nome = r["colaborador__nome_completo"] or r["colaborador_nome"] or "Sem colaborador"
        acc[nome][0] += _n(r["prod"])
        acc[nome][1] += _n(r["ret"])
    return sorted(
        ({"nome": n, "prod": p, "pct_prod": pct(p, prod_total), "ret": r, "pct_ret": pct(r, p), "rend": rend(p, r)}
         for n, (p, r) in acc.items()),
        key=lambda x: -x["prod"],
    )


def _por_grupo(qs, campo, vazio, prod_total):
    return [
        {"nome": r[campo] or vazio, "prod": _n(r["prod"]), "pct_prod": pct(_n(r["prod"]), prod_total),
         "ret": _n(r["ret"]), "pct_ret": pct(_n(r["ret"]), _n(r["prod"])), "rend": rend(_n(r["prod"]), _n(r["ret"]))}
        for r in qs.values(campo).annotate(prod=Sum("qtd_lentes"), ret=Sum("qtd_retrabalho")).order_by(campo)
    ]


def analise_diaria(dia):
    qs = _base(dia, dia)
    total = _linha_passos(qs.aggregate(**_agg_passos()))
    prod = total["produzidas"]
    itens = RendimentoHCItem.objects.filter(registro__data=dia)
    motivos = [
        {"nome": c.nome, "qtd": q, "pct": pct(q, prod)}
        for c, q in _soma_por_cadastro(itens, RendimentoHCItem.RET_MOTIVO, HCCadastro.TIPO_MOTIVO)
    ]
    return {
        "total": total, "motivos": motivos, "materiais": _tabela_material(dia, dia),
        "turnos": _por_grupo(qs, "turno_nome", "Sem turno", prod),
        "garras": _por_grupo(qs, "tipo_garra__nome", "Sem tipo", prod),
        "colaboradores": _por_colaborador(qs, prod), "meta": meta(),
    }


def retrabalho_motivo(inicio, fim):
    """Matriz motivo x turno (quantidade e % sobre o retrabalho total do período)."""
    itens = RendimentoHCItem.objects.filter(tipo=RendimentoHCItem.RET_MOTIVO, registro__data__gte=inicio, registro__data__lte=fim)
    turnos = sorted({t for t in _base(inicio, fim).values_list("turno_nome", flat=True).distinct() if t})
    por = defaultdict(int)
    for r in itens.values("cadastro_id", "registro__turno_nome").annotate(q=Sum("quantidade")):
        por[(r["cadastro_id"], r["registro__turno_nome"])] += r["q"]
    total = sum(por.values())
    motivos = HCCadastro.objects.filter(tipo=HCCadastro.TIPO_MOTIVO).filter(Q(ativo=True) | Q(pk__in={k[0] for k in por}))
    linhas = []
    for m in motivos:
        q_total = sum(v for (cid, _t), v in por.items() if cid == m.pk)
        linhas.append({
            "nome": m.nome, "total": q_total, "pct": pct(q_total, total),
            "turnos": [{"qtd": por.get((m.pk, t), 0), "pct": pct(por.get((m.pk, t), 0), total)} for t in turnos],
        })
    return {"turnos": turnos, "linhas": linhas, "total": total}


def _filtro_colaborador(chave):
    """'id:12' ou 'nome:Fulano' -> filtro Q (ou None)."""
    if chave.startswith("id:") and chave[3:].isdigit():
        return Q(colaborador_id=int(chave[3:]))
    if chave.startswith("nome:"):
        return Q(colaborador__isnull=True, colaborador_nome=chave[5:])
    return None


def lista_colaboradores():
    out = {}
    for r in RendimentoHCRegistro.objects.values("colaborador_id", "colaborador__nome_completo", "colaborador_nome").distinct():
        if r["colaborador_id"]:
            out[f"id:{r['colaborador_id']}"] = r["colaborador__nome_completo"]
        elif r["colaborador_nome"]:
            out[f"nome:{r['colaborador_nome']}"] = r["colaborador_nome"]
    return sorted(out.items(), key=lambda kv: norm(kv[1]))


def _linhas_diarias(por_dia, inicio, fim):
    linhas = []
    for dia in _dias(inicio, fim):
        p, q = por_dia.get(dia, (0, 0))
        linhas.append({"data": dia, "prod": p, "ret": q, "pct_ret": pct(q, p), "rend": rend(p, q)})
    return linhas


def analise_colaborador(chave, inicio, fim):
    filtro = _filtro_colaborador(chave or "")
    if filtro is None:
        return None
    qs = _base(inicio, fim).filter(filtro)
    por_dia = {r["data"]: (_n(r["prod"]), _n(r["ret"]))
               for r in qs.values("data").annotate(prod=Sum("qtd_lentes"), ret=Sum("qtd_retrabalho"))}
    tot = qs.aggregate(prod=Sum("qtd_lentes"), ret=Sum("qtd_retrabalho"))
    p, q = _n(tot["prod"]), _n(tot["ret"])
    motivos = [
        {"nome": c.nome, "qtd": s}
        for c, s in _soma_por_cadastro(RendimentoHCItem.objects.filter(registro__in=qs), RendimentoHCItem.RET_MOTIVO, HCCadastro.TIPO_MOTIVO)
        if s
    ]
    return {"linhas": _linhas_diarias(por_dia, inicio, fim),
            "total": {"prod": p, "ret": q, "pct_ret": pct(q, p), "rend": rend(p, q)}, "motivos": motivos, "meta": meta()}


def retrabalho_ano(ano):
    """Aba Retrabalho x Ano: uma linha por mês."""
    qs = RendimentoHCRegistro.objects.filter(data__year=ano)
    por_mes = {r["data__month"]: r for r in qs.values("data__month").annotate(**_agg_passos())}
    nomes = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]
    linhas = []
    for mes in range(1, 13):
        linha = _linha_passos(por_mes.get(mes, {}))
        linha["mes"] = f"{nomes[mes - 1]}/{str(ano)[2:]}"
        linhas.append(linha)
    return {"linhas": linhas, "total": _linha_passos(qs.aggregate(**_agg_passos())), "meta": meta()}


def anos_disponiveis():
    anos = sorted({d.year for d in RendimentoHCRegistro.objects.dates("data", "year")}, reverse=True)
    return anos or [date.today().year]


def rendimento_material(material_id, inicio, fim):
    """Aba Rendimento por Material: dia a dia de um material + resumo de todos os materiais."""
    resumo = _tabela_material(inicio, fim)
    mat = HCCadastro.objects.filter(pk=material_id, tipo=HCCadastro.TIPO_MATERIAL).first() if material_id else None
    if not mat:
        return {"resumo": resumo, "material": None, "linhas": [], "total": None, "meta": meta()}
    itens = RendimentoHCItem.objects.filter(cadastro=mat, registro__data__gte=inicio, registro__data__lte=fim)
    prod, ret = defaultdict(int), defaultdict(int)
    for r in itens.values("tipo", "registro__data").annotate(q=Sum("quantidade")):
        if r["tipo"] == RendimentoHCItem.PROD_MATERIAL:
            prod[r["registro__data"]] += r["q"]
        elif r["tipo"] == RendimentoHCItem.RET_MATERIAL:
            ret[r["registro__data"]] += r["q"]
    por_dia = {d: (prod.get(d, 0), ret.get(d, 0)) for d in set(prod) | set(ret)}
    tp, tr = sum(prod.values()), sum(ret.values())
    return {"resumo": resumo, "material": mat, "linhas": _linhas_diarias(por_dia, inicio, fim),
            "total": {"prod": tp, "ret": tr, "pct_ret": pct(tr, tp), "rend": rend(tp, tr)}, "meta": meta()}


# --------------------------------------------------------------------------- sincronização com outros cadastros
def propostas_sincronizacao():
    """Compara Equipe Coating (HMC > Anti-Reflexo) e RH com a Equipe HC e devolve as propostas de ajuste."""
    hc = {e.colaborador_id: e for e in EquipeHC.objects.select_related("colaborador")}
    coating = {e.colaborador_id: e for e in EquipeCoating.objects.select_related("colaborador")}
    return {
        "adicionar": [coating[i].colaborador for i in coating if i not in hc and coating[i].colaborador.is_active],
        "inativos": [e for e in hc.values() if e.ativo and not e.colaborador.is_active],
        "fora_coating": [e for i, e in hc.items() if i not in coating],
        "sem_vinculo": list(
            RendimentoHCRegistro.objects.filter(colaborador__isnull=True).exclude(colaborador_nome="")
            .values("colaborador_nome").annotate(n=Count("id")).order_by("-n")
        ),
    }


@transaction.atomic
def aplicar_sincronizacao():
    """Adiciona à Equipe HC quem está na Equipe Coating e desativa quem foi inativado no RH."""
    p = propostas_sincronizacao()
    for colab in p["adicionar"]:
        EquipeHC.objects.get_or_create(colaborador=colab)
    desativados = EquipeHC.objects.filter(pk__in=[e.pk for e in p["inativos"]]).update(ativo=False)
    return len(p["adicionar"]), desativados


def candidatos_colaborador():
    """[(colaborador, {nomes normalizados})] — nome completo + apelidos da Equipe HC; a equipe HC tem prioridade."""
    apelidos = {e.colaborador_id: {norm(a) for a in e.apelidos.split(",") if a.strip()} for e in EquipeHC.objects.all()}
    cands = [(c, {norm(c.nome_completo)} | apelidos.get(c.pk, set())) for c in Colaborador.objects.all()]
    return sorted(cands, key=lambda x: x[0].pk not in apelidos)


def resolver_colaborador(nome, candidatos):
    """Associa um nome digitado (ex.: 'Matheus') a um colaborador do RH: exato/apelido ou prefixo único (equipe HC primeiro)."""
    alvo = norm(nome)
    if not alvo:
        return None
    exatos = [c for c, chaves in candidatos if alvo in chaves]
    if len(exatos) == 1:
        return exatos[0]
    tokens = alvo.split()
    pref = [c for c, chaves in candidatos if any(k.split()[: len(tokens)] == tokens for k in chaves)]
    if len(pref) == 1:
        return pref[0]
    hc_ids = set(EquipeHC.objects.values_list("colaborador_id", flat=True))
    na_equipe = [c for c in pref if c.pk in hc_ids]
    return na_equipe[0] if len(na_equipe) == 1 else None
