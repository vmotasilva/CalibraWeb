"""Regras de negócio do Retrabalho CF (Controle Final): cadastros padrão, formulário dinâmico, cálculos e sincronizações."""
import re
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django import forms
from django.core.validators import MinValueValidator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from maquinas.models import Maquina
from rh.models import Colaborador

from .hc_rendimento import norm
from .models import (
    CFCadastro,
    CFCampoFormulario,
    EquipeCF,
    EquipeCoating,
    RegraTurnoCoating,
    RetrabalhoCFConfig,
    RetrabalhoCFItem,
    RetrabalhoCFRegistro,
    TratamentoAntiReflexo,
)

MOTIVOS_PADRAO = {
    "AR": ["Batida / Risco de Anel", "Mancha de Borracha", "Marca de Digital", "Ponto Branco (Material)", "Risco", "Saliva",
           "Sujeira de Máquina", "Sujeira de Manuseio", "Esqueceu de virar a lente", "Outros Motivos"],
    "HC": ["Mancha", "Ponto de Verniz", "Risco", "Trinca de verniz", "Verniz escorrido", "Outros motivos"],
    "CF": ["Batida FOG ID", "FOG ID errado", "Risco FOG ID", "Outros motivos"],
}
REPROVACAO_PADRAO = ["Lote Reprovado - Outros Motivos"]
ORIGENS = dict(CFCadastro.ORIGEM_CHOICES)
# chave, rótulo, tipo, obrigatório, visível
CAMPOS_PADRAO = [
    ("data", "Data", "DATA", True, True),
    ("turno", "Turno", "SELECAO", True, True),
    ("numero_lote", "Número do Lote", "TEXTO", False, True),
    ("total_lentes", "Total de Lentes no Lote", "NUMERO", True, True),
    ("maquina", "Máquina", "SELECAO", False, True),
    ("tratamento", "Tratamento", "SELECAO", False, True),
    ("colaborador_cf", "Colaborador CF - Responsável pela Inspeção do Lote", "SELECAO", True, True),
    ("colaborador_ar", "Colaborador AR - Responsável pela Montagem do Lote", "SELECAO", False, True),
    ("necessidade_retrabalho", "Necessidade de Retrabalho?", "SIM_NAO", True, True),
    ("retrabalho_motivos", "Retrabalho por Motivo", "NUMERO", False, True),
    ("lote_reprovado", "Lote Reprovado?", "SIM_NAO", False, True),
    ("motivo_reprovacao", "Motivo da Reprovação", "SELECAO", False, True),
    ("observacoes", "Observações", "TEXTO_LONGO", False, True),
]


def garantir_padroes():
    """Cria (sem sobrescrever) cadastros e campos padrão. Idempotente."""
    for origem, nomes in MOTIVOS_PADRAO.items():
        for i, nome in enumerate(nomes):
            CFCadastro.objects.get_or_create(tipo="MOTIVO", grupo=origem, nome=nome, defaults={"ordem": i})
    for i, nome in enumerate(REPROVACAO_PADRAO):
        CFCadastro.objects.get_or_create(tipo="REPROVACAO", grupo="", nome=nome, defaults={"ordem": i})
    for i, (chave, rotulo, tipo, obrig, visivel) in enumerate(CAMPOS_PADRAO):
        CFCampoFormulario.objects.get_or_create(
            chave=chave, defaults={"rotulo": rotulo, "tipo": tipo, "obrigatorio": obrig, "visivel": visivel, "ordem": i * 10, "sistema": True})
    RetrabalhoCFConfig.get()


# --------------------------------------------------------------------------- listas do formulário (com integração)
def maquinas_cf():
    """Máquinas do HMC (cadastro de Máquinas): evaporadoras; se não houver, todas as ativas."""
    qs = Maquina.objects.filter(Q(categoria__nome__icontains="evaporadora") | Q(nome__icontains="evaporadora")).distinct()
    if not qs.exists():
        qs = Maquina.objects.filter(status=True)
    return qs.order_by("codigo")


def colaboradores_cf():
    ids = list(EquipeCF.objects.filter(ativo=True).values_list("colaborador_id", flat=True))
    qs = Colaborador.objects.filter(pk__in=ids) if ids else Colaborador.objects.filter(is_active=True)
    return qs.order_by("nome_completo")


