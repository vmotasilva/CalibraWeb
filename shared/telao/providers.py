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

import logging
from datetime import datetime
from typing import Callable

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

DURACAO_PADRAO = 15  # segundos por slide
CARDS_POR_SLIDE = 4
MAX_SLIDES_CARDS = 3
RESUMO_TEXTO = 110


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


def slides_ocorrencias(user, resumo=False):
    from shared import ocorrencias as central

    itens = central.listar_ocorrencias(user, "abertas")
    hoje = timezone.localdate()
    vencidas = [i for i in itens if i.vencida]
    minhas = [i for i in itens if i.envolve_usuario]
    slides = []

    tiles = [
        {"rotulo": "Em aberto", "valor": len(itens), "tom": "alerta" if itens else "ok"},
        {"rotulo": "Vencidas", "valor": len(vencidas), "tom": "critico" if vencidas else "ok"},
        {"rotulo": "Envolvem você", "valor": len(minhas), "tom": "neutro"},
    ]
    por_origem = {}
    for i in itens:
        por_origem[i.origem_nome] = por_origem.get(i.origem_nome, 0) + 1
    tiles += [{"rotulo": nome, "valor": qtd, "tom": "neutro", "nota": "em aberto"}
              for nome, qtd in sorted(por_origem.items(), key=lambda kv: -kv[1])]
    slides.append(_slide("ocorrencias", "tiles", "Ocorrências em aberto", "Todos os módulos",
                         "bi-exclamation-triangle", itens=tiles))

    prioridade = vencidas or sorted(itens, key=lambda i: i.data_ordem)
    prioridade = sorted(prioridade, key=lambda i: (i.prazo is None, i.prazo or hoje))
    titulo = "Ocorrências vencidas" if vencidas else "Ocorrências mais antigas"
    cards = []
    for i in prioridade[: CARDS_POR_SLIDE * MAX_SLIDES_CARDS]:
        tags = [i.origem_nome]
        if i.prazo:
            tags.append(f"prazo {i.prazo:%d/%m/%Y}")
        if i.responsaveis and not resumo:
            tags.append(", ".join(i.responsaveis[:2]))
        dias = max((hoje - timezone.localtime(i.data_ordem).date()).days, 0)
        tags.append(f"{dias} d em aberto")
        cards.append({
            "titulo": _corta(i.titulo, 100),
            "texto": "" if resumo else _corta(i.descricao, 220),
            "tom": "critico" if i.vencida else "alerta", "tags": tags,
        })
    for n, lote in enumerate(_lotes(cards, CARDS_POR_SLIDE), start=1):
        slides.append(_slide("ocorrencias", "cards", titulo, f"parte {n}" if len(cards) > CARDS_POR_SLIDE else "",
                             "bi-exclamation-octagon", itens=lote))

    if not resumo:
        coment = []
        for i in itens:
            for p in i.plano:
                for c in p.comentarios:
                    coment.append((_quando(c["quando"]), i, p, c))
        coment.sort(key=lambda t: t[0], reverse=True)
        cards = [{
            "titulo": _corta(i.titulo, 90), "texto": _corta(c["texto"], 240), "tom": "neutro",
            "tags": [c["autor"], c["quando"], f"ação: {_corta(p.descricao, 40)}"],
        } for _, i, p, c in coment[:CARDS_POR_SLIDE]]
        if cards:
            slides.append(_slide("ocorrencias", "cards", "Comentários recentes", "Plano de ação das ocorrências",
                                 "bi-chat-left-text", itens=cards))
    return slides


# ---------------------------------------------------------------------------
# KPI (indicadores gerais)
# ---------------------------------------------------------------------------
def slides_kpi(user, resumo=False):
    from kpi.models import Indicador
    from shared.permissions import has_view_access

    if not has_view_access(user, "kpi:painel"):
        return []
    linhas = []
    for ind in Indicador.objects.filter(ativo=True).prefetch_related("medicoes"):
        gerais = sorted((m for m in ind.medicoes.all() if m.setor_id is None and m.granularidade == "mensal"),
                        key=lambda m: m.periodo)
        ultima = gerais[-1] if gerais else None
        atingiu = ind.atingiu(ultima.valor) if ultima else None
        linhas.append((ind, gerais[-12:], ultima, atingiu))
    if not linhas:
        return []

    ok = sum(1 for *_, a in linhas if a is True)
    fora = sum(1 for *_, a in linhas if a is False)
    slides = [_slide("kpi", "tiles", "Indicadores — situação geral", "Último mês lançado de cada indicador",
                     "bi-speedometer2", itens=[
        {"rotulo": "Na meta", "valor": ok, "tom": "ok"},
        {"rotulo": "Fora da meta", "valor": fora, "tom": "critico" if fora else "ok"},
        {"rotulo": "Sem dado", "valor": len(linhas) - ok - fora, "tom": "neutro"},
    ] + [{
        "rotulo": ind.nome, "valor": f"{_fmt_num(ult.valor, 2)}{ind.unidade}" if ult else "—",
        "tom": "neutro" if a is None else "ok" if a else "critico",
        "nota": f"meta {_fmt_num(ind.meta, 2)}{ind.unidade} · {ult.periodo:%m/%Y}" if ult else "sem lançamento",
    } for ind, _s, ult, a in linhas[:18]])]

    for ind, serie, ult, a in [l for l in linhas if l[3] is False][:6]:
        slides.append(_slide("kpi", "chart", ind.nome, f"Fora da meta · {'maior' if ind.sentido == 'maior' else 'menor'} é melhor",
                             "bi-graph-down-arrow", labels=[m.periodo.strftime("%m/%Y") for m in serie],
                             valores=[float(m.valor) for m in serie], meta=float(ind.meta), unidade=ind.unidade))
    return slides


