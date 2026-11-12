"""Provedores de slides do Modo Apresentação (telão).

Cada provedor recebe o usuário e devolve uma lista de slides em formato simples (dicts serializáveis em JSON).
O front (shared/templates/shared/telao.html) só sabe desenhar os tipos abaixo:

  tiles  {"itens": [{"rotulo", "valor", "tom", "nota"}]}
  cards  {"itens": [{"titulo", "texto", "tom", "tags": [..]}]}
  bars   {"itens": [{"rotulo", "pct", "txt", "tom"}]}
  chart  {"labels": [..], "valores": [..], "meta": n, "unidade": ".."}

`tom`: ok | alerta | critico | neutro.  Cada provedor respeita as permissões do usuário e nunca levanta
exceção para quem o chama (um módulo com falha apenas some da rotação).
"""
from __future__ import annotations

import contextvars
import logging
from datetime import datetime, timedelta
from typing import Callable

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

DURACAO_PADRAO = 15  # segundos por slide
CARDS_POR_SLIDE = 4
MAX_SLIDES_CARDS = 3
MAX_GRUPOS_OCORRENCIAS = 8
RESUMO_TEXTO = 110


_SEM_CACHE = contextvars.ContextVar("telao_sem_cache", default=False)
CACHE_SEGUNDOS = 45  # menor que o ciclo de atualização do player (60 s)


def _cache_get(chave):
    """Cache curto dos cálculos pesados; ignorado quando o telão pede dados frescos (sempre, via API)."""
    return None if _SEM_CACHE.get() else cache.get(chave)


def _slide(provedor, kind, titulo, subtitulo="", icone="bi-display", duracao=DURACAO_PADRAO, **dados):
    return {"provedor": provedor, "kind": kind, "titulo": titulo, "subtitulo": subtitulo,
            "icone": icone, "duracao": duracao, **dados}