def colaboradores_montagem():
    """Quem monta os lotes vem da Equipe Coating (HMC > Anti-Reflexo); sem equipe cadastrada, todos os ativos do RH."""
    ids = list(EquipeCoating.objects.filter(pode_montar=True).values_list("colaborador_id", flat=True))
    qs = Colaborador.objects.filter(pk__in=ids, is_active=True) if ids else Colaborador.objects.filter(is_active=True)
    return qs.order_by("nome_completo")


def nome_maquina(m):
    return (m.nome or m.codigo) if m else ""


# --------------------------------------------------------------------------- formulário dinâmico
class RegistroCFForm(forms.Form):
    def __init__(self, *args, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        garantir_padroes()
        self.campos = [c for c in CFCampoFormulario.objects.all() if c.visivel or c.chave in CFCampoFormulario.CHAVES_OBRIGATORIAS]
        self.motivos = list(CFCadastro.objects.filter(tipo="MOTIVO", ativo=True))
        self.blocos = []
        for campo in self.campos:
            self._montar(campo)
        if instance is not None and not self.is_bound:
            self._carregar(instance)

    @staticmethod
    def _sim_nao(c, obrigatorio=True):
        return forms.ChoiceField(label=c.rotulo, required=obrigatorio, choices=[("0", "Não"), ("1", "Sim")], initial="0",
                                 widget=forms.Select(attrs={"class": "form-select"}))

    def _montar(self, c):
        k, sel, txt = c.chave, {"class": "form-select"}, {"class": "form-control"}
        dep = ""
        if k == "data":
            f = forms.DateField(label=c.rotulo, required=True, widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"))
        elif k == "turno":
            f = forms.ModelChoiceField(label=c.rotulo, required=c.obrigatorio, queryset=RegraTurnoCoating.objects.filter(ativo=True), widget=forms.Select(attrs=sel))
        elif k == "numero_lote":
            f = forms.CharField(label=c.rotulo, required=c.obrigatorio, max_length=30, widget=forms.TextInput(attrs=txt))
        elif k == "total_lentes":
            f = forms.IntegerField(label=c.rotulo, required=True, validators=[MinValueValidator(1)],
                                   widget=forms.NumberInput(attrs={"class": "form-control", "min": 1, "inputmode": "numeric"}))
        elif k == "maquina":
            f = forms.ModelChoiceField(label=c.rotulo, required=c.obrigatorio, queryset=maquinas_cf(), widget=forms.Select(attrs=sel))
        elif k == "tratamento":
            f = forms.ModelChoiceField(label=c.rotulo, required=c.obrigatorio, queryset=TratamentoAntiReflexo.objects.filter(ativo=True), widget=forms.Select(attrs=sel))
        elif k == "colaborador_cf":
            f = forms.ModelChoiceField(label=c.rotulo, required=c.obrigatorio, queryset=colaboradores_cf(), widget=forms.Select(attrs=sel))
        elif k == "colaborador_ar":
            f = forms.ModelChoiceField(label=c.rotulo, required=c.obrigatorio, queryset=colaboradores_montagem(), widget=forms.Select(attrs=sel))
        elif k == "necessidade_retrabalho":
            f = self._sim_nao(c)
        elif k == "lote_reprovado":
            f = self._sim_nao(c, obrigatorio=False)
        elif k == "motivo_reprovacao":
            opcoes = [(n, n) for n in CFCadastro.objects.filter(tipo="REPROVACAO", ativo=True).values_list("nome", flat=True)]
            f = forms.ChoiceField(label=c.rotulo, required=False, choices=[("", "---------")] + opcoes, widget=forms.Select(attrs=sel))
            dep = "reprovado"
        elif k == "observacoes":
            f = forms.CharField(label=c.rotulo, required=c.obrigatorio, widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}))
        elif k == "retrabalho_motivos":
            grupos = []
            for origem, nome_origem in CFCadastro.ORIGEM_CHOICES:
                campos = []
                for m in (m for m in self.motivos if m.grupo == origem):
                    self.fields[f"mt_{m.pk}"] = forms.IntegerField(label=m.nome, required=False, min_value=0,
                                                                   widget=forms.NumberInput(attrs={"class": "form-control", "min": 0, "inputmode": "numeric"}))
                    campos.append(self[f"mt_{m.pk}"])
                if campos:
                    grupos.append((nome_origem, campos))
            self.blocos.append({"campo": c, "grupo": True, "grupos": grupos, "campos": [], "dep": "retrabalho"})
            return
        else:
            f = HCExtra.campo(c)
        nome = f"x_{k}" if (f is not None and k not in _SISTEMA) else k
        self.fields[nome] = f
        f.help_text = c.ajuda
        self.blocos.append({"campo": c, "grupo": False, "campos": [self[nome]], "dep": dep})

    def _carregar(self, r):
        ini = {
            "data": r.data, "turno": r.turno_id, "numero_lote": r.numero_lote, "total_lentes": r.total_lentes, "maquina": r.maquina_id,
            "tratamento": r.tratamento_id, "colaborador_cf": r.colaborador_cf_id, "colaborador_ar": r.colaborador_ar_id,
            "necessidade_retrabalho": "1" if r.teve_retrabalho else "0", "lote_reprovado": "1" if r.reprovado else "0",
            "motivo_reprovacao": r.motivo_reprovacao, "observacoes": r.observacoes,
        }
        for item in r.itens.all():
            ini[f"mt_{item.motivo_id}"] = item.quantidade
        for k, v in (r.extras or {}).items():
            ini[f"x_{k}"] = v
        for nome, valor in ini.items():
            if nome in self.fields:
                self.initial[nome] = valor

    def clean(self):
        d = super().clean()
        if self.errors:
            return d
        total_lentes = d.get("total_lentes") or 0
        if d.get("necessidade_retrabalho") == "1":
            total = sum((d.get(n) or 0) for n in self.fields if n.startswith("mt_"))
            if not total:
                raise forms.ValidationError("Informe a quantidade retrabalhada por motivo.")
            if total > total_lentes:
                raise forms.ValidationError(f"O retrabalho ({total}) não pode ser maior que o total de lentes do lote ({total_lentes}).")
            d["_total_retrabalho"] = total
        else:
            d["_total_retrabalho"] = 0
        return d

    @transaction.atomic
    def save(self, usuario=None):
        d = self.cleaned_data
        r = self.instance or RetrabalhoCFRegistro(origem=RetrabalhoCFRegistro.ORIGEM_FORM, usuario=usuario)
        r.data = d["data"]
        r.turno = d.get("turno")
        r.turno_nome = r.turno.nome if r.turno else ""
        r.numero_lote = d.get("numero_lote") or ""
        r.total_lentes = d["total_lentes"]
        r.maquina = d.get("maquina")
        r.maquina_nome = nome_maquina(r.maquina)
        r.tratamento = d.get("tratamento")
        r.tratamento_nome = r.tratamento.nome if r.tratamento else ""
        r.colaborador_cf = d.get("colaborador_cf")
        r.colaborador_cf_nome = r.colaborador_cf.nome_completo if r.colaborador_cf else ""
        r.colaborador_ar = d.get("colaborador_ar")
        r.colaborador_ar_nome = r.colaborador_ar.nome_completo if r.colaborador_ar else ""
        r.teve_retrabalho = d.get("necessidade_retrabalho") == "1"
        r.qtd_retrabalho = d["_total_retrabalho"]
        r.reprovado = d.get("lote_reprovado") == "1"
        r.motivo_reprovacao = (d.get("motivo_reprovacao") or "") if r.reprovado else ""
        r.observacoes = d.get("observacoes") or ""
        extras = dict(r.extras or {})
        for nome in self.fields:
            if nome.startswith("x_"):
                v = d.get(nome)
                extras[nome[2:]] = v.isoformat() if isinstance(v, date) else (float(v) if isinstance(v, Decimal) else v)
        r.extras = extras
        r.save()
        r.itens.all().delete()
        if r.teve_retrabalho:
            RetrabalhoCFItem.objects.bulk_create(
                RetrabalhoCFItem(registro=r, motivo_id=int(n[3:]), quantidade=d[n]) for n in self.fields if n.startswith("mt_") and d.get(n))
        return r