# ---------------------------------------------------------------------------
# Auditoria (checklists periódicos: último ciclo fechado de cada modelo)
# ---------------------------------------------------------------------------
def _dados_modelo(modelo):
    chave = f"telao:auditoria:v1:{modelo.pk}"
    dados = cache.get(chave)
    if dados is None:
        from auditoria.apresentacao import montar_apresentacao

        a = montar_apresentacao(modelo, max_ciclos=8)
        dados = {
            "nome": modelo.nome, "pct": a["pct_geral"], "variacao": a["variacao"],
            "ciclos": [{"label": c["label"], "pct": c["pct"]} for c in a["ciclos"]],
            "criticas": [{"pergunta": c["pergunta"], "ncs": c["ncs"], "semanas": c["semanas"]} for c in a["criticas"][:4]],
            "abertas": a["total_ocorrencias_abertas"], "vencidas": a["ocorrencias_vencidas"],
            "periodo": a["periodo_txt"], "tem_ciclo": a["base"] is not None,
        }
        cache.set(chave, dados, 120)
    return dados


def slides_auditoria(user, resumo=False):
    from auditoria.models import ModeloAuditoria
    from auditoria.views import _filter_modelos_para_usuario
    from shared.permissions import has_module_access

    if not has_module_access(user, "auditoria"):
        return []
    modelos = list(_filter_modelos_para_usuario(user, ModeloAuditoria.objects.all()).order_by("nome")[:10])
    dados = [d for d in (_dados_modelo(m) for m in modelos) if d["tem_ciclo"]]
    if not dados:
        return []
    ordenados = sorted(dados, key=lambda d: (d["pct"] is None, d["pct"] if d["pct"] is not None else 0))
    slides = [_slide("auditoria", "bars", "Conformidade — último ciclo fechado", "% de itens conformes por auditoria",
                     "bi-clipboard-check", itens=[{
        "rotulo": d["nome"], "pct": d["pct"] or 0, "tom": _tom_pct(d["pct"]),
        "txt": (f"{_fmt_num(d['pct'], 1)}%" if d["pct"] is not None else "—")
               + (f"  ({'+' if d['variacao'] > 0 else ''}{_fmt_num(d['variacao'], 1)})" if d["variacao"] else ""),
    } for d in ordenados])]
    for d in ordenados[:4]:
        pontos = [c for c in d["ciclos"] if c["pct"] is not None]
        if len(pontos) > 1:
            slides.append(_slide("auditoria", "chart", d["nome"], f"Evolução da conformidade · {d['periodo']}",
                                 "bi-graph-up", labels=[c["label"] for c in pontos],
                                 valores=[c["pct"] for c in pontos], meta=100, unidade="%"))
        if d["criticas"]:
            slides.append(_slide("auditoria", "cards", f"{d['nome']} — pontos de atenção",
                                 f"{d['abertas']} ocorrência(s) em aberto · {d['vencidas']} vencida(s)", "bi-flag",
                                 itens=[{"titulo": _corta(c["pergunta"], 120), "texto": "", "tom": "critico",
                                         "tags": [f"{c['ncs']} NC", f"{c['semanas']} semana(s) seguidas"] if c["semanas"] else [f"{c['ncs']} NC"]}
                                        for c in d["criticas"]]))
    return slides


PROVEDORES: dict[str, Callable] = {
    "ocorrencias": slides_ocorrencias,
    "kpi": slides_kpi,
    "auditoria": slides_auditoria,
}

# Playlists (modelos de apresentação): nome -> provedores em ordem de rotação.
PLAYLISTS = {
    "geral": ("Geral", "bi-grid-1x2", ("ocorrencias", "kpi", "auditoria")),
    "ocorrencias": ("Ocorrências", "bi-exclamation-triangle", ("ocorrencias",)),
    "kpi": ("Indicadores (KPI)", "bi-speedometer2", ("kpi",)),
    "auditoria": ("Auditorias", "bi-clipboard-check", ("auditoria",)),
}
PLAYLIST_PADRAO = "geral"


def montar_playlist(user, playlist: str, resumo: bool = False) -> list[dict]:
    nome, _icone, provedores = PLAYLISTS.get(playlist, PLAYLISTS[PLAYLIST_PADRAO])
    slides: list[dict] = []
    for chave in provedores:
        try:
            slides.extend(PROVEDORES[chave](user, resumo=resumo))
        except Exception:  # um módulo com problema não derruba a rotação
            logger.exception("Telão: provedor %s falhou", chave)
    if not slides:
        slides.append(_slide("geral", "vazio", "Nada para exibir", "Sem dados ou sem permissão nesta playlist.",
                             "bi-inbox"))
    for n, s in enumerate(slides, start=1):
        s["n"] = n
    return slides