def _lotes(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def _corta(texto, limite):
    texto = (texto or "").strip()
    return texto if len(texto) <= limite else texto[: limite - 1].rstrip() + "…"


def _fmt_num(v, casas=1):
    if v is None:
        return "—"
    txt = f"{float(v):,.{casas}f}"
    return txt.replace(",", "X").replace(".", ",").replace("X", ".")


def _tom_pct(pct):
    if pct is None:
        return "neutro"
    return "ok" if pct >= 95 else "alerta" if pct >= 80 else "critico"


# ---------------------------------------------------------------------------
# Ocorrências (todas as origens, via Central de Ocorrências)
# ---------------------------------------------------------------------------
def _quando(txt):
    try:
        return datetime.strptime(txt, "%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return datetime.min


def _sem_auditorias_inativas(itens):
    """Tira do telão as ocorrências de auditorias (modelos) inativadas ou arquivadas; a Central continua mostrando todas."""
    from django.db.models import Q

    from auditoria.models import ComentarioRespostaAuditoria

    ids = [int(i.uid.split(":")[1]) for i in itens if i.origem == "auditoria"]
    if not ids:
        return itens
    fora = set(ComentarioRespostaAuditoria.objects.filter(pk__in=ids).filter(
        Q(pergunta__modelo__ativo=False) | Q(pergunta__modelo__arquivado=True)).values_list("pk", flat=True))
    return [i for i in itens if not (i.origem == "auditoria" and int(i.uid.split(":")[1]) in fora)]


def _itens_ocorrencias(user, origem, f):
    """Ocorrências em aberto de uma origem, para embutir no slide do próprio módulo (vazio se desligado no modelo)."""
    from shared import ocorrencias as central

    if f.get("com_ocorrencias") == "nao":
        return []
    return _sem_auditorias_inativas(central.listar_ocorrencias(user, "abertas", origem))


def _colunas_cards(f):
    """Em quantas colunas os cards de ocorrência são divididos (configuração do card; padrão 1)."""
    return _col_barras((f or {}).get("oc_colunas"))


def _col_barras(v):
    """Número de colunas (2 a 4), "auto" (o player escolhe pelo tamanho do card) ou 1."""
    v = str(v or "")
    return int(v) if v in ("2", "3", "4") else "auto" if v == "auto" else 1


def _ultima_acao(i):
    """Última ação do plano (em aberto; senão a última concluída), ou None."""
    ativas = [p for p in i.plano if p.status == "ABERTA"] or [p for p in i.plano if p.status == "CONCLUIDA"]
    return ativas[-1] if ativas and (ativas[-1].descricao or "").strip() else None


def _texto_ocorrencia(i):
    """Texto do card: a última ação do plano, ou o texto da ocorrência se não houver ação."""
    a = _ultima_acao(i)
    return a.descricao.strip() if a else (i.descricao or "").strip()


def _prazo_ocorrencia(i):
    """Prazo da última ação do plano (ou o da ocorrência, se não houver ação)."""
    a = _ultima_acao(i)
    return a.prazo if a else i.prazo


def _slides_lista_ocorrencias(provedor, nome, lista, resumo, mostrar_coment, icone=None, colunas=1):
    """Slides de ocorrências de uma sessão: lista = [(item, título curto)]; cada card traz prazo, dias em aberto e comentários."""
    if not lista:
        return []
    hoje = timezone.localdate()
    lista = sorted(lista, key=lambda t: (not t[0].vencida, t[0].prazo is None, t[0].prazo or hoje, t[0].data_ordem))
    n_venc = sum(int(t[0].vencida) for t in lista)
    cards = []
    por_slide = CARDS_POR_SLIDE * (3 if colunas == "auto" else colunas)
    for t in lista[: por_slide * MAX_SLIDES_CARDS]:
        i, titulo_item, extra = t[0], t[1], (t[2] if len(t) > 2 else [])
        dias = max((hoje - timezone.localtime(i.data_ordem).date()).days, 0)
        prazo = _prazo_ocorrencia(i)
        tags = list(extra) + ([f"prazo {prazo:%d/%m/%Y}"] if prazo else []) + [f"{dias} d em aberto"]
        if i.responsaveis and not resumo:
            tags.append(", ".join(i.responsaveis[:2]))
        coment = []
        if mostrar_coment:
            todos = sorted(((_quando(c["quando"]), c) for p in i.plano for c in p.comentarios), key=lambda t: t[0], reverse=True)
            coment = [{"autor": c["autor"], "quando": c["quando"], "texto": _corta(c["texto"], 170)} for _, c in todos[:2]]
        txt = _texto_ocorrencia(i)
        texto = "" if resumo or txt in ("", titulo_item) else _corta(txt, 180)
        cards.append({"titulo": _corta(titulo_item, 110), "texto": texto, "tom": "critico" if i.vencida else "alerta",
                      "tags": tags, "comentarios": coment})
    sub = f"{len(lista)} em aberto" + (f" · {n_venc} vencida{'s' if n_venc != 1 else ''}" if n_venc else "")
    lotes = list(_lotes(cards, por_slide))
    return [_slide(provedor, "cards", nome, sub + (f" · parte {n}/{len(lotes)}" if len(lotes) > 1 else ""),
                   icone or lista[0][0].icon or "bi-exclamation-octagon", grupo=True, ocorr=True, colunas=colunas, itens=lote)
            for n, lote in enumerate(lotes, start=1)]


def _tag_equipamento(titulo):
    """'Avaria/Dano: VI-01 (HMC)' -> 'VI-01 · Avaria/Dano' (só código e tipo); outros formatos ficam como estão."""
    import re

    m = re.match(r"^(.+?):\s*(.+?)(?:\s*\([^)]*\))?$", titulo or "")
    return f"{m.group(2)} · {m.group(1)}" if m else (titulo or "")


def _slides_por_responsavel(provedor, nome, itens, mostrar_coment, colunas=1):
    """Um card por responsável e texto: quando várias ocorrências têm o mesmo texto, listam-se só código e tipo."""
    hoje = timezone.localdate()
    grupos = {}
    for i in itens:
        resp = ", ".join(i.responsaveis[:2]) or "Sem responsável"
        grupos.setdefault((resp, _texto_ocorrencia(i)), []).append(i)
    ordem = sorted(grupos.items(), key=lambda kv: (kv[0][0] == "Sem responsável", -sum(int(i.vencida) for i in kv[1]), -len(kv[1]), kv[0][0]))
    cards = []
    por_slide = CARDS_POR_SLIDE * (3 if colunas == "auto" else colunas)
    for (resp, texto), lista in ordem[: por_slide * MAX_SLIDES_CARDS]:
        dias = max(max((hoje - timezone.localtime(i.data_ordem).date()).days, 0) for i in lista)
        prazos = [p for p in (_prazo_ocorrencia(i) for i in lista) if p]
        coment = []
        if mostrar_coment:
            todos = sorted(((_quando(c["quando"]), c) for i in lista for p in i.plano for c in p.comentarios), key=lambda t: t[0], reverse=True)
            coment = [{"autor": c["autor"], "quando": c["quando"], "texto": _corta(c["texto"], 170)} for _, c in todos[:2]]
        cards.append({"titulo": resp, "texto": _corta(texto, 200), "tom": "critico" if any(i.vencida for i in lista) else "alerta",
                      "tags": [_tag_equipamento(i.titulo) for i in lista[:12]] + ([f"+{len(lista) - 12}"] if len(lista) > 12 else [])
                              + ([f"prazo {min(prazos):%d/%m/%Y}"] if prazos else []) + [f"mais antiga {dias} d"],
                      "comentarios": coment})
    n_venc = sum(int(i.vencida) for i in itens)
    sub = f"{len(itens)} em aberto" + (f" · {n_venc} vencida{'s' if n_venc != 1 else ''}" if n_venc else "") + " · por responsável"
    lotes = list(_lotes(cards, por_slide))
    return [_slide(provedor, "cards", f"{nome} — ocorrências", sub + (f" · parte {n}/{len(lotes)}" if len(lotes) > 1 else ""),
                   itens[0].icon or "bi-exclamation-octagon", grupo=True, ocorr=True, colunas=colunas, itens=lote)
            for n, lote in enumerate(lotes, start=1)]


def _filtrar_ocorrencias_metrologia(itens, f):
    """Aplica às ocorrências de metrologia os filtros do módulo (setores e tratativa da calibração do instrumento)."""
    setores = set(f.get("setores") or [])
    trat = f.get("tratativa") or ""
    if not itens or not (setores or trat):
        return itens
    from qms.models import OcorrenciaInstrumento

    pks = [int(i.uid.split(":")[1]) for i in itens]
    info = {}
    for oc in OcorrenciaInstrumento.objects.filter(pk__in=pks).select_related("instrumento__setor", "instrumento__categoria"):
        inst = oc.instrumento
        t = ((getattr(inst, "tratativa_calibracao", "") or (inst.categoria.tratativa_calibracao if getattr(inst, "categoria", None) else "") or "INTERNA")
             if inst else "INTERNA").upper()
        info[oc.pk] = (inst.setor.nome if inst and inst.setor_id else "", t == "EXTERNA")
    saida = []
    for i in itens:
        setor, externo = info.get(int(i.uid.split(":")[1]), ("", False))
        if setores and setor not in setores:
            continue
        if trat and externo != (trat == "externa"):
            continue
        saida.append(i)
    return saida


def _slides_ocorrencias_modulo(user, origem, nome, resumo, f):
    itens = _itens_ocorrencias(user, origem, f)
    if origem == "metrologia":
        itens = _filtrar_ocorrencias_metrologia(itens, f)
    if itens and not resumo and origem in ("metrologia", "pcp", "laboratorio"):
        return _slides_por_responsavel(origem, nome, itens, f.get("comentarios") != "nao", _colunas_cards(f))
    return _slides_lista_ocorrencias(origem, f"{nome} — ocorrências", [(i, i.titulo) for i in itens],
                                     resumo, not resumo and f.get("comentarios") != "nao", colunas=_colunas_cards(f))


def _com_ocorrencias(origem, nome):
    """Decorador: depois dos slides do módulo, vêm as ocorrências em aberto dele (e seus comentários)."""
    def deco(fn):
        import functools

        @functools.wraps(fn)
        def _w(user, resumo=False, filtros=None):
            f = filtros or {}
            return list(fn(user, resumo=resumo, filtros=filtros)) + _slides_ocorrencias_modulo(user, origem, nome, resumo, f)
        return _w
    return deco


def slides_ocorrencias(user, resumo=False, filtros=None):
    from shared import ocorrencias as central

    f = filtros or {}
    origens = set(f.get("origens") or [])
    itens = _sem_auditorias_inativas(central.listar_ocorrencias(user, "abertas"))
    if origens:
        itens = [i for i in itens if i.origem in origens]
    if f.get("apenas_vencidas"):
        itens = [i for i in itens if i.vencida]
    hoje = timezone.localdate()
    vencidas = [i for i in itens if i.vencida]
    minhas = [i for i in itens if i.envolve_usuario]
    slides = []
    escopo = ", ".join(central.ORIGENS[o].nome for o in origens if o in central.ORIGENS) if origens else "Todos os módulos"

    pessoal = f.get("abordagem") == "pessoal"
    sem_resp = [i for i in itens if not i.responsaveis]
    pessoas = {}  # responsável -> [em aberto, vencidas]; uma ocorrência com 2 responsáveis conta para os dois
    for i in itens:
        for nome in (i.responsaveis or ["Sem responsável"]):
            c = pessoas.setdefault(nome, [0, 0])
            c[0] += 1
            c[1] += int(i.vencida)
    mais_antiga = max((max((hoje - timezone.localtime(i.data_ordem).date()).days, 0) for i in itens), default=0)
    por_origem = {}
    for i in itens:
        por_origem[i.origem_nome] = por_origem.get(i.origem_nome, 0) + 1

    tiles = [
        {"rotulo": "Em aberto", "valor": len(itens), "tom": "alerta" if itens else "ok"},
        {"rotulo": "Vencidas", "valor": len(vencidas), "tom": "critico" if vencidas else "ok"},
    ]
    if pessoal:
        tiles.append({"rotulo": "Envolvem você", "valor": len(minhas), "tom": "neutro"})
    else:  # global: panorama sem apontar o que é de quem está logado
        tiles += [
            {"rotulo": "Sem responsável", "valor": len(sem_resp), "tom": "alerta" if sem_resp else "ok"},
            {"rotulo": "Responsáveis envolvidos", "valor": len([n for n in pessoas if n != "Sem responsável"]), "tom": "neutro"},
            {"rotulo": "Mais antiga", "valor": f"{mais_antiga} d", "tom": "alerta" if mais_antiga > 30 else "neutro"},
        ]
    tiles += [{"rotulo": nome, "valor": qtd, "tom": "neutro", "nota": "em aberto"}
              for nome, qtd in sorted(por_origem.items(), key=lambda kv: -kv[1])]
    slides.append(_slide("ocorrencias", "tiles", "Ocorrências em aberto", escopo, "bi-exclamation-triangle", itens=tiles))

    if not pessoal and not resumo and pessoas:  # gráfico por pessoa (some no modo resumido, que oculta nomes)
        ordem = sorted(pessoas.items(), key=lambda kv: (-kv[1][0], -kv[1][1], kv[0]))[:12]
        topo = ordem[0][1][0]
        slides.append(_slide("ocorrencias", "bars", "Ocorrências em aberto por responsável",
                             f"{len(pessoas)} responsável(is) · vermelho = tem ocorrência vencida", "bi-people", itens=[{
            "rotulo": nome, "pct": c[0] * 100 / topo, "tom": "critico" if c[1] else "alerta",
            "txt": f"{c[0]}" + (f"  ({c[1]} venc.)" if c[1] else ""),
        } for nome, c in ordem]))
    if not pessoal and len(por_origem) > 1:
        topo = max(por_origem.values())
        venc_origem = {}
        for i in vencidas:
            venc_origem[i.origem_nome] = venc_origem.get(i.origem_nome, 0) + 1
        slides.append(_slide("ocorrencias", "bars", "Ocorrências em aberto por módulo", "Origem das ocorrências",
                             "bi-diagram-3", itens=[{
            "rotulo": nome, "pct": qtd * 100 / topo, "tom": "critico" if venc_origem.get(nome) else "alerta",
            "txt": f"{qtd}" + (f"  ({venc_origem[nome]} venc.)" if venc_origem.get(nome) else ""),
        } for nome, qtd in sorted(por_origem.items(), key=lambda kv: -kv[1])]))

    # Origens cujo módulo já está na apresentação mostram as próprias ocorrências junto de seus indicadores
    embutidas = set(f.get("_embutidas") or [])
    mostrar_coment = not resumo and f.get("comentarios") != "nao"
    grupos = {}
    for i in itens:
        if i.origem in embutidas:
            continue
        grupo, titulo_item = i.origem_nome, i.titulo
        if i.origem == "auditoria" and " — " in i.titulo:
            grupo, titulo_item = (x.strip() for x in i.titulo.split(" — ", 1))
        grupos.setdefault(grupo, []).append((i, titulo_item))
    ordem = sorted(grupos.items(), key=lambda kv: (-sum(int(i.vencida) for i, _ in kv[1]), -len(kv[1]), kv[0]))
    for nome, lista in ordem[:MAX_GRUPOS_OCORRENCIAS]:
        slides += _slides_lista_ocorrencias("ocorrencias", nome, lista, resumo, mostrar_coment, colunas=_colunas_cards(f))
    return slides


# ---------------------------------------------------------------------------
# KPI (indicadores gerais ou por setor)
# ---------------------------------------------------------------------------
def slides_kpi(user, resumo=False, filtros=None):
    from kpi.models import Indicador
    from shared.permissions import has_view_access

    if not has_view_access(user, "kpi:painel"):
        return []
    f = filtros or {}
    ids = {int(x) for x in (f.get("indicadores") or []) if str(x).isdigit()}
    setores = set(f.get("setores") or [])
    graficos = f.get("graficos") or "fora"
    meses = int(f["meses"]) if str(f.get("meses") or "").isdigit() else 12
    dias = int(f["dias"]) if str(f.get("dias") or "").isdigit() else 0
    qs = Indicador.objects.filter(ativo=True).prefetch_related("medicoes", "setores", "motivos")
    if ids:
        qs = qs.filter(pk__in=ids)

    linhas = []  # (rótulo, indicador, série, última, meta, atingiu)
    setor_de = {}  # rótulo -> id do setor (None = geral), para remontar a série do gráfico
    for ind in qs:
        escopos = [(s, f"{ind.nome} · {s.nome}") for s in ind.setores.all() if s.nome in setores] if setores else [(None, ind.nome)]
        for setor, rotulo in escopos:
            sid = setor.pk if setor else None
            meta = setor.meta_efetiva if setor else ind.meta
            doIndSetor = [m for m in ind.medicoes.all() if m.setor_id == sid]
            serie = sorted((m for m in doIndSetor if m.granularidade == "mensal"), key=lambda m: m.periodo)[-meses:]
            if not serie and doIndSetor:  # sem mês lançado: mostra o que foi preenchido por último (dia ou semana)
                g = max(doIndSetor, key=lambda m: m.periodo).granularidade
                serie = sorted((m for m in doIndSetor if m.granularidade == g), key=lambda m: m.periodo)[-30:]
            if dias:  # últimos N dias: usa as medições diárias (se o indicador não tiver, mantém a série mensal)
                diarias = sorted((m for m in doIndSetor if m.granularidade == "diaria"), key=lambda m: m.periodo)
                if diarias:
                    corte = diarias[-1].periodo - timedelta(days=dias - 1)
                    serie = [m for m in diarias if m.periodo >= corte]
            ultima = serie[-1] if serie else None
            setor_de[rotulo] = sid
            linhas.append((rotulo, ind, serie, ultima, meta, ind.atingiu(ultima.valor, meta) if ultima else None))
    if f.get("apenas_fora"):
        linhas = [l for l in linhas if l[5] is False]
    if not linhas:
        return []

    ok = sum(1 for l in linhas if l[5] is True)
    fora = sum(1 for l in linhas if l[5] is False)
    escopo = " + ".join(sorted(setores)) if setores else ""
    # situação geral (cada contador pode ser ocultado) e, separados por um traço, os indicadores
    situacao = [("ocultar_na_meta", {"rotulo": "Na meta", "valor": ok, "tom": "ok"}),
                ("ocultar_fora", {"rotulo": "Fora da meta", "valor": fora, "tom": "critico" if fora else "ok"}),
                ("ocultar_sem_dado", {"rotulo": "Sem dado", "valor": len(linhas) - ok - fora, "tom": "neutro"})]
    itens_situacao = [{**i, "grupo": "situacao"} for chave, i in situacao if not f.get(chave)]
    itens_indicadores = [{
        "rotulo": rotulo, "valor": f"{_fmt_num(ult.valor, 2)}{ind.unidade}" if ult else "—",
        "tom": "neutro" if a is None else "ok" if a else "critico", "grupo": "indicador",
        "nota": f"meta {_fmt_num(meta, 2)}{ind.unidade} · {ult.periodo:%d/%m/%Y}" if ult and ult.granularidade != "mensal" else f"meta {_fmt_num(meta, 2)}{ind.unidade} · {ult.periodo:%m/%Y}" if ult else "sem lançamento",
    } for rotulo, ind, _s, ult, meta, a in linhas[:18]]
    slides = [_slide("kpi", "tiles", f"Indicadores{' — ' + escopo if escopo else ' — situação geral'}",
                     "Último mês lançado de cada indicador", "bi-speedometer2", itens=itens_situacao + itens_indicadores)]

    # ocorrências (cards de causa/análise) de cada indicador: entram logo depois do gráfico dele
    import re

    oc_por_ind = {}
    for i in _itens_ocorrencias(user, "kpi", f):
        m = re.search(r"ind=(\d+)", i.url_origem or "")
        resto = i.titulo.split(" — ", 1)[-1]
        if m and (not setores or any(f"· {x}" in resto for x in setores)):
            oc_por_ind.setdefault(int(m.group(1)), []).append((i, resto))
    mostrar_coment = not resumo and f.get("comentarios") != "nao"
    emitidos = set()

    def _ocorr(rotulo, ind):
        if ind.pk in oc_por_ind and ind.pk not in emitidos:
            emitidos.add(ind.pk)
            return _slides_lista_ocorrencias("kpi", f"{rotulo} — ocorrências", oc_por_ind[ind.pk], resumo, mostrar_coment, colunas=_colunas_cards(f))
        return []

    if graficos != "nenhum":
        escolhidos = [l for l in linhas if (graficos == "todos" and l[2]) or l[5] is False]
        for rotulo, ind, serie, ult, meta, a in escolhidos[:8]:
            situacao = "Fora da meta" if a is False else "Na meta" if a else "Sem dado"
            extra, empilhado = {}, None
            if f.get("serie") in _GRANULARIDADES_GRAFICO:  # período, janela e tipo escolhidos no card
                serie = _janela(sorted((m for m in ind.medicoes.all() if m.setor_id == setor_de.get(rotulo) and m.granularidade == f["serie"]),
                                       key=lambda m: m.periodo), f, f["serie"])
            if f.get("tipo_grafico") == "empilhadas":
                empilhado = _empilhado_por_setor(ind, f.get("serie") or "mensal", f)
            if empilhado:
                extra = dict(tipo="empilhadas", labels=empilhado["labels"], series=empilhado["series"], valores=empilhado["totais"], atingiu=None)
            else:
                extra = dict(tipo="barras" if f.get("tipo_grafico") in ("barras", "empilhadas") else "linha",
                             labels=[_rotulo_periodo(m) for m in serie], valores=[float(m.valor) for m in serie],
                             atingiu=[bool(ind.atingiu(m.valor, meta)) for m in serie])
            gran_txt = {"diaria": "diário", "semanal": "semanal", "mensal": "mensal"}.get(f.get("serie"), "")
            janela_txt = "última competência" if gran_txt and f.get("janela") == "competencia" else ""
            slides.append(_slide("kpi", "chart", rotulo, f"{situacao} · {'maior' if ind.sentido == 'maior' else 'menor'} é melhor" + (f" · {gran_txt}" if gran_txt else "") + (f" · {janela_txt}" if janela_txt else "")
                                 + (f" · últimos {dias} dias" if dias and not gran_txt and serie and serie[-1].granularidade == "diaria" else "")
                                 + (" · última medição lançada" if serie and serie[-1].granularidade != "mensal" and not dias and not gran_txt else ""),
                                 "bi-graph-down-arrow" if a is False else "bi-graph-up", meta=float(meta), unidade=ind.unidade, **extra))
            slides += _ocorr(rotulo, ind)
    if f.get("_motivos") or "motivos" in (f.get("cards") or []):  # só quando o card é pedido: não muda a Apresentação Geral
        for rotulo, ind, *_ in linhas[:8]:
            slides += _slide_motivos(ind, rotulo, f, setor_de.get(rotulo) if setores else False)
    for rotulo, ind, *_ in linhas:  # indicadores sem gráfico na apresentação, mas com ocorrência
        slides += _ocorr(rotulo, ind)
    return slides


_GRANULARIDADES_GRAFICO = ("diaria", "semanal", "mensal")
_PADRAO_ULTIMOS = {"diaria": 30, "semanal": 12, "mensal": 12}


def _rotulo_periodo(m):
    if m.granularidade == "mensal":
        return m.periodo.strftime("%m/%Y")
    if m.granularidade == "semanal":
        return f"S{m.periodo.isocalendar()[1]} ({m.periodo:%d/%m})"
    return m.periodo.strftime("%d/%m")


def _janela(lista, f, gran):
    """Recorta a série (ordenada por período): 'competencia' = só o último mês com dado; senão, os últimos N períodos."""
    if not lista:
        return []
    if f.get("janela") == "competencia":
        u = lista[-1].periodo
        return [m for m in lista if (m.periodo.year, m.periodo.month) == (u.year, u.month)]
    n = int(f["ultimos"]) if str(f.get("ultimos") or "").isdigit() and int(f["ultimos"]) > 0 else _PADRAO_ULTIMOS[gran]
    return lista[-n:]


def _empilhado_por_setor(ind, gran, f):
    """Barras empilhadas: uma fatia por setor do indicador (None se o indicador não tem medições por setor)."""
    nomes = {s.pk: s.nome for s in ind.setores.all()}
    meds = [m for m in ind.medicoes.all() if m.setor_id in nomes and m.granularidade == gran]
    if not meds:
        return None
    datas = sorted({m.periodo for m in meds})
    ref = [type("P", (), {"periodo": d, "granularidade": gran})() for d in datas]
    ref = _janela(ref, f, gran)
    if not ref:
        return None
    por = {(m.setor_id, m.periodo): float(m.valor) for m in meds}
    series = [{"nome": nome, "valores": [por.get((pk, r.periodo)) for r in ref]} for pk, nome in nomes.items()
              if any(por.get((pk, r.periodo)) is not None for r in ref)]
    return {"labels": [_rotulo_periodo(r) for r in ref], "series": series,
            "totais": [round(sum(s["valores"][i] or 0 for s in series), 2) for i in range(len(ref))]}


_PADRAO_MOTIVOS = {"diaria": 90, "semanal": 4, "mensal": 1}  # dias / semanas / meses, quando o card não define "últimos N"


def _periodo_motivos(m_data_gran, f, gran):
    """Datas (de uma granularidade) que entram no Top motivos: última competência (mês) ou os últimos N dias/semanas/meses."""
    datas = sorted(set(m_data_gran))
    ultimo = datas[-1]
    if f.get("janela") == "competencia":
        escolhidas = {d for d in datas if (d.year, d.month) == (ultimo.year, ultimo.month)}
        return escolhidas, f"competência {ultimo:%m/%Y}"
    n = int(f["ultimos"]) if str(f.get("ultimos") or "").isdigit() and int(f["ultimos"]) > 0 else _PADRAO_MOTIVOS[gran]
    if gran == "mensal":
        meses = sorted({(d.year, d.month) for d in datas})[-n:]
        return {d for d in datas if (d.year, d.month) in meses}, ("último mês" if n == 1 else f"últimos {n} meses")
    dias = n if gran == "diaria" else n * 7
    corte = ultimo - timedelta(days=dias - 1)
    return {d for d in datas if d >= corte}, (f"últimos {n} dias" if gran == "diaria" else f"últimas {n} semanas")


def _slide_motivos(ind, rotulo, f, setor_id=False):
    """Top principais motivos de um indicador (a mesma tabela do Painel de Indicadores), como barras.
    Período (diário/semanal/mensal) e janela de tempo como nos gráficos; sem período escolhido, usa o mais detalhado
    que o indicador tem (ex.: retorno de clientes só lança motivos por mês). Configurável: o que mostrar
    (quantidade, percentual ou ambos), barra de preenchimento e prioridade ao texto."""
    exibir = f.get("motivos_exibir") if f.get("motivos_exibir") in ("quantidade", "percentual") else "ambos"
    # sem filtro de setor: motivos de todos os setores; com filtro, só os do setor do card
    todos = [m for m in ind.motivos.all() if setor_id is False or m.setor_id == setor_id]
    gran = f.get("serie") if f.get("serie") in _GRANULARIDADES_GRAFICO else next(
        (g for g in _GRANULARIDADES_GRAFICO if any(m.granularidade == g for m in todos)), None)
    do_gran = [m for m in todos if m.granularidade == gran]
    if not do_gran:
        return []
    datas, descricao = _periodo_motivos([m.data for m in do_gran], f, gran)
    itens = [m for m in do_gran if m.data in datas]
    soma_por = {}
    for m in itens:
        a = soma_por.setdefault(m.descricao.strip().lower(), [m.descricao.strip(), 0])
        a[1] += m.quantidade
    limite = int(f["motivos_qtd"]) if str(f.get("motivos_qtd") or "").isdigit() and 1 <= int(f["motivos_qtd"]) <= 40 else 10
    colunas = _col_barras(f.get("motivos_colunas"))
    top = sorted(soma_por.values(), key=lambda a: a[1], reverse=True)[:limite]
    total = sum(a[1] for a in soma_por.values())
    if not top or not total:
        return []
    maior = top[0][1]

    def qtd(v):
        return _fmt_num(v, 0 if v == int(v) else 2)

    def texto(v):
        if exibir == "quantidade":
            return qtd(v)
        if exibir == "percentual":
            return f"{_fmt_num(v / total * 100, 1)}%"
        return f"{qtd(v)} · {_fmt_num(v / total * 100, 0)}%"

    return [_slide("kpi", "bars", rotulo, f"Top principais motivos · {descricao}", "bi-list-ol",
                   sem_barra=bool(f.get("motivos_sem_barra")), texto_prioritario=bool(f.get("motivos_texto")), colunas=colunas, itens=[{
        "rotulo": f"{n}. {nome}", "pct": float(v / maior * 100), "tom": "neutro", "txt": texto(v),
    } for n, (nome, v) in enumerate(top, 1)])]


# ---------------------------------------------------------------------------
# Auditoria (checklists periódicos: último ciclo fechado de cada modelo/relatório)
# ---------------------------------------------------------------------------
def _dados_modelo(modelo):
    chave = f"telao:auditoria:v4:{modelo.pk}"
    dados = _cache_get(chave)
    if dados is None:
        from auditoria.apresentacao import montar_apresentacao

        a = montar_apresentacao(modelo, max_ciclos=24)
        dados = {
            "nome": modelo.nome, "pct": a["pct_geral"], "variacao": a["variacao"],
            "ciclos": [{"label": c["label"], "pct": c["pct"]} for c in a["ciclos"]],
            "criticas": [{"pergunta": c["pergunta"], "ncs": c["ncs"], "semanas": c["semanas"]} for c in a["criticas"]],
            "abertas": a["total_ocorrencias_abertas"], "vencidas": a["ocorrencias_vencidas"],
            "periodo": a["periodo_txt"], "periodo_curto": a["ciclos"][-1]["periodo"] if a["ciclos"] else "", "tem_ciclo": a["base"] is not None,
        }
        cache.set(chave, dados, CACHE_SEGUNDOS)
    return dados


def slides_auditoria(user, resumo=False, filtros=None):
    from auditoria.models import ModeloAuditoria
    from auditoria.views import _filter_modelos_para_usuario
    from shared.permissions import has_module_access

    if not has_module_access(user, "auditoria"):
        return []
    f = filtros or {}
    ids = {int(x) for x in (f.get("modelos") or []) if str(x).isdigit()}
    secoes = set(f.get("secoes") or []) or {"conformidade", "evolucao", "pontos"}
    qs = _filter_modelos_para_usuario(user, ModeloAuditoria.objects.filter(ativo=True, arquivado=False))
    if ids:
        qs = qs.filter(pk__in=ids)
    modelos = list(qs.order_by("nome")[:10])
    dados = [d for d in (_dados_modelo(m) for m in modelos) if d["tem_ciclo"]]
    if not dados:
        return []
    ordenados = sorted(dados, key=lambda d: (d["pct"] is None, d["pct"] if d["pct"] is not None else 0))
    slides = []
    # configuração dos cards (como nos de KPI): gráfico de evolução e tabela de conformidade
    n_ciclos = int(f["ultimos"]) if str(f.get("ultimos") or "").isdigit() and int(f["ultimos"]) > 1 else 8
    tipo_graf = "barras" if f.get("tipo_grafico") == "barras" else "linha"
    conf_colunas = _col_barras(f.get("conf_colunas"))
    conf_qtd = int(f["conf_qtd"]) if str(f.get("conf_qtd") or "").isdigit() and 1 <= int(f["conf_qtd"]) <= 40 else None
    if "conformidade" in secoes:
        sem_barra, exibir = bool(f.get("conf_sem_barra")), f.get("conf_exibir")

        def _txt_conf(d):
            if d["pct"] is None:
                return "—"
            var = f"  ({'+' if d['variacao'] > 0 else ''}{_fmt_num(d['variacao'], 1)})" if d["variacao"] and exibir != "percentual" else ""
            return f"{_fmt_num(d['pct'], 1)}%{var}"

        slides.append(_slide("auditoria", "bars", "Conformidade — último ciclo fechado", "% de itens conformes por auditoria",
                             "bi-clipboard-check", sem_barra=sem_barra, texto_prioritario=bool(f.get("conf_texto")), colunas=conf_colunas, itens=[{
            "rotulo": d["nome"], "sub": f"({d['periodo_curto']})" if d["periodo_curto"] else "", "pct": d["pct"] or 0, "tom": _tom_pct(d["pct"]), "txt": _txt_conf(d),
        } for d in ordenados[:conf_qtd]]))
    oc_por_modelo = {}
    for i in _itens_ocorrencias(user, "auditoria", f):
        if " — " in i.titulo:
            nome_m, resto = (x.strip() for x in i.titulo.split(" — ", 1))
            oc_por_modelo.setdefault(nome_m, []).append((i, resto))
    mostrar_coment = not resumo and f.get("comentarios") != "nao"
    limite = 10 if ids or f.get("_pontos_sempre") else 4
    for n_mod, d in enumerate(ordenados):
        pontos = [c for c in d["ciclos"] if c["pct"] is not None][-n_ciclos:]
        if n_mod >= limite:  # além do limite de gráficos, só as ocorrências da auditoria
            slides += _slides_lista_ocorrencias("auditoria", f"{d['nome']} — ocorrências", oc_por_modelo.get(d["nome"], []), resumo, mostrar_coment, colunas=_colunas_cards(f))
            continue
        if "evolucao" in secoes and len(pontos) > 1:
            slides.append(_slide("auditoria", "chart", d["nome"], f"Evolução da conformidade · {d['periodo']}",
                                 "bi-graph-up", tipo=tipo_graf, labels=[c["label"] for c in pontos],
                                 valores=[c["pct"] for c in pontos], meta=100, unidade="%"))
        # o ponto de atenção que já tem ocorrência aberta aparece no detalhe dela (com NCs, texto e comentários)
        lista_oc, ja_detalhados = [], set()
        crit = {c["pergunta"][:90].strip(): c for c in d["criticas"]}
        for i, resto in oc_por_modelo.get(d["nome"], []):
            c = crit.get(resto)
            extra = ([f"{c['ncs']} NC"] + ([f"{c['semanas']} semana(s) seguidas"] if c["semanas"] else [])) if c else []
            if c:
                ja_detalhados.add(resto)
            lista_oc.append((i, resto, extra))
        restantes = [c for c in d["criticas"] if c["pergunta"][:90].strip() not in ja_detalhados]
        sempre = bool(f.get("_pontos_sempre"))  # card escolhido à mão: todo relatório aparece, mesmo sem pontos a listar
        if "pontos" in secoes and sempre and not restantes:
            restantes = d["criticas"]
        if "pontos" in secoes and sempre and not restantes:
            slides.append(_slide("auditoria", "cards", f"{d['nome']} — pontos de atenção",
                                 f"{d['abertas']} ocorrência(s) em aberto · {d['vencidas']} vencida(s)", "bi-flag", colunas=1,
                                 itens=[{"titulo": "Nenhum ponto de atenção no último ciclo", "texto": "", "tom": "ok", "tags": []}]))
        elif "pontos" in secoes and restantes:
            cols = _colunas_cards(f)
            lotes_p = list(_lotes(restantes, CARDS_POR_SLIDE * (3 if cols == "auto" else cols)))
            for n_p, lote in enumerate(lotes_p, start=1):
                slides.append(_slide("auditoria", "cards", f"{d['nome']} — pontos de atenção",
                                     f"{d['abertas']} ocorrência(s) em aberto · {d['vencidas']} vencida(s)"
                                     + (f" · parte {n_p}/{len(lotes_p)}" if len(lotes_p) > 1 else ""), "bi-flag",
                                     colunas=cols, itens=[{"titulo": _corta(c["pergunta"], 120), "texto": "", "tom": "critico",
                                             "tags": [f"{c['ncs']} NC", f"{c['semanas']} semana(s) seguidas"] if c["semanas"] else [f"{c['ncs']} NC"]}
                                            for c in lote]))
        slides += _slides_lista_ocorrencias("auditoria", f"{d['nome']} — ocorrências", lista_oc, resumo, mostrar_coment, colunas=_colunas_cards(f))
    return slides


# ---------------------------------------------------------------------------
# Metrologia (instrumentos vencidos / a vencer)
# ---------------------------------------------------------------------------
def _dados_metrologia():
    dados = _cache_get("telao:metrologia:v2")
    if dados is None:
        from metrologia.views.views import get_metrologia_dashboard_data

        d = get_metrologia_dashboard_data()
        dados = {
            "cotacoes": d["kpis"]["externo"]["cotacoes_abertas"],
            "orcamentos": d["kpis"]["externo"]["orcamentos_pendentes"],
            "instrumentos": [{
                "tag": i["tag"], "descricao": i["descricao"], "setor": i["setor_nome"], "status": i["status_situacao"],
                "data": i["data_proxima_calibracao_display"], "dias": i["dias_para_vencer"], "externo": not i["is_internal"],
                "ocorrencias": i["ocorrencias_count"],
            } for i in d["instrumentos"]],  # já vem ordenado: vencidos, a vencer, com ocorrência
        }
        cache.set("telao:metrologia:v2", dados, CACHE_SEGUNDOS)
    return dados


@_com_ocorrencias("metrologia", "Metrologia")
def slides_metrologia(user, resumo=False, filtros=None):
    from shared.permissions import has_module_access

    if not has_module_access(user, "metrologia"):
        return []
    f = filtros or {}
    d = _dados_metrologia()
    insts = d["instrumentos"]
    setores = set(f.get("setores") or [])
    trat = f.get("tratativa") or ""
    if setores:
        insts = [i for i in insts if i["setor"] in setores]
    if trat:
        insts = [i for i in insts if i["externo"] == (trat == "externa")]
    filtrado = bool(setores or trat)
    venc = sum(1 for i in insts if i["status"] == "VENCIDO")
    a30 = sum(1 for i in insts if i["status"] == "AVENCER_30")
    oc = sum(i["ocorrencias"] for i in insts)
    tiles = [
        {"rotulo": "Vencidos", "valor": venc, "tom": "critico" if venc else "ok"},
        {"rotulo": "A vencer em 30 dias", "valor": a30, "tom": "alerta" if a30 else "ok"},
        {"rotulo": "Em dia", "valor": len(insts) - venc - a30, "tom": "ok"},
        {"rotulo": "Ocorrências ativas", "valor": oc, "tom": "alerta" if oc else "ok"},
    ]
    if not filtrado:
        tiles += [{"rotulo": "Cotações abertas", "valor": d["cotacoes"], "tom": "neutro"},
                  {"rotulo": "Orçamentos pendentes", "valor": d["orcamentos"], "tom": "neutro"}]
    escopo = " · ".join(filter(None, [", ".join(sorted(setores)), {"interna": "calibração interna", "externa": "calibração externa"}.get(trat)]))
    slides = [_slide("metrologia", "tiles", "Metrologia — calibrações", escopo or f"{len(insts)} instrumentos ativos",
                     "bi-tools", itens=tiles)]
    cards = []
    colunas = _col_barras(f.get("oc_colunas") or "auto")
    por_slide = CARDS_POR_SLIDE * (3 if colunas == "auto" else colunas)
    for i in [x for x in insts if x["status"] in ("VENCIDO", "AVENCER_30")][: por_slide * MAX_SLIDES_CARDS]:
        venceu = i["status"] == "VENCIDO"
        tags = [i["setor"], f"{'venceu' if venceu else 'vence'} em {i['data']}",
                "calibração externa" if i["externo"] else "calibração interna"]
        if i["ocorrencias"]:
            tags.append("com ocorrência")
        cards.append({"titulo": f"{i['tag']} — {_corta(i['descricao'], 70)}", "texto": "",
                      "tom": "critico" if venceu else "alerta", "tags": tags})
    for n, lote in enumerate(_lotes(cards, por_slide), start=1):
        slides.append(_slide("metrologia", "cards", "Instrumentos críticos", f"parte {n}" if len(cards) > por_slide else "",
                             "bi-exclamation-octagon", colunas=colunas, itens=lote))
    return slides


# ---------------------------------------------------------------------------
# PCP (cumprimento das verificações; um formulário = um setor)
# ---------------------------------------------------------------------------
def _dados_pcp(formulario_id=None, dias=30):
    chave = f"telao:pcp:v4:{formulario_id or 0}:{dias}"
    dados = _cache_get(chave)
    if dados is None:
        import datetime

        from pcp import pendencias as pend
        from pcp.models import Turno

        hoje = timezone.localdate()
        fim = hoje - datetime.timedelta(days=1)
        ini = fim - datetime.timedelta(days=dias - 1)
        d = pend.dashboard(ini, fim, list(Turno.objects.filter(ativo=True)), formulario_id, hoje)
        paginas = [(l, b["titulo"]) for b in d["blocos"] for g in b["grupos"] for l in g["linhas"]
                   if l["pct"] is not None and l["devidos"] >= pend.MIN_PRAZOS_PAGINA]
        paginas.sort(key=lambda t: t[0]["pct"])
        dados = {
            "ini": ini, "fim": fim, "pct": d["pct"], "devidos": d["devidos"], "feitos": d["feitos"], "atrasados": d["atrasados"],
            "evolucao": [{"rotulo": e["rotulo"], "pct": e["pct"]} for e in d["evolucao"] if e["pct"] is not None],
            "frequencias": [{"nome": f["nome"], "pct": f["pct"]} for f in d["por_frequencia"] if f["pct"] is not None],
            "piores": [{"nome": f"{t} · {l['nome']}", "pct": l["pct"]} for l, t in paginas[:30]],
        }
        cache.set(chave, dados, CACHE_SEGUNDOS)
    return dados


@_com_ocorrencias("pcp", "PCP")
def slides_pcp(user, resumo=False, filtros=None):
    from shared.permissions import has_view_access

    if not has_view_access(user, "pcp:dashboard"):
        return []
    f = filtros or {}
    fid = f.get("formulario")
    dias = int(f["dias"]) if str(f.get("dias") or "").isdigit() else 30
    fid = int(fid) if str(fid or "").isdigit() else None
    d = _dados_pcp(fid, dias)
    so_form = f.get("_so_formulario")
    slides = _slides_pcp_dados(d, dias, f, "") if (d["devidos"] or f.get("_por_formulario")) and not so_form else []  # cards à mão: sem dado aparece como 0%
    if f.get("_por_formulario") and fid is None:  # cards montados à mão: cada formulário (setor) também pode ser escolhido à parte
        from pcp.models import Formulario

        forms = Formulario.objects.filter(ativo=True).order_by("codigo")
        for form in (forms.filter(codigo=so_form) if so_form else forms[:30]):
            slides += _slides_pcp_dados(_dados_pcp(form.pk, dias), dias, f, f" · {form.codigo}")
    return slides


def _slides_pcp_dados(d, dias, f, sufixo):
    sub = f"{d['ini']:%d/%m} a {d['fim']:%d/%m} (últimos {dias} dias)"
    slides = [_slide("pcp", "tiles", f"PCP — cumprimento das verificações{sufixo}", sub, "bi-gear-wide-connected", itens=[
        {"rotulo": "Cumprimento", "valor": f"{_fmt_num(d['pct'] or 0, 1)}%", "tom": _tom_pct(d["pct"] or 0)},
        {"rotulo": "Devidas", "valor": d["devidos"], "tom": "neutro"},
        {"rotulo": "Feitas", "valor": d["feitos"], "tom": "ok"},
        {"rotulo": "Em atraso", "valor": d["atrasados"], "tom": "critico" if d["atrasados"] else "ok"},
    ])]
    evolucao = d["evolucao"]
    if len(evolucao) < 2:  # sem dado no período: o gráfico mostra 0% em cada dia (ou semana)
        import datetime

        passo = 7 if (d["fim"] - d["ini"]).days + 1 > 31 else 1
        dia = d["ini"] - datetime.timedelta(days=d["ini"].weekday()) if passo == 7 else d["ini"]
        evolucao = []
        while dia <= d["fim"]:
            evolucao.append({"rotulo": f"sem. {dia:%d/%m}" if passo == 7 else f"{dia:%d/%m}", "pct": 0})
            dia += datetime.timedelta(days=passo)
    if str(f.get("ultimos") or "").isdigit() and int(f["ultimos"]) > 1:  # últimos N pontos (dias ou semanas) do gráfico
        evolucao = evolucao[-int(f["ultimos"]):]
    if len(evolucao) > 1:
        slides.append(_slide("pcp", "chart", f"PCP — evolução do cumprimento{sufixo}", sub, "bi-graph-up",
                             tipo="barras" if f.get("tipo_grafico") == "barras" else "linha",
                             labels=[e["rotulo"] for e in evolucao], valores=[e["pct"] for e in evolucao],
                             meta=100, unidade="%"))
    qtd = int(f["barras_qtd"]) if str(f.get("barras_qtd") or "").isdigit() and 1 <= int(f["barras_qtd"]) <= 40 else None
    colunas = _col_barras(f.get("barras_colunas"))
    for titulo, lista, icone, padrao in ((f"PCP — cumprimento por frequência{sufixo}", d["frequencias"], "bi-calendar-check", None),
                                         (f"PCP — páginas com menor cumprimento{sufixo}", d["piores"], "bi-flag", 6)):
        lista = lista[:qtd or padrao]
        if lista:
            slides.append(_slide("pcp", "bars", titulo, sub, icone, sem_barra=bool(f.get("barras_sem_barra")),
                                 texto_prioritario=bool(f.get("barras_texto")), colunas=colunas, itens=[
                {"rotulo": x["nome"], "pct": x["pct"], "tom": _tom_pct(x["pct"]), "txt": f"{_fmt_num(x['pct'], 1)}%"} for x in lista]))
    return slides


# ---------------------------------------------------------------------------
# Laboratório (rendimento HC, mês do último lançamento)
# ---------------------------------------------------------------------------
def _periodo_lab(ultimo, periodo):
    import calendar
    from datetime import timedelta

    if periodo == "30d":
        return ultimo - timedelta(days=29), ultimo, "Últimos 30 dias"
    if periodo == "90d":
        return ultimo - timedelta(days=89), ultimo, "Últimos 90 dias"
    if periodo == "ano":
        return ultimo.replace(month=1, day=1), ultimo.replace(month=12, day=31), f"Ano {ultimo.year}"
    ini = ultimo.replace(day=1)
    return ini, ini.replace(day=calendar.monthrange(ini.year, ini.month)[1]), f"Mês {ini:%m/%Y}"


def _dados_lab(f):
    import hashlib
    import json
    from collections import defaultdict

    from django.db.models import Sum

    from laboratorio import hc_rendimento as hc
    from laboratorio.models import HCCadastro, RendimentoHCItem, RendimentoHCRegistro

    turnos = [t for t in (f.get("turnos") or []) if str(t).strip()]
    periodo = f.get("periodo") if f.get("periodo") in ("mes", "30d", "90d", "ano") else "mes"
    chave = "telao:lab:v2:" + hashlib.md5(json.dumps([periodo, sorted(turnos)]).encode()).hexdigest()
    dados = _cache_get(chave)
    if dados is not None:
        return dados
    ultimo = RendimentoHCRegistro.objects.order_by("-data").values_list("data", flat=True).first()
    if ultimo is None:
        dados = {"vazio": True}
    else:
        ini, fim, rotulo = _periodo_lab(ultimo, periodo)
        qs = hc._base(ini, fim)
        if turnos:
            qs = qs.filter(turno_nome__in=turnos)
        meta = hc.meta()
        total = hc._linha_passos(qs.aggregate(**hc._agg_passos()))
        prod = total["produzidas"]
        dias = [{"rotulo": f"{r['data']:%d/%m}", "rend": hc.rend(hc._n(r["prod"]), hc._n(r["ret"]))}
                for r in qs.values("data").annotate(prod=Sum("qtd_lentes"), ret=Sum("qtd_retrabalho")).order_by("data")]
        dias = [d for d in dias if d["rend"] is not None]
        meses = []
        if periodo == "ano":
            nomes = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]
            por_mes = {r["data__month"]: r for r in qs.values("data__month").annotate(prod=Sum("qtd_lentes"), ret=Sum("qtd_retrabalho"))}
            meses = [{"rotulo": nomes[m - 1], "rend": hc.rend(hc._n(por_mes[m]["prod"]), hc._n(por_mes[m]["ret"]))}
                     for m in range(1, 13) if m in por_mes and hc.rend(hc._n(por_mes[m]["prod"]), hc._n(por_mes[m]["ret"])) is not None]
        por_turno = [g for g in hc._por_grupo(qs, "turno_nome", "Sem turno", prod) if g["rend"] is not None]
        itens = RendimentoHCItem.objects.filter(registro__in=qs)
        motivos = sorted(({"nome": c.nome, "qtd": q, "pct": hc.pct(q, prod)} for c, q in
                          hc._soma_por_cadastro(itens, RendimentoHCItem.RET_MOTIVO, HCCadastro.TIPO_MOTIVO) if q),
                         key=lambda x: -x["qtd"])[:8]
        prod_mat = {c.pk: q for c, q in hc._soma_por_cadastro(itens, RendimentoHCItem.PROD_MATERIAL, HCCadastro.TIPO_MATERIAL)}
        materiais = []
        for c, ret in hc._soma_por_cadastro(itens, RendimentoHCItem.RET_MATERIAL, HCCadastro.TIPO_MATERIAL):
            p = hc._n(prod_mat.get(c.pk))
            if p:
                materiais.append({"nome": c.nome, "prod": p, "rend": hc.rend(p, ret)})
        materiais.sort(key=lambda x: -x["prod"])
        colabs = [c for c in hc._por_colaborador(qs, prod) if c["rend"] is not None][:10]
        dados = {"vazio": False, "rotulo": rotulo, "meta": meta, "total": total, "dias": dias, "meses": meses,
                 "turnos": por_turno, "motivos": motivos, "materiais": materiais[:8], "colabs": colabs}
    cache.set(chave, dados, CACHE_SEGUNDOS)
    return dados


def _tom_rend(v, meta):
    return "neutro" if v is None else "ok" if v >= meta else "critico"


@_com_ocorrencias("laboratorio", "Laboratório")
def slides_laboratorio(user, resumo=False, filtros=None):
    from shared.permissions import has_view_access

    if not has_view_access(user, "laboratorio:hc_dashboard"):
        return []
    f = filtros or {}
    d = _dados_lab(f)
    if d["vazio"]:
        return []
    t, meta, sub = d["total"], d["meta"], d["rotulo"]
    if not t["produzidas"]:
        return []
    ic = "bi-droplet-half"
    slides = [_slide("laboratorio", "tiles", "Laboratório — rendimento HC", f"{sub} · meta {_fmt_num(meta, 1)}%", ic, itens=[
        {"rotulo": "Rendimento", "valor": f"{_fmt_num(t['rendimento'], 1)}%", "tom": _tom_rend(t["rendimento"], meta), "nota": f"meta {_fmt_num(meta, 1)}%"},
        {"rotulo": "Retrabalho", "valor": f"{_fmt_num(t['pct_retrabalho'], 1)}%", "tom": "neutro"},
        {"rotulo": "Lentes produzidas", "valor": _fmt_num(t["produzidas"], 0), "tom": "neutro"},
        {"rotulo": "Lentes em retrabalho", "valor": _fmt_num(t["retrabalho"], 0), "tom": "alerta" if t["retrabalho"] else "ok"},
    ])]
    if len(d["dias"]) > 1:
        slides.append(_slide("laboratorio", "chart", "Laboratório — rendimento HC por dia", sub, "bi-graph-up",
                             labels=[x["rotulo"] for x in d["dias"]], valores=[x["rend"] for x in d["dias"]], meta=meta, unidade="%",
                             atingiu=[x["rend"] >= meta for x in d["dias"]]))
    if len(d["meses"]) > 1:
        slides.append(_slide("laboratorio", "chart", "Laboratório — rendimento HC por mês", sub, "bi-bar-chart",
                             labels=[x["rotulo"] for x in d["meses"]], valores=[x["rend"] for x in d["meses"]], meta=meta, unidade="%",
                             atingiu=[x["rend"] >= meta for x in d["meses"]]))

    def _bars(lista, nome="nome"):
        return [{"rotulo": x[nome], "pct": x["rend"], "tom": _tom_rend(x["rend"], meta), "txt": f"{_fmt_num(x['rend'], 1)}%"} for x in lista]
    if d["turnos"]:
        slides.append(_slide("laboratorio", "bars", "Laboratório — rendimento por turno", sub, "bi-clock", itens=_bars(d["turnos"])))
    if d["motivos"]:
        slides.append(_slide("laboratorio", "bars", "Laboratório — retrabalho por motivo", f"{sub} · % sobre lentes produzidas",
                             "bi-exclamation-triangle", itens=[
            {"rotulo": m["nome"], "pct": min(m["pct"] or 0, 100), "tom": "alerta", "txt": f"{_fmt_num(m['qtd'], 0)} ({_fmt_num(m['pct'], 1)}%)"}
            for m in d["motivos"]]))
    if d["materiais"]:
        slides.append(_slide("laboratorio", "bars", "Laboratório — rendimento por material", sub, "bi-layers", itens=_bars(d["materiais"])))
    if d["colabs"] and not resumo:
        slides.append(_slide("laboratorio", "bars", "Laboratório — rendimento por colaborador", sub, "bi-people", itens=_bars(d["colabs"])))
    return slides


def _opts_lab_turnos(user):
    from laboratorio.models import RendimentoHCRegistro

    return [(t, t) for t in sorted(set(RendimentoHCRegistro.objects.exclude(turno_nome="").values_list("turno_nome", flat=True).distinct()))]


# ---------------------------------------------------------------------------
# Treinamentos (planejamento)
# ---------------------------------------------------------------------------
def _filtros_pessoas(f):
    """Filtros do dashboard de treinamentos que recortam por colaborador / procedimento (iguais aos da tela)."""
    return {k: [x for x in (f.get(k) or []) if str(x).strip()] for k in
            ("setores", "turnos", "lideres", "supervisores", "gerentes", "criticidade", "matrizes", "sub_areas")}


def _dados_treinamentos(f):
    import hashlib
    import json
    from datetime import date, timedelta

    from django.db.models import Case, Count, Exists, F, IntegerField, OuterRef, Q, Subquery, Value, When
    from django.db.models.functions import TruncMonth

    from core.models import TURNOS_CHOICES
    from procedures.models import ColaboradorPerfil, RegistroTreinamento
    from rh.models import Colaborador

    flt = _filtros_pessoas(f)
    chave = "telao:trein:v2:" + hashlib.md5(json.dumps(flt, sort_keys=True).encode()).hexdigest()
    dados = _cache_get(chave)
    if dados is not None:
        return dados

    base = RegistroTreinamento.objects.filter(
        colaborador__isnull=False, colaborador__is_active=True, colaborador__afastado=False,
        colaborador__em_ferias=False, procedimento__isnull=False, ativo=True)
    if flt["setores"]:
        base = base.filter(colaborador__setor_id__in=flt["setores"])
    if flt["turnos"]:
        base = base.filter(colaborador__turno__in=flt["turnos"])
    if flt["lideres"]:
        base = base.filter(Q(colaborador__lider_id__in=flt["lideres"]) | Q(colaborador__vice_lider_id__in=flt["lideres"]))
    if flt["supervisores"]:
        base = base.filter(colaborador__supervisor_id__in=flt["supervisores"])
    if flt["gerentes"]:
        base = base.filter(colaborador__gerente_id__in=flt["gerentes"])
    if flt["criticidade"]:
        base = base.filter(procedimento__criticidade__in=flt["criticidade"])
    if flt["matrizes"]:
        base = base.filter(procedimento__matriz__in=flt["matrizes"])
    if flt["sub_areas"]:
        base = base.filter(procedimento__sub_area__in=flt["sub_areas"])
    # só procedimentos que fazem parte de algum perfil ativo do colaborador (como no dashboard)
    base = base.annotate(_perfil=Exists(ColaboradorPerfil.objects.filter(
        colaborador_id=OuterRef("colaborador_id"), ativo=True,
        perfil__grupos__subgrupos__procedimentos=OuterRef("procedimento_id")))).filter(_perfil=True)

    ultimo = RegistroTreinamento.objects.filter(
        colaborador_id=OuterRef("colaborador_id"), procedimento_id=OuterRef("procedimento_id")).annotate(
        valida=Case(When(data_treinamento__isnull=False, data_treinamento__gt=date(1970, 1, 1), then=Value(1)),
                    default=Value(0), output_field=IntegerField())).order_by("-valida", "-data_treinamento", "-id").values("id")[:1]
    vig_q = Q(data_treinamento__isnull=False) & (Q(procedimento__data_aprovacao__isnull=True)
                                                 | Q(data_treinamento__gte=F("procedimento__data_aprovacao")))
    pen_q = Q(data_treinamento__isnull=True) | (Q(procedimento__data_aprovacao__isnull=False)
                                                 & Q(data_treinamento__lt=F("procedimento__data_aprovacao")))
    unicos = base.filter(id=Subquery(ultimo))
    total = unicos.count()
    vig = unicos.filter(vig_q).count()
    pend = unicos.filter(pen_q).count()

    def _por(campos, nomear, limite=10):
        linhas = []
        for r in unicos.values(*campos).annotate(v=Count("id", filter=vig_q), p=Count("id", filter=pen_q)):
            if r["v"] + r["p"] > 0:
                linhas.append({"nome": nomear(r), "vig": r["v"], "pend": r["p"]})
        linhas.sort(key=lambda x: -(x["vig"] + x["p"] if False else x["vig"] + x["pend"]))
        return linhas[:limite]

    turnos = dict(TURNOS_CHOICES)
    setor_turno = _por(("colaborador__setor__nome", "colaborador__turno"),
                       lambda r: f"{(r['colaborador__setor__nome'] or 'Sem setor')[:22]} - {turnos.get(r['colaborador__turno'], r['colaborador__turno'] or 'N/A')}")
    lideres = _por(("colaborador__lider__nome_completo",),
                   lambda r: " ".join(filter(None, [(r["colaborador__lider__nome_completo"] or "Sem líder").split()[0],
                                                     (r["colaborador__lider__nome_completo"] or "").split()[-1] if len((r["colaborador__lider__nome_completo"] or "").split()) > 1 else ""])))

    mes_ini = (date.today().replace(day=1) - timedelta(days=330)).replace(day=1)
    por_mes = {(r["mes"].date() if hasattr(r["mes"], "date") else r["mes"]): r["n"] for r in base.filter(
        data_treinamento__isnull=False, data_treinamento__gte=mes_ini).annotate(mes=TruncMonth("data_treinamento"))
        .values("mes").annotate(n=Count("id"))}
    meses, cur = [], mes_ini
    for _ in range(12):
        meses.append({"rotulo": cur.strftime("%m/%Y"), "n": por_mes.get(cur, 0)})
        cur = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)

    dados = {
        "total": total, "vig": vig, "pend": pend, "taxa": round(vig * 100 / total, 1) if total else None,
        "colab": unicos.filter(vig_q).values("colaborador_id").distinct().count(),
        "procs": unicos.filter(vig_q).values("procedimento_id").distinct().count(),
        "ult30": base.filter(data_treinamento__gte=date.today() - timedelta(days=30)).count(),
        "setor_turno": setor_turno, "lideres": lideres, "meses": meses,
    }
    cache.set(chave, dados, CACHE_SEGUNDOS)
    return dados