_SISTEMA = {c[0] for c in CAMPOS_PADRAO}


class HCExtra:
    """Campos personalizados: reaproveita a construção do formulário do HC."""

    @staticmethod
    def campo(c):
        from .hc_rendimento import RegistroHCForm
        return RegistroHCForm._campo_extra(c, {"class": "form-select"}, {"class": "form-control"})


# --------------------------------------------------------------------------- cálculos
def pct(num, den, casas=2):
    return round(num / den * 100, casas) if den else None


def _n(v):
    return v or 0


def meta():
    return float(RetrabalhoCFConfig.get().meta_retrabalho)


def _base(inicio, fim):
    return RetrabalhoCFRegistro.objects.filter(data__gte=inicio, data__lte=fim)


def _dias(inicio, fim):
    dia = inicio
    while dia <= fim:
        yield dia
        dia += timedelta(days=1)


def _agg():
    rep = Q(reprovado=True)
    return dict(lentes=Sum("total_lentes"), lotes=Count("id"), ret=Sum("qtd_retrabalho"),
                lentes_rep=Sum("total_lentes", filter=rep), lotes_rep=Count("id", filter=rep))


def _linha(row):
    lentes, lotes, ret = _n(row.get("lentes")), _n(row.get("lotes")), _n(row.get("ret"))
    lr, nr = _n(row.get("lentes_rep")), _n(row.get("lotes_rep"))
    return {"lentes": lentes, "lotes": lotes, "ret": ret, "pct_ret": pct(ret, lentes), "lentes_rep": lr, "pct_lentes_rep": pct(lr, lentes),
            "lotes_rep": nr, "pct_lotes_rep": pct(nr, lotes)}


def geral(inicio, fim):
    por_dia = {r["data"]: r for r in _base(inicio, fim).values("data").annotate(**_agg())}
    origem_dia = defaultdict(lambda: defaultdict(int))
    itens = RetrabalhoCFItem.objects.filter(registro__data__gte=inicio, registro__data__lte=fim)
    for r in itens.values("registro__data", "motivo__grupo").annotate(q=Sum("quantidade")):
        origem_dia[r["registro__data"]][r["motivo__grupo"]] += r["q"]
    linhas = []
    for dia in _dias(inicio, fim):
        l = _linha(por_dia.get(dia, {}))
        l["data"] = dia
        for o in ("AR", "HC", "CF"):
            q = origem_dia[dia][o]
            l[o.lower()], l[f"pct_{o.lower()}"] = q, pct(q, l["lentes"])
        linhas.append(l)
    total = _linha(_base(inicio, fim).aggregate(**_agg()))
    tot_o = defaultdict(int)
    for r in itens.values("motivo__grupo").annotate(q=Sum("quantidade")):
        tot_o[r["motivo__grupo"]] += r["q"]
    for o in ("AR", "HC", "CF"):
        total[o.lower()], total[f"pct_{o.lower()}"] = tot_o[o], pct(tot_o[o], total["lentes"])
    return {"linhas": linhas, "total": total, "meta": meta()}


def hora_registro(r):
    """Hora (0-23) do lançamento, ou None se não for confiável.

    O modelo não guarda a hora da inspeção: só `data` e `criado_em`. A hora de `criado_em` vale quando o lote foi
    lançado pelo formulário no próprio dia; importações e lançamentos retroativos ficam sem hora.
    """
    if r.origem != RetrabalhoCFRegistro.ORIGEM_FORM or not r.criado_em:
        return None
    local = timezone.localtime(r.criado_em)
    return local.hour if local.date() == r.data else None


def por_hora(dia):
    """Mesmos indicadores do consolidado diário, calculados por hora de lançamento no dia."""
    regs = list(RetrabalhoCFRegistro.objects.filter(data=dia))
    ids = [r.pk for r in regs]
    motivos = defaultdict(lambda: defaultdict(int))
    for it in RetrabalhoCFItem.objects.filter(registro_id__in=ids).select_related("motivo"):
        motivos[it.registro_id][it.motivo.grupo] += it.quantidade
    acc = defaultdict(lambda: {"lentes": 0, "lotes": 0, "ret": 0, "lentes_rep": 0, "lotes_rep": 0, "AR": 0, "HC": 0, "CF": 0})
    for r in regs:
        a = acc[hora_registro(r)]
        a["lentes"] += r.total_lentes
        a["lotes"] += 1
        a["ret"] += r.qtd_retrabalho
        if r.reprovado:
            a["lentes_rep"] += r.total_lentes
            a["lotes_rep"] += 1
        for o in ("AR", "HC", "CF"):
            a[o] += motivos[r.pk][o]

    def montar(a):
        l = _linha(a)
        for o in ("AR", "HC", "CF"):
            l[o.lower()], l[f"pct_{o.lower()}"] = a[o], pct(a[o], l["lentes"])
        return l

    horas = sorted(h for h in acc if h is not None)
    linhas = []
    for h in (range(horas[0], horas[-1] + 1) if horas else []):
        l = montar(acc.get(h, {"lentes": 0, "lotes": 0, "ret": 0, "lentes_rep": 0, "lotes_rep": 0, "AR": 0, "HC": 0, "CF": 0}))
        l["hora"], l["rotulo"] = h, f"{h:02d}h"
        linhas.append(l)
    sem_hora = montar(acc[None]) if None in acc else None
    if sem_hora:
        sem_hora["rotulo"] = "Sem horário"
    total = montar({k: sum(a[k] for a in acc.values()) for k in ("lentes", "lotes", "ret", "lentes_rep", "lotes_rep", "AR", "HC", "CF")})
    return {"linhas": linhas, "sem_hora": sem_hora, "total": total, "meta": meta(), "dia": dia}