def _bars_vigencia(linhas):
    return [{"rotulo": x["nome"], "pct": (x["vig"] * 100 / (x["vig"] + x["pend"])), "tom": _tom_pct(x["vig"] * 100 / (x["vig"] + x["pend"])),
             "txt": f"{_fmt_num(x['vig'] * 100 / (x['vig'] + x['pend']), 0)}%  ({x['vig']}/{x['vig'] + x['pend']})"} for x in linhas]


def slides_treinamentos(user, resumo=False, filtros=None):
    import datetime

    from procedures.models import PlanejamentoTreinamento as P
    from shared.permissions import has_view_access

    if not has_view_access(user, "procedures:dashboard_treinamentos"):
        return []
    f = filtros or {}
    flt = _filtros_pessoas(f)
    escopo = "Recorte aplicado" if any(flt.values()) else "Todos os colaboradores ativos"
    d = _dados_treinamentos(f)
    slides = []
    if d["total"]:
        slides.append(_slide("treinamentos", "tiles", "Treinamentos — vigência", escopo, "bi-mortarboard", itens=[
            {"rotulo": "Conformidade", "valor": f"{_fmt_num(d['taxa'], 1)}%", "tom": _tom_pct(d["taxa"]), "nota": "treinamentos vigentes / total"},
            {"rotulo": "Vigentes", "valor": d["vig"], "tom": "ok"},
            {"rotulo": "Pendentes", "valor": d["pend"], "tom": "critico" if d["pend"] else "ok"},
            {"rotulo": "Colaboradores treinados", "valor": d["colab"], "tom": "neutro"},
            {"rotulo": "Procedimentos treinados", "valor": d["procs"], "tom": "neutro"},
            {"rotulo": "Treinamentos nos últimos 30 dias", "valor": d["ult30"], "tom": "neutro"},
        ]))
        qtd = int(f["barras_qtd"]) if str(f.get("barras_qtd") or "").isdigit() and 1 <= int(f["barras_qtd"]) <= 40 else None
        est_barras = dict(sem_barra=bool(f.get("barras_sem_barra")), texto_prioritario=bool(f.get("barras_texto")),
                          colunas=_col_barras(f.get("barras_colunas")))
        if d["setor_turno"]:
            slides.append(_slide("treinamentos", "bars", "Treinamentos — vigência por setor e turno", escopo,
                                 "bi-building", itens=_bars_vigencia(d["setor_turno"][:qtd]), **est_barras))
        if d["lideres"] and not resumo:
            slides.append(_slide("treinamentos", "bars", "Treinamentos — vigência por líder", escopo,
                                 "bi-person-badge", itens=_bars_vigencia(d["lideres"][:qtd]), **est_barras))
        meses = d["meses"]
        if str(f.get("ultimos") or "").isdigit() and int(f["ultimos"]) > 1:
            meses = meses[-int(f["ultimos"]):]
        if any(m["n"] for m in meses):
            slides.append(_slide("treinamentos", "chart", "Treinamentos realizados por mês", f"Últimos {len(meses)} meses",
                                 "bi-calendar3", tipo="barras" if f.get("tipo_grafico") == "barras" else "linha",
                                 labels=[m["rotulo"] for m in meses], valores=[m["n"] for m in meses],
                                 meta=None, unidade=""))

    # Planejamento (mesmos recortes do dashboard, aplicados aos colaboradores do treinamento)
    janela = int(f["janela"]) if str(f.get("janela") or "").isdigit() else 30
    hoje = timezone.localdate()
    pq = P.objects.all()
    for campo, vals in (("colaboradores__setor_id__in", flt["setores"]), ("colaboradores__turno__in", flt["turnos"]),
                        ("colaboradores__supervisor_id__in", flt["supervisores"]), ("colaboradores__gerente_id__in", flt["gerentes"]),
                        ("procedimentos__criticidade__in", flt["criticidade"]), ("procedimentos__matriz__in", flt["matrizes"]),
                        ("procedimentos__sub_area__in", flt["sub_areas"])):
        if vals:
            pq = pq.filter(**{campo: vals})
    if flt["lideres"]:
        from django.db.models import Q
        pq = pq.filter(Q(colaboradores__lider_id__in=flt["lideres"]) | Q(colaboradores__vice_lider_id__in=flt["lideres"]))
    pq = pq.distinct()
    abertos = pq.filter(status__in=("PLANEJADO", "CONFIRMADO", "ATRASADO"))
    atrasados = abertos.filter(data_prevista__lt=hoje).count()
    proximos_qs = abertos.filter(data_prevista__gte=hoje, data_prevista__lte=hoje + datetime.timedelta(days=janela)).order_by("data_prevista")
    n_prox = int(f["proximos_qtd"]) if str(f.get("proximos_qtd") or "").isdigit() and 1 <= int(f["proximos_qtd"]) <= 40 else 8
    proximos = [] if f.get("apenas_atrasados") else list(proximos_qs[:n_prox])
    realizados_mes = pq.filter(status="REALIZADO", data_realizada__year=hoje.year, data_realizada__month=hoje.month).count()
    if atrasados or proximos or realizados_mes:
        tiles = [{"rotulo": "Atrasados", "valor": atrasados, "tom": "critico" if atrasados else "ok"}]
        if not f.get("apenas_atrasados"):
            tiles += [{"rotulo": f"Próximos {janela} dias", "valor": proximos_qs.count(), "tom": "neutro"},
                      {"rotulo": "Realizados no mês", "valor": realizados_mes, "tom": "ok"}]
        slides.append(_slide("treinamentos", "tiles", "Treinamentos — planejamento", f"Posição em {hoje:%d/%m/%Y}",
                             "bi-calendar-check", itens=tiles))
    cards = [{"titulo": _corta(p.titulo, 100), "texto": "", "tom": "neutro",
              "tags": [f"{p.data_prevista:%d/%m/%Y}", f"em {(p.data_prevista - hoje).days} d", p.get_status_display()]
                      + ([p.local] if p.local and not resumo else [])} for p in proximos]
    col_prox = _col_barras(f.get("proximos_colunas"))
    por_slide = CARDS_POR_SLIDE * (3 if col_prox == "auto" else col_prox)
    for n, lote in enumerate(_lotes(cards, por_slide), start=1):
        slides.append(_slide("treinamentos", "cards", "Próximos treinamentos", f"parte {n}" if len(cards) > por_slide else "",
                             "bi-calendar-event", colunas=col_prox, itens=lote))
    return slides