def retrabalho_motivo(inicio, fim):
    itens = RetrabalhoCFItem.objects.filter(registro__data__gte=inicio, registro__data__lte=fim)
    turnos = sorted({t for t in _base(inicio, fim).values_list("turno_nome", flat=True).distinct() if t})
    por = defaultdict(int)
    for r in itens.values("motivo_id", "registro__turno_nome").annotate(q=Sum("quantidade")):
        por[(r["motivo_id"], r["registro__turno_nome"])] += r["q"]
    total = sum(por.values())
    usados = {k[0] for k in por}
    grupos = []
    for origem, nome in CFCadastro.ORIGEM_CHOICES:
        linhas = []
        for m in CFCadastro.objects.filter(tipo="MOTIVO", grupo=origem).filter(Q(ativo=True) | Q(pk__in=usados)):
            q = sum(v for (mid, _t), v in por.items() if mid == m.pk)
            linhas.append({"nome": m.nome, "total": q, "pct": pct(q, total),
                           "turnos": [{"qtd": por.get((m.pk, t), 0), "pct": pct(por.get((m.pk, t), 0), total)} for t in turnos]})
        grupos.append({"origem": origem, "nome": nome, "linhas": linhas, "total": sum(l["total"] for l in linhas),
                       "pct": pct(sum(l["total"] for l in linhas), total)})
    return {"turnos": turnos, "grupos": grupos, "total": total}


def _filtro_pessoa(papel, chave):
    fk, nome = f"colaborador_{papel}", f"colaborador_{papel}_nome"
    if chave.startswith("id:") and chave[3:].isdigit():
        return Q(**{f"{fk}_id": int(chave[3:])})
    if chave.startswith("nome:"):
        return Q(**{f"{fk}__isnull": True, nome: chave[5:]})
    return None


def lista_colaboradores(papel):
    fk, nome = f"colaborador_{papel}", f"colaborador_{papel}_nome"
    out = {}
    for r in RetrabalhoCFRegistro.objects.values(f"{fk}_id", f"{fk}__nome_completo", nome).distinct():
        if r[f"{fk}_id"]:
            out[f"id:{r[f'{fk}_id']}"] = r[f"{fk}__nome_completo"]
        elif r[nome]:
            out[f"nome:{r[nome]}"] = r[nome]
    return sorted(out.items(), key=lambda kv: norm(kv[1]))


def _resumo_por(qs, rotulo_fn, campos):
    acc = defaultdict(lambda: {"lentes": 0, "lotes": 0, "ret": 0, "lentes_rep": 0, "lotes_rep": 0})
    for r in qs.values(*campos).annotate(**_agg()):
        a = acc[rotulo_fn(r)]
        for k in a:
            a[k] += _n(r[k])
    return sorted(({"nome": n, **_linha(v)} for n, v in acc.items()), key=lambda x: -x["lentes"])


def _linhas_diarias(qs, inicio, fim):
    por_dia = {r["data"]: r for r in qs.values("data").annotate(**_agg())}
    out = []
    for dia in _dias(inicio, fim):
        l = _linha(por_dia.get(dia, {}))
        l["data"] = dia
        out.append(l)
    return out