def _opts_trein_setores(user):
    from organization.models import Setor

    return [(str(s.pk), s.nome) for s in Setor.objects.order_by("nome")]


def _opts_trein_turnos(user):
    from core.models import TURNOS_CHOICES

    return list(TURNOS_CHOICES)


def _opts_trein_pessoas(papel):
    def _f(user):
        from rh.models import Colaborador

        ids = set(Colaborador.objects.filter(is_active=True).exclude(**{f"{papel}__isnull": True}).values_list(f"{papel}_id", flat=True))
        return [(str(c.pk), c.nome_completo) for c in Colaborador.objects.filter(pk__in=ids, is_active=True).order_by("nome_completo")]
    return _f


def _opts_trein_proc(campo):
    def _f(user):
        from procedures.models import Procedimento

        vals = Procedimento.objects.exclude(**{f"{campo}__isnull": True}).exclude(**{campo: ""}).values_list(campo, flat=True).distinct()
        return [(v, v) for v in sorted(set(vals))]
    return _f


PROVEDORES: dict[str, Callable] = {
    "ocorrencias": slides_ocorrencias,
    "kpi": slides_kpi,
    "auditoria": slides_auditoria,
    "metrologia": slides_metrologia,
    "pcp": slides_pcp,
    "laboratorio": slides_laboratorio,
    "treinamentos": slides_treinamentos,
}