def analise_colaborador(papel, chave, inicio, fim):
    fk, nome = f"colaborador_{papel}", f"colaborador_{papel}_nome"
    base = _base(inicio, fim)
    resumo = _resumo_por(base, lambda r: r[f"{fk}__nome_completo"] or r[nome] or "Sem colaborador", [f"{fk}__nome_completo", nome])
    filtro = _filtro_pessoa(papel, chave or "")
    if filtro is None:
        return {"resumo": resumo, "linhas": None, "total": None, "motivos": [], "meta": meta()}
    qs = base.filter(filtro)
    somas = dict(RetrabalhoCFItem.objects.filter(registro__in=qs).values_list("motivo_id").annotate(q=Sum("quantidade")))
    motivos = [{"nome": str(m), "qtd": somas[m.pk]} for m in CFCadastro.objects.filter(pk__in=somas)]
    return {"resumo": resumo, "linhas": _linhas_diarias(qs, inicio, fim), "total": _linha(qs.aggregate(**_agg())),
            "motivos": sorted(motivos, key=lambda x: -x["qtd"]), "meta": meta()}


def analise_dimensao(dimensao, selecionado, inicio, fim):
    """dimensao: 'maquina' ou 'tratamento' (aba Retrabalho x Máquina / x Tratamento)."""
    campo = f"{dimensao}_nome"
    base = _base(inicio, fim)
    resumo = _resumo_por(base, lambda r: r[campo] or "Não informado", [campo])
    if not selecionado:
        return {"resumo": resumo, "linhas": None, "total": None, "meta": meta()}
    qs = base.filter(**{campo: "" if selecionado == "Não informado" else selecionado})
    return {"resumo": resumo, "linhas": _linhas_diarias(qs, inicio, fim), "total": _linha(qs.aggregate(**_agg())), "meta": meta()}


def colaborador_x_tratamento(papel, inicio, fim):
    fk, nome = f"colaborador_{papel}", f"colaborador_{papel}_nome"
    acc = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    trats = set()
    for r in _base(inicio, fim).values(f"{fk}__nome_completo", nome, "tratamento_nome").annotate(lentes=Sum("total_lentes"), ret=Sum("qtd_retrabalho")):
        quem, trat = r[f"{fk}__nome_completo"] or r[nome] or "Sem colaborador", r["tratamento_nome"] or "Não informado"
        trats.add(trat)
        acc[quem][trat][0] += _n(r["lentes"])
        acc[quem][trat][1] += _n(r["ret"])
    trats = sorted(trats)
    linhas = []
    for quem, d in acc.items():
        celulas = [{"lentes": d[t][0], "ret": d[t][1], "pct": pct(d[t][1], d[t][0])} for t in trats]
        lentes, ret = sum(d[t][0] for t in trats), sum(d[t][1] for t in trats)
        linhas.append({"nome": quem, "celulas": celulas, "lentes": lentes, "ret": ret, "pct": pct(ret, lentes)})
    return {"tratamentos": trats, "linhas": sorted(linhas, key=lambda x: -x["lentes"]), "meta": meta()}


def opcoes_dimensao(dimensao):
    campo = f"{dimensao}_nome"
    nomes = [n or "Não informado" for n in RetrabalhoCFRegistro.objects.values_list(campo, flat=True).distinct()]
    return sorted(set(nomes), key=norm)


# --------------------------------------------------------------------------- integração / sincronização
def _vinculos_pendentes():
    out = {}
    for papel, rotulo in (("cf", "Colaborador CF (inspeção)"), ("ar", "Colaborador AR (montagem)")):
        out[f"colab_{papel}"] = {"rotulo": rotulo, "tipo": "colaborador", "itens": list(
            RetrabalhoCFRegistro.objects.filter(**{f"colaborador_{papel}__isnull": True}).exclude(**{f"colaborador_{papel}_nome": ""})
            .values(f"colaborador_{papel}_nome").annotate(n=Count("id")).order_by("-n"))}
        out[f"colab_{papel}"]["itens"] = [{"nome": i[f"colaborador_{papel}_nome"], "n": i["n"]} for i in out[f"colab_{papel}"]["itens"]]
    out["maquina"] = {"rotulo": "Máquina", "tipo": "maquina", "itens": [
        {"nome": i["maquina_nome"], "n": i["n"]} for i in RetrabalhoCFRegistro.objects.filter(maquina__isnull=True).exclude(maquina_nome="")
        .values("maquina_nome").annotate(n=Count("id")).order_by("-n")]}
    out["tratamento"] = {"rotulo": "Tratamento", "tipo": "tratamento", "itens": [
        {"nome": i["tratamento_nome"], "n": i["n"]} for i in RetrabalhoCFRegistro.objects.filter(tratamento__isnull=True).exclude(tratamento_nome="")
        .values("tratamento_nome").annotate(n=Count("id")).order_by("-n")]}
    return out