# Única playlist fixa no código (disponível para todos); as demais são modelos criados pelos usuários.
PLAYLISTS = {
    "geral": ("Apresentação Geral", "bi-grid-1x2",
              ("ocorrencias", "kpi", "auditoria", "metrologia", "pcp", "laboratorio", "treinamentos")),
}
PLAYLIST_PADRAO = "geral"

# Rótulos dos provedores (usados no editor de modelos).
ROTULOS_PROVEDORES = {
    "ocorrencias": ("Ocorrências", "bi-exclamation-triangle"),
    "kpi": ("Indicadores (KPI)", "bi-speedometer2"),
    "auditoria": ("Auditorias", "bi-clipboard-check"),
    "metrologia": ("Metrologia", "bi-tools"),
    "pcp": ("PCP", "bi-gear-wide-connected"),
    "laboratorio": ("Laboratório", "bi-droplet-half"),
    "treinamentos": ("Treinamentos", "bi-mortarboard"),
}


# ---------------------------------------------------------------------------
# Cards selecionáveis de cada módulo: (id, rótulo, quais slides pertencem ao card)
# ---------------------------------------------------------------------------
PROVEDOR_CARDS = {
    "ocorrencias": [
        ("totais", "Totais de ocorrências em aberto", lambda s: s["kind"] == "tiles"),
        ("por_responsavel", "Gráfico de ocorrências em aberto por responsável", lambda s: s["kind"] == "bars" and "responsável" in s["titulo"]),
        ("por_modulo", "Gráfico de ocorrências em aberto por módulo", lambda s: s["kind"] == "bars" and "módulo" in s["titulo"]),
        ("lista", "Ocorrências por sessão (módulo / relatório de auditoria), com comentários", lambda s: bool(s.get("grupo"))),
    ],
    "kpi": [
        ("situacao", "Situação dos indicadores (na meta / fora)", lambda s: s["kind"] == "tiles"),
        ("graficos", "Gráficos de evolução com rótulos", lambda s: s["kind"] == "chart"),
        ("motivos", "Top principais motivos (por indicador)", lambda s: s["kind"] == "bars"),
    ],
    "auditoria": [
        ("conformidade", "Conformidade do último ciclo (barras)", lambda s: s["kind"] == "bars"),
        ("evolucao", "Evolução da conformidade por ciclo", lambda s: s["kind"] == "chart"),
        ("pontos", "Pontos de atenção (não conformidades)", lambda s: s["kind"] == "cards"),
    ],
    "metrologia": [
        ("totais", "Totais de calibrações (vencidos, a vencer, em dia)", lambda s: s["kind"] == "tiles"),
        ("criticos", "Instrumentos críticos", lambda s: s["kind"] == "cards"),
    ],
    "pcp": [
        ("resumo", "Cumprimento geral", lambda s: s["kind"] == "tiles"),
        ("evolucao", "Evolução do cumprimento", lambda s: s["kind"] == "chart"),
        ("frequencias", "Cumprimento por frequência", lambda s: s["kind"] == "bars" and "frequência" in s["titulo"]),
        ("paginas", "Páginas com menor cumprimento", lambda s: s["kind"] == "bars" and "páginas" in s["titulo"]),
    ],
    "laboratorio": [
        ("resumo", "Rendimento HC (rendimento, retrabalho, lentes)", lambda s: s["kind"] == "tiles"),
        ("dia", "Rendimento por dia", lambda s: s["kind"] == "chart" and "por dia" in s["titulo"]),
        ("mes", "Rendimento por mês (período Ano)", lambda s: s["kind"] == "chart" and "por mês" in s["titulo"]),
        ("turno", "Rendimento por turno", lambda s: s["kind"] == "bars" and "turno" in s["titulo"]),
        ("motivo", "Retrabalho por motivo", lambda s: s["kind"] == "bars" and "motivo" in s["titulo"]),
        ("material", "Rendimento por material", lambda s: s["kind"] == "bars" and "material" in s["titulo"]),
        ("colaborador", "Rendimento por colaborador", lambda s: s["kind"] == "bars" and "colaborador" in s["titulo"]),
    ],
    "treinamentos": [
        ("resumo", "Vigência dos treinamentos (conformidade, vigentes, pendentes)", lambda s: s["kind"] == "tiles" and "vigência" in s["titulo"]),
        ("setor_turno", "Vigência por setor e turno", lambda s: s["kind"] == "bars" and "setor" in s["titulo"]),
        ("lider", "Vigência por líder", lambda s: s["kind"] == "bars" and "líder" in s["titulo"]),
        ("mensal", "Treinamentos realizados por mês", lambda s: s["kind"] == "chart"),
        ("planejamento", "Planejamento (atrasados, próximos, realizados)", lambda s: s["kind"] == "tiles" and "planejamento" in s["titulo"]),
        ("proximos", "Lista dos próximos treinamentos", lambda s: s["kind"] == "cards"),
    ],
}


def _opts_kpi_indicadores(user):
    from kpi.models import Indicador

    return [(str(i.pk), i.nome) for i in Indicador.objects.filter(ativo=True).order_by("ordem", "nome")]


def _opts_kpi_setores(user):
    from kpi.models import SetorIndicador

    return [(n, n) for n in SetorIndicador.objects.order_by("nome").values_list("nome", flat=True).distinct()]


def _opts_auditoria_modelos(user):
    from auditoria.models import ModeloAuditoria
    from auditoria.views import _filter_modelos_para_usuario

    qs = _filter_modelos_para_usuario(user, ModeloAuditoria.objects.filter(ativo=True, arquivado=False))
    return [(str(m.pk), m.nome) for m in qs.order_by("nome")]


def _opts_metrologia_setores(user):
    from organization.models import Setor

    return [(n, n) for n in Setor.objects.order_by("nome").values_list("nome", flat=True)]


def _opts_pcp_formularios(user):
    from pcp.models import Formulario

    return [("", "Todos os formulários")] + [(str(f.pk), f"{f.codigo} — {f.titulo} ({f.setor.nome})")
                                              for f in Formulario.objects.filter(ativo=True).select_related("setor")]


def _opts_origens(user):
    from shared import ocorrencias as central

    return [(k, o.nome) for k, o in central.ORIGENS.items()]