def propostas_sincronizacao():
    equipe = {e.colaborador_id: e for e in EquipeCF.objects.select_related("colaborador")}
    inspetores = set(RetrabalhoCFRegistro.objects.exclude(colaborador_cf=None).values_list("colaborador_cf_id", flat=True))
    return {
        "adicionar": list(Colaborador.objects.filter(pk__in=inspetores, is_active=True).exclude(pk__in=equipe).order_by("nome_completo")),
        "inativos": [e for e in equipe.values() if e.ativo and not e.colaborador.is_active],
        "vinculos": _vinculos_pendentes(),
    }


@transaction.atomic
def aplicar_sincronizacao():
    p = propostas_sincronizacao()
    for c in p["adicionar"]:
        EquipeCF.objects.get_or_create(colaborador=c)
    desativados = EquipeCF.objects.filter(pk__in=[e.pk for e in p["inativos"]]).update(ativo=False)
    return len(p["adicionar"]), desativados


@transaction.atomic
def vincular(tipo, papel, nome, objeto_id):
    """Vincula um nome digitado nos lançamentos a um cadastro oficial. Devolve a quantidade atualizada."""
    if tipo == "colaborador":
        colab = Colaborador.objects.get(pk=objeto_id)
        fk, nm = f"colaborador_{papel}", f"colaborador_{papel}_nome"
        n = RetrabalhoCFRegistro.objects.filter(**{f"{fk}__isnull": True, nm: nome}).update(**{fk: colab, nm: colab.nome_completo})
        if papel == "cf":
            membro, _ = EquipeCF.objects.get_or_create(colaborador=colab)
            apelidos = [a.strip() for a in membro.apelidos.split(",") if a.strip()]
            if nome not in apelidos:
                membro.apelidos = ", ".join(apelidos + [nome])[:255]
                membro.save(update_fields=["apelidos"])
        return n
    if tipo == "maquina":
        m = Maquina.objects.get(pk=objeto_id)
        return RetrabalhoCFRegistro.objects.filter(maquina__isnull=True, maquina_nome=nome).update(maquina=m, maquina_nome=nome_maquina(m))
    t = TratamentoAntiReflexo.objects.get(pk=objeto_id)
    return RetrabalhoCFRegistro.objects.filter(tratamento__isnull=True, tratamento_nome=nome).update(tratamento=t, tratamento_nome=t.nome)


def resolver_colaborador(nome, candidatos, preferidos=()):
    """Nome digitado -> colaborador do RH: exato/apelido, prefixo único, ou único entre os preferidos."""
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
    ok = [c for c in pref if c.pk in preferidos]
    return ok[0] if len(ok) == 1 else None


def candidatos_colaborador():
    apelidos = {e.colaborador_id: {norm(a) for a in e.apelidos.split(",") if a.strip()} for e in EquipeCF.objects.all()}
    return [(c, {norm(c.nome_completo)} | apelidos.get(c.pk, set())) for c in Colaborador.objects.all()]


def preferidos_colaborador():
    return set(EquipeCF.objects.values_list("colaborador_id", flat=True)) | set(EquipeCoating.objects.values_list("colaborador_id", flat=True))


def _compacto(t):
    return re.sub(r"[^A-Z0-9]", "", norm(t))


def resolver_maquina(nome, maquinas):
    """Por igualdade de código/nome (sem pontuação) ou, se única, por inclusão."""
    alvo = _compacto(nome)
    if not alvo:
        return None
    ig = [m for m in maquinas if alvo in {_compacto(m.codigo), _compacto(m.nome)}]
    if len(ig) == 1:
        return ig[0]
    inc = [m for m in maquinas if alvo and (alvo in _compacto(m.codigo) or _compacto(m.codigo) in alvo) and _compacto(m.codigo)]
    return inc[0] if len(inc) == 1 else None