# Filtros de cada módulo, espelhando os dos dashboards. tipo: multi | select | bool.
# Multi vazio = todos; select sem valor = padrão do módulo.
# Campos que configuram COMO o card é mostrado (período, tipo de gráfico...), e não QUAIS dados entram.
# módulo -> campo -> cards a que se aplicam (no editor, o resto aparece só em "Filtros").
CAMPOS_CONFIG = {
    "kpi": {
        "serie": ["kpi.graficos", "kpi.motivos"], "tipo_grafico": ["kpi.graficos"], "janela": ["kpi.graficos", "kpi.motivos"],
        "ultimos": ["kpi.graficos", "kpi.motivos"],
        "dias": ["kpi.graficos", "kpi.situacao"], "meses": ["kpi.graficos"], "graficos": ["kpi.graficos"],
        "ocultar_na_meta": ["kpi.situacao"], "ocultar_fora": ["kpi.situacao"], "ocultar_sem_dado": ["kpi.situacao"],
        "motivos_exibir": ["kpi.motivos"], "motivos_sem_barra": ["kpi.motivos"], "motivos_texto": ["kpi.motivos"],
        "motivos_qtd": ["kpi.motivos"], "motivos_colunas": ["kpi.motivos"],
    },
    "pcp": {
        "dias": ["pcp.resumo", "pcp.evolucao", "pcp.frequencias", "pcp.paginas"],
        "tipo_grafico": ["pcp.evolucao"], "ultimos": ["pcp.evolucao"],
        "barras_qtd": ["pcp.frequencias", "pcp.paginas"], "barras_colunas": ["pcp.frequencias", "pcp.paginas"],
        "barras_sem_barra": ["pcp.frequencias", "pcp.paginas"], "barras_texto": ["pcp.frequencias", "pcp.paginas"],
    },
    "treinamentos": {
        "tipo_grafico": ["treinamentos.mensal"], "ultimos": ["treinamentos.mensal"],
        "barras_qtd": ["treinamentos.setor_turno", "treinamentos.lider"], "barras_colunas": ["treinamentos.setor_turno", "treinamentos.lider"],
        "barras_sem_barra": ["treinamentos.setor_turno", "treinamentos.lider"], "barras_texto": ["treinamentos.setor_turno", "treinamentos.lider"],
        "proximos_qtd": ["treinamentos.proximos"], "proximos_colunas": ["treinamentos.proximos"],
    },
    "ocorrencias": {"comentarios": ["ocorrencias.lista"], "oc_colunas": ["ocorrencias.lista"]},
    "auditoria": {
        "tipo_grafico": ["auditoria.evolucao"], "ultimos": ["auditoria.evolucao"],
        "conf_exibir": ["auditoria.conformidade"], "conf_qtd": ["auditoria.conformidade"], "conf_colunas": ["auditoria.conformidade"],
        "conf_sem_barra": ["auditoria.conformidade"], "conf_texto": ["auditoria.conformidade"],
    },
}

FILTROS = {
    "ocorrencias": [
        dict(nome="abordagem", rotulo="Abordagem", tipo="select",
             opcoes=lambda u: [("global", "Global — panorama de todos, sem destacar o usuário logado (recomendado para TV)"),
                               ("pessoal", "Pessoal — destaca o que envolve quem está logado")]),
        dict(nome="origens", rotulo="Módulos de origem", tipo="multi", opcoes=_opts_origens,
             ajuda="Vazio = todos os módulos."),
        dict(nome="apenas_vencidas", rotulo="Somente ocorrências vencidas", tipo="bool"),
        dict(nome="comentarios", rotulo="Comentários do plano de ação", tipo="select",
             opcoes=lambda u: [("sim", "Mostrar sob cada ocorrência"), ("nao", "Não mostrar")]),
        dict(nome="oc_colunas", rotulo="Ocorrências — dividir em colunas", tipo="select",
             opcoes=lambda u: [("auto", "Automático (ajusta ao tamanho)"), ("1", "1 coluna"), ("2", "2 colunas"), ("3", "3 colunas"), ("4", "4 colunas")]),
    ],
    "kpi": [
        dict(nome="indicadores", rotulo="Indicadores", tipo="multi", opcoes=_opts_kpi_indicadores, ajuda="Vazio = todos."),
        dict(nome="setores", rotulo="Setores (indicador de quebra)", tipo="multi", opcoes=_opts_kpi_setores,
             ajuda="Mostra a meta e as medições do setor, em vez do geral. Ex.: Montagem, Surfaçagem, HMC."),
        dict(nome="ocultar_na_meta", rotulo="Ocultar “Na meta” na situação geral", tipo="bool"),
        dict(nome="ocultar_fora", rotulo="Ocultar “Fora da meta” na situação geral", tipo="bool"),
        dict(nome="ocultar_sem_dado", rotulo="Ocultar “Sem dado” na situação geral", tipo="bool"),
        dict(nome="apenas_fora", rotulo="Somente indicadores fora da meta", tipo="bool"),
        dict(nome="motivos_exibir", rotulo="Motivos — informação exibida", tipo="select",
             opcoes=lambda u: [("ambos", "Quantidade e percentual"), ("quantidade", "Somente a quantidade"), ("percentual", "Somente o percentual")]),
        dict(nome="motivos_qtd", rotulo="Motivos — quantos mostrar (padrão 10)", tipo="select",
             opcoes=lambda u: [(str(n), str(n)) for n in (3, 4, 5, 6, 8, 10, 12, 15, 20, 30)]),
        dict(nome="motivos_colunas", rotulo="Motivos — dividir em colunas", tipo="select",
             opcoes=lambda u: [("auto", "Automático (ajusta ao tamanho)"), ("1", "1 coluna"), ("2", "2 colunas"), ("3", "3 colunas"), ("4", "4 colunas")]),
        dict(nome="motivos_sem_barra", rotulo="Motivos — ocultar a barra de preenchimento", tipo="bool"),
        dict(nome="motivos_texto", rotulo="Motivos — priorizar o texto (mais largura, sem cortar)", tipo="bool"),
        dict(nome="serie", rotulo="Período (diário, semanal ou mensal)", tipo="select",
             opcoes=lambda u: [("diaria", "Diário"), ("semanal", "Semanal"), ("mensal", "Mensal")],
             ajuda="Gráficos: padrão mensal (ou o último lançado). Principais motivos: padrão o mais detalhado lançado."),
        dict(nome="tipo_grafico", rotulo="Gráfico — tipo", tipo="select",
             opcoes=lambda u: [("linha", "Linha pontilhada"), ("barras", "Barras"), ("empilhadas", "Barras empilhadas (por setor)")]),
        dict(nome="janela", rotulo="Janela de tempo", tipo="select",
             opcoes=lambda u: [("ultimos", "Últimos N períodos"), ("competencia", "Dentro da última competência (mês)")]),
        dict(nome="ultimos", rotulo="Quantos períodos (últimos N)", tipo="select",
             opcoes=lambda u: [(str(n), str(n)) for n in (1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 15, 20, 24, 26, 30, 45, 52, 60, 90)],
             ajuda="N dias, semanas ou meses, conforme o período escolhido. Ignorado na última competência."),
        dict(nome="graficos", rotulo="Gráficos de evolução", tipo="select",
             opcoes=lambda u: [("fora", "Só dos fora da meta"), ("todos", "De todos"), ("nenhum", "Nenhum")]),
        dict(nome="dias", rotulo="Últimos dias (medições diárias)", tipo="select",
             opcoes=lambda u: [(str(n), f"Últimos {n} dias") for n in (7, 15, 30, 45, 60, 90)],
             ajuda="Mostra as medições diárias dos últimos N dias nos gráficos e na situação; sem isso, valem os meses."),
        dict(nome="meses", rotulo="Meses nos gráficos", tipo="select",
             opcoes=lambda u: [("6", "6 meses"), ("12", "12 meses"), ("24", "24 meses")]),
    ],
    "auditoria": [
        dict(nome="modelos", rotulo="Relatórios (auditorias)", tipo="multi", opcoes=_opts_auditoria_modelos,
             ajuda="Sempre usa o último ciclo concluído de cada um. Vazio = todos os ativos."),
        dict(nome="tipo_grafico", rotulo="Gráfico — tipo", tipo="select",
             opcoes=lambda u: [("linha", "Linha pontilhada"), ("barras", "Barras")]),
        dict(nome="ultimos", rotulo="Gráfico — quantos ciclos (últimos N, padrão 8)", tipo="select",
             opcoes=lambda u: [(str(n), str(n)) for n in (2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24)]),
        dict(nome="conf_exibir", rotulo="Conformidade — informação exibida", tipo="select",
             opcoes=lambda u: [("ambos", "Percentual e variação"), ("percentual", "Somente o percentual")]),
        dict(nome="conf_qtd", rotulo="Conformidade — quantas auditorias mostrar", tipo="select",
             opcoes=lambda u: [(str(n), str(n)) for n in (3, 4, 5, 6, 8, 10)]),
        dict(nome="conf_colunas", rotulo="Conformidade — dividir em colunas", tipo="select",
             opcoes=lambda u: [("auto", "Automático (ajusta ao tamanho)"), ("1", "1 coluna"), ("2", "2 colunas"), ("3", "3 colunas"), ("4", "4 colunas")]),
        dict(nome="conf_sem_barra", rotulo="Conformidade — ocultar a barra de preenchimento", tipo="bool"),
        dict(nome="conf_texto", rotulo="Conformidade — priorizar o texto (mais largura, sem cortar)", tipo="bool"),
    ],
    "metrologia": [
        dict(nome="setores", rotulo="Setores", tipo="multi", opcoes=_opts_metrologia_setores, ajuda="Vazio = todos."),
        dict(nome="tratativa", rotulo="Tratativa da calibração", tipo="select",
             opcoes=lambda u: [("", "Interna e externa"), ("interna", "Somente interna"), ("externa", "Somente externa")]),
    ],
    "pcp": [
        dict(nome="formulario", rotulo="Formulário (setor)", tipo="select", opcoes=_opts_pcp_formularios),
        dict(nome="dias", rotulo="Período analisado", tipo="select",
             opcoes=lambda u: [("7", "7 dias"), ("14", "14 dias"), ("30", "30 dias"), ("60", "60 dias"), ("90", "90 dias")]),
        dict(nome="tipo_grafico", rotulo="Gráfico — tipo", tipo="select",
             opcoes=lambda u: [("linha", "Linha pontilhada"), ("barras", "Barras")]),
        dict(nome="ultimos", rotulo="Gráfico — quantos pontos (últimos N dias/semanas)", tipo="select",
             opcoes=lambda u: [(str(n), str(n)) for n in (3, 5, 7, 10, 14, 15, 20, 30)]),
        dict(nome="barras_qtd", rotulo="Barras — quantas linhas mostrar", tipo="select",
             opcoes=lambda u: [(str(n), str(n)) for n in (3, 4, 5, 6, 8, 10, 12, 15, 20, 30)]),
        dict(nome="barras_colunas", rotulo="Barras — dividir em colunas", tipo="select",
             opcoes=lambda u: [("auto", "Automático (ajusta ao tamanho)"), ("1", "1 coluna"), ("2", "2 colunas"), ("3", "3 colunas"), ("4", "4 colunas")]),
        dict(nome="barras_sem_barra", rotulo="Barras — ocultar a barra de preenchimento", tipo="bool"),
        dict(nome="barras_texto", rotulo="Barras — priorizar o texto (mais largura, sem cortar)", tipo="bool"),
    ],
    "laboratorio": [
        dict(nome="periodo", rotulo="Período (a partir do último lançamento)", tipo="select",
             opcoes=lambda u: [("mes", "Mês do último lançamento"), ("30d", "Últimos 30 dias"), ("90d", "Últimos 90 dias"), ("ano", "Ano do último lançamento")]),
        dict(nome="turnos", rotulo="Turnos", tipo="multi", opcoes=_opts_lab_turnos, ajuda="Vazio = todos."),
    ],
    "treinamentos": [
        dict(nome="setores", rotulo="Setores", tipo="multi", opcoes=_opts_trein_setores, ajuda="Vazio = todos."),
        dict(nome="turnos", rotulo="Turnos", tipo="multi", opcoes=_opts_trein_turnos),
        dict(nome="lideres", rotulo="Líderes", tipo="multi", opcoes=_opts_trein_pessoas("lider")),
        dict(nome="supervisores", rotulo="Supervisores", tipo="multi", opcoes=_opts_trein_pessoas("supervisor")),
        dict(nome="gerentes", rotulo="Gerentes", tipo="multi", opcoes=_opts_trein_pessoas("gerente")),
        dict(nome="criticidade", rotulo="Criticidade do procedimento", tipo="multi",
             opcoes=lambda u: [("CRITICO", "Crítico"), ("NAO_CRITICO", "Não crítico")]),
        dict(nome="matrizes", rotulo="Matrizes", tipo="multi", opcoes=_opts_trein_proc("matriz")),
        dict(nome="sub_areas", rotulo="Sub-áreas", tipo="multi", opcoes=_opts_trein_proc("sub_area")),
        dict(nome="janela", rotulo="Próximos treinamentos em até", tipo="select",
             opcoes=lambda u: [("15", "15 dias"), ("30", "30 dias"), ("60", "60 dias"), ("90", "90 dias")]),
        dict(nome="apenas_atrasados", rotulo="Planejamento: somente atrasados", tipo="bool"),
        dict(nome="tipo_grafico", rotulo="Gráfico — tipo", tipo="select",
             opcoes=lambda u: [("linha", "Linha pontilhada"), ("barras", "Barras")]),
        dict(nome="ultimos", rotulo="Gráfico — quantos meses (últimos N)", tipo="select",
             opcoes=lambda u: [(str(n), str(n)) for n in (3, 4, 6, 8, 10, 12)]),
        dict(nome="barras_qtd", rotulo="Barras — quantas linhas mostrar", tipo="select",
             opcoes=lambda u: [(str(n), str(n)) for n in (3, 4, 5, 6, 8, 10, 12, 15, 20, 30)]),
        dict(nome="barras_colunas", rotulo="Barras — dividir em colunas", tipo="select", opcoes=lambda u: [("auto", "Automático (ajusta ao tamanho)"), ("1", "1 coluna"), ("2", "2 colunas"), ("3", "3 colunas"), ("4", "4 colunas")]),
        dict(nome="barras_sem_barra", rotulo="Barras — ocultar a barra de preenchimento", tipo="bool"),
        dict(nome="barras_texto", rotulo="Barras — priorizar o texto (mais largura, sem cortar)", tipo="bool"),
        dict(nome="proximos_qtd", rotulo="Próximos — quantos mostrar (padrão 8)", tipo="select",
             opcoes=lambda u: [(str(n), str(n)) for n in (4, 6, 8, 12, 16, 20, 30)]),
        dict(nome="proximos_colunas", rotulo="Próximos — dividir em colunas", tipo="select", opcoes=lambda u: [("auto", "Automático (ajusta ao tamanho)"), ("1", "1 coluna"), ("2", "2 colunas"), ("3", "3 colunas"), ("4", "4 colunas")]),
    ],
}


_CAMPOS_OCORRENCIAS = [
    dict(nome="com_ocorrencias", rotulo="Ocorrências do módulo na sequência", tipo="select",
         opcoes=lambda u: [("sim", "Mostrar (e seus comentários)"), ("nao", "Não mostrar")]),
    dict(nome="comentarios", rotulo="Comentários do plano de ação", tipo="select",
         opcoes=lambda u: [("sim", "Mostrar sob cada ocorrência"), ("nao", "Não mostrar")]),
    dict(nome="oc_colunas", rotulo="Ocorrências — dividir em colunas", tipo="select",
         opcoes=lambda u: [("auto", "Automático (ajusta ao tamanho)"), ("1", "1 coluna"), ("2", "2 colunas"), ("3", "3 colunas"), ("4", "4 colunas")]),
]
for _k in ("kpi", "auditoria", "metrologia", "pcp", "laboratorio"):
    FILTROS[_k] = list(FILTROS.get(_k, [])) + _CAMPOS_OCORRENCIAS
    PROVEDOR_CARDS[_k] = [("ocorrencias", "Ocorrências do módulo e comentários (na sequência)", lambda s: bool(s.get("ocorr")))] + list(PROVEDOR_CARDS.get(_k, []))
    CAMPOS_CONFIG.setdefault(_k, {}).update({"com_ocorrencias": [f"{_k}.ocorrencias"], "comentarios": [f"{_k}.ocorrencias"],
                                         "oc_colunas": [f"{_k}.ocorrencias"] + (["auditoria.pontos"] if _k == "auditoria" else [])
                                         + (["metrologia.criticos"] if _k == "metrologia" else [])})


def campos_filtro(provedor: str, user) -> list[dict]:
    """Campos de filtro do provedor para o editor: primeiro a seleção de cards, depois os filtros do módulo."""
    from . import layout

    campos = [dict(nome="cards", rotulo="Cards que entram na apresentação", tipo="multi",
                   opcoes=lambda u, p=provedor: [(c[0], c[1]) for c in PROVEDOR_CARDS.get(p, [])], ajuda="Vazio = todos os cards."),
              dict(nome="layout", rotulo="Disposição dos cards nos slides", tipo="select", opcoes=lambda u: layout.OPCOES_LAYOUT)]
    campos += FILTROS.get(provedor, [])
    saida = []
    for c in campos:
        try:
            opcoes = c["opcoes"](user) if "opcoes" in c else []
        except Exception:
            logger.exception("Telão: opções de filtro %s.%s", provedor, c["nome"])
            opcoes = []
        saida.append({**c, "opcoes": opcoes})
    return saida


def limpar_filtros(provedor: str, get_lista, get_valor, user, prefixo: str = "") -> dict:
    """Lê os filtros enviados pelo formulário (`f_<provedor>_<campo>`, ou `<prefixo><campo>`), descartando o que não é opção válida."""
    filtros = {}
    for c in campos_filtro(provedor, user):
        chave = f"{prefixo}{c['nome']}" if prefixo else f"f_{provedor}_{c['nome']}"
        validos = {str(v) for v, _ in c["opcoes"]}
        if c["tipo"] == "multi":
            marcados = [v for v in get_lista(chave) if v in validos]
            if marcados:
                filtros[c["nome"]] = marcados
        elif c["tipo"] == "select":
            v = (get_valor(chave) or "").strip()
            if v and v in validos:
                filtros[c["nome"]] = v
        elif c["tipo"] == "bool" and get_valor(chave) == "on":
            filtros[c["nome"]] = True
    return filtros


def modelos_visiveis(user):
    """Modelos de apresentação personalizados que o usuário pode rodar."""
    from django.db.models import Q

    from shared.models import ModeloApresentacao

    if not getattr(user, "is_authenticated", False):
        return ModeloApresentacao.objects.none()
    qs = ModeloApresentacao.objects.filter(ativo=True)
    if user.is_staff or user.is_superuser:
        return qs
    return qs.filter(Q(compartilhada=True) | Q(criado_por=user))


def obter_playlist(user, chave: str) -> dict:
    """Resolve a chave ("geral", "kpi"... ou "m<id>") para a definição da playlist; chave inválida cai no padrão."""
    if chave and chave[0] == "m" and chave[1:].isdigit():
        m = modelos_visiveis(user).filter(pk=int(chave[1:])).first()
        if m is not None:
            itens = []
            if m.slides:  # modelo no formato de slides: tem precedência sobre a lista antiga de conteúdos
                itens = [(CHAVE_SLIDE, c.get("duracao"), c) for c in m.slides if isinstance(c, dict)]
            for i in ([] if m.slides else (m.itens or [])):
                if not isinstance(i, dict):
                    continue
                if i.get("tipo") == "assunto":  # página montada à mão, com itens de um ou mais módulos
                    itens.append((CHAVE_ASSUNTO, i.get("duracao"), {"titulo": i.get("titulo") or "Assunto", "icone": i.get("icone") or "",
                                                                   "blocos": [b for b in (i.get("blocos") or []) if isinstance(b, dict)]}))
                else:
                    itens.append((i.get("provedor"), i.get("duracao"), i.get("filtros") or {}))
            return {"chave": m.chave, "nome": m.nome, "icone": m.icone or "bi-display", "itens": itens,
                    "duracao": m.duracao_padrao or DURACAO_PADRAO, "resumo": m.resumo, "tema": m.tema}
    nome, icone, provedores = PLAYLISTS.get(chave, PLAYLISTS[PLAYLIST_PADRAO])
    chave = chave if chave in PLAYLISTS else PLAYLIST_PADRAO
    return {"chave": chave, "nome": nome, "icone": icone, "itens": [(p, None, {}) for p in provedores],
            "duracao": None, "resumo": False, "tema": "escuro"}


CHAVE_ASSUNTO = "@assunto"
CHAVE_SLIDE = "@slide"  # slide da configuração `ModeloApresentacao.slides` (automático ou manual; ver shared.telao.layout)
MAX_PAINEIS = 4
ORIGENS_EMBUTIDAS = ("kpi", "auditoria", "metrologia", "pcp", "laboratorio")


def _marcar_cards(provedor, slides):
    regras = PROVEDOR_CARDS.get(provedor, [])
    for s in slides:
        s["card"] = next((cid for cid, _r, pred in regras if pred(s)), "")
        s["card_id"] = f"{provedor}.{s['card']}" if s["card"] else ""  # id estável do catálogo (shared.telao.cards)


def montar_playlist(user, playlist: str, resumo: bool = False, fresco: bool = False) -> list[dict]:
    """Monta os slides a cada chamada: filtros e cards do modelo valem na hora, e os dados são os atuais
    (fresco=True ignora o cache dos cálculos pesados)."""
    token = _SEM_CACHE.set(bool(fresco))
    try:
        return _montar_playlist(user, playlist, resumo)
    finally:
        _SEM_CACHE.reset(token)


def _slides_provedor(user, chave, filtros, resumo, embutidas):
    if chave not in PROVEDORES:
        return []
    if chave == "ocorrencias" and embutidas:
        filtros = {**filtros, "_embutidas": embutidas}
    try:
        novos = PROVEDORES[chave](user, resumo=resumo, filtros=filtros)
    except Exception:  # um módulo com problema não derruba a rotação
        logger.exception("Telão: provedor %s falhou", chave)
        return []
    _marcar_cards(chave, novos)
    escolhidos = set(filtros.get("cards") or [])
    if escolhidos:
        novos = [s for s in novos if s["card"] in escolhidos]
    from . import layout

    if filtros.get("layout") in layout.LAYOUTS or filtros.get("layout") == layout.AUTO:  # vários cards por slide, na disposição escolhida
        novos = layout.compor(novos, chave, filtros["layout"])
    return novos


_LIMITE_PAINEL = {"cards": 3, "bars": 6, "tiles": 8}


def _slide_assunto(user, cfg, resumo, embutidas):
    """"One page report": uma página com os itens escolhidos (de um ou mais módulos), cada um num painel."""
    paineis = []
    for b in cfg.get("blocos") or []:
        for sl in _slides_provedor(user, b.get("provedor"), {k: v for k, v in (b.get("filtros") or {}).items() if k != "layout"},
                                   resumo, embutidas):
            lim = _LIMITE_PAINEL.get(sl["kind"])
            if lim and len(sl.get("itens") or []) > lim:
                sl = {**sl, "itens": sl["itens"][:lim]}
            paineis.append(sl)
    paineis = paineis[:MAX_PAINEIS]
    if not paineis:
        return []
    return [_slide("assunto", "pagina", cfg.get("titulo") or "Assunto", "", cfg.get("icone") or "bi-layout-text-window",
                   paineis=paineis, card="")]


def _montar_playlist(user, playlist: str, resumo: bool = False) -> list[dict]:
    definicao = obter_playlist(user, playlist)
    resumo = resumo or definicao["resumo"]
    slides: list[dict] = []
    from . import layout

    memo: dict = {}  # cálculos dos módulos reaproveitados entre os cards dos slides manuais
    pares = []  # (provedor, filtros) de todos os conteúdos, inclusive os de dentro dos assuntos e dos slides
    for c, _d, fl in definicao["itens"]:
        if c == CHAVE_SLIDE:
            pares += layout.pares_do_slide(fl)
        elif c == CHAVE_ASSUNTO:
            pares += [(b.get("provedor"), b.get("filtros") or {}) for b in fl.get("blocos") or []]
        else:
            pares.append((c, fl))
    embutidas = [c for c, fl in pares if c in ORIGENS_EMBUTIDAS and fl.get("com_ocorrencias") != "nao"
                 and (not fl.get("cards") or "ocorrencias" in fl["cards"])]
    for chave, duracao, filtros in definicao["itens"]:
        if chave == CHAVE_SLIDE:
            novos = layout.montar_slide(user, filtros, resumo, embutidas, memo)
        elif chave == CHAVE_ASSUNTO:
            novos = _slide_assunto(user, filtros, resumo, embutidas)
        else:
            novos = _slides_provedor(user, chave, filtros, resumo, embutidas)
        seg = duracao or definicao["duracao"]
        if seg:
            for s in novos:
                s["duracao"] = int(seg)
        slides.extend(novos)
    if not slides:
        slides.append(_slide("geral", "vazio", "Nada para exibir", "Sem dados ou sem permissão nesta apresentação.",
                             "bi-inbox"))
    for n, s in enumerate(slides, start=1):
        s["n"] = n
    return slides
