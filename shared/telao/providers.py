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


# ---------------------------------------------------------------------------
# Metrologia (instrumentos vencidos / a vencer)
# ---------------------------------------------------------------------------
def _dados_metrologia():
    dados = cache.get("telao:metrologia:v1")
    if dados is None:
        from metrologia.views.views import get_metrologia_dashboard_data

        d = get_metrologia_dashboard_data()
        criticos = [i for i in d["instrumentos"] if i["status_situacao"] in ("VENCIDO", "AVENCER_30")]
        dados = {
            "kpis": d["kpis"],
            "criticos": [{
                "tag": i["tag"], "descricao": i["descricao"], "setor": i["setor_nome"], "venc": i["status_situacao"] == "VENCIDO",
                "data": i["data_proxima_calibracao_display"], "dias": i["dias_para_vencer"], "externo": not i["is_internal"],
                "ocorrencia": i["has_active_occurrence"],
            } for i in criticos[:8]],
        }
        cache.set("telao:metrologia:v1", dados, 120)
    return dados


def slides_metrologia(user, resumo=False):
    from shared.permissions import has_module_access

    if not has_module_access(user, "metrologia"):
        return []
    d = _dados_metrologia()
    k, ext = d["kpis"]["todos"], d["kpis"]["externo"]
    slides = [_slide("metrologia", "tiles", "Metrologia — calibrações", f"{k['total_instrumentos']} instrumentos ativos",
                     "bi-tools", itens=[
        {"rotulo": "Vencidos", "valor": k["vencidos"], "tom": "critico" if k["vencidos"] else "ok"},
        {"rotulo": "A vencer em 30 dias", "valor": k["avencer_30"], "tom": "alerta" if k["avencer_30"] else "ok"},
        {"rotulo": "Em dia", "valor": k["em_dia"], "tom": "ok"},
        {"rotulo": "Ocorrências ativas", "valor": k["ocorrencias_ativas"], "tom": "alerta" if k["ocorrencias_ativas"] else "ok"},
        {"rotulo": "Cotações abertas", "valor": ext["cotacoes_abertas"], "tom": "neutro"},
        {"rotulo": "Orçamentos pendentes", "valor": ext["orcamentos_pendentes"], "tom": "neutro"},
    ])]
    cards = []
    for i in d["criticos"]:
        quando = f"venceu em {i['data']}" if i["venc"] else f"vence em {i['data']}"
        tags = [i["setor"], quando, "calibração externa" if i["externo"] else "calibração interna"]
        if i["ocorrencia"]:
            tags.append("com ocorrência")
        cards.append({"titulo": f"{i['tag']} — {_corta(i['descricao'], 70)}", "texto": "",
                      "tom": "critico" if i["venc"] else "alerta", "tags": tags})
    for n, lote in enumerate(_lotes(cards, CARDS_POR_SLIDE), start=1):
        slides.append(_slide("metrologia", "cards", "Instrumentos críticos", f"parte {n}" if len(cards) > CARDS_POR_SLIDE else "",
                             "bi-exclamation-octagon", itens=lote))
    return slides


# ---------------------------------------------------------------------------
# PCP (cumprimento das verificações)
# ---------------------------------------------------------------------------
def _dados_pcp():
    dados = cache.get("telao:pcp:v1")
    if dados is None:
        import datetime

        from pcp import pendencias as pend
        from pcp.models import Turno

        hoje = timezone.localdate()
        fim = hoje - datetime.timedelta(days=1)
        ini = fim - datetime.timedelta(days=29)
        d = pend.dashboard(ini, fim, list(Turno.objects.filter(ativo=True)), None, hoje)
        paginas = [(l, b["titulo"]) for b in d["blocos"] for g in b["grupos"] for l in g["linhas"]
                   if l["pct"] is not None and l["devidos"] >= pend.MIN_PRAZOS_PAGINA]
        paginas.sort(key=lambda t: t[0]["pct"])
        dados = {
            "ini": ini, "fim": fim, "pct": d["pct"], "devidos": d["devidos"], "feitos": d["feitos"], "atrasados": d["atrasados"],
            "evolucao": [{"rotulo": e["rotulo"], "pct": e["pct"]} for e in d["evolucao"] if e["pct"] is not None],
            "frequencias": [{"nome": f["nome"], "pct": f["pct"]} for f in d["por_frequencia"] if f["pct"] is not None],
            "piores": [{"nome": f"{t} · {l['nome']}", "pct": l["pct"]} for l, t in paginas[:6]],
        }
        cache.set("telao:pcp:v1", dados, 120)
    return dados


def slides_pcp(user, resumo=False):
    from shared.permissions import has_view_access

    if not has_view_access(user, "pcp:dashboard"):
        return []
    d = _dados_pcp()
    if not d["devidos"]:
        return []
    sub = f"{d['ini']:%d/%m} a {d['fim']:%d/%m} (últimos 30 dias)"
    slides = [_slide("pcp", "tiles", "PCP — cumprimento das verificações", sub, "bi-gear-wide-connected", itens=[
        {"rotulo": "Cumprimento", "valor": f"{_fmt_num(d['pct'], 1)}%", "tom": _tom_pct(d["pct"])},
        {"rotulo": "Devidas", "valor": d["devidos"], "tom": "neutro"},
        {"rotulo": "Feitas", "valor": d["feitos"], "tom": "ok"},
        {"rotulo": "Em atraso", "valor": d["atrasados"], "tom": "critico" if d["atrasados"] else "ok"},
    ])]
    if len(d["evolucao"]) > 1:
        slides.append(_slide("pcp", "chart", "PCP — evolução do cumprimento", sub, "bi-graph-up",
                             labels=[e["rotulo"] for e in d["evolucao"]], valores=[e["pct"] for e in d["evolucao"]],
                             meta=100, unidade="%"))
    for titulo, lista, icone in (("PCP — cumprimento por frequência", d["frequencias"], "bi-calendar-check"),
                                 ("PCP — páginas com menor cumprimento", d["piores"], "bi-flag")):
        if lista:
            slides.append(_slide("pcp", "bars", titulo, sub, icone, itens=[
                {"rotulo": x["nome"], "pct": x["pct"], "tom": _tom_pct(x["pct"]), "txt": f"{_fmt_num(x['pct'], 1)}%"} for x in lista]))
    return slides


# ---------------------------------------------------------------------------
# Laboratório (rendimento HC, mês do último lançamento)
# ---------------------------------------------------------------------------
def _dados_lab():
    dados = cache.get("telao:lab:v1")
    if dados is None:
        import calendar

        from laboratorio import hc_rendimento as hc
        from laboratorio.models import RendimentoHCRegistro

        ultimo = RendimentoHCRegistro.objects.order_by("-data").values_list("data", flat=True).first()
        if ultimo is None:
            dados = {"vazio": True}
        else:
            ini = ultimo.replace(day=1)
            fim = ini.replace(day=calendar.monthrange(ini.year, ini.month)[1])
            c = hc.consolidado(ini, fim)
            dados = {"vazio": False, "mes": f"{ini:%m/%Y}", "meta": c["meta"], "total": c["total"],
                     "dias": [{"rotulo": f"{l['data']:%d/%m}", "rend": l["rendimento"]} for l in c["linhas"] if l["rendimento"] is not None]}
        cache.set("telao:lab:v1", dados, 120)
    return dados


def slides_laboratorio(user, resumo=False):
    from shared.permissions import has_view_access

    if not has_view_access(user, "laboratorio:hc_dashboard"):
        return []
    d = _dados_lab()
    if d["vazio"]:
        return []
    t, meta = d["total"], d["meta"]
    tom_rend = "neutro" if t["rendimento"] is None else "ok" if t["rendimento"] >= meta else "critico"
    slides = [_slide("laboratorio", "tiles", "Laboratório — rendimento HC", f"Mês {d['mes']} · meta {_fmt_num(meta, 1)}%",
                     "bi-droplet-half", itens=[
        {"rotulo": "Rendimento", "valor": f"{_fmt_num(t['rendimento'], 1)}%", "tom": tom_rend, "nota": f"meta {_fmt_num(meta, 1)}%"},
        {"rotulo": "Retrabalho", "valor": f"{_fmt_num(t['pct_retrabalho'], 1)}%", "tom": "neutro"},
        {"rotulo": "Lentes produzidas", "valor": _fmt_num(t["produzidas"], 0), "tom": "neutro"},
        {"rotulo": "Lentes em retrabalho", "valor": _fmt_num(t["retrabalho"], 0), "tom": "alerta" if t["retrabalho"] else "ok"},
    ])]
    if len(d["dias"]) > 1:
        slides.append(_slide("laboratorio", "chart", "Laboratório — rendimento HC por dia", f"Mês {d['mes']}", "bi-graph-up",
                             labels=[x["rotulo"] for x in d["dias"]], valores=[x["rend"] for x in d["dias"]], meta=meta, unidade="%"))
    return slides


# ---------------------------------------------------------------------------
# Treinamentos (planejamento)
# ---------------------------------------------------------------------------
def slides_treinamentos(user, resumo=False):
    import datetime

    from procedures.models import PlanejamentoTreinamento as P
    from shared.permissions import has_view_access

    if not has_view_access(user, "procedures:dashboard_treinamentos"):
        return []
    hoje = timezone.localdate()
    abertos = P.objects.filter(status__in=("PLANEJADO", "CONFIRMADO", "ATRASADO"))
    atrasados = abertos.filter(data_prevista__lt=hoje).count()
    proximos_qs = abertos.filter(data_prevista__gte=hoje).order_by("data_prevista")
    proximos = list(proximos_qs[:8])
    realizados_mes = P.objects.filter(status="REALIZADO", data_realizada__year=hoje.year, data_realizada__month=hoje.month).count()
    if not (atrasados or proximos or realizados_mes):
        return []
    slides = [_slide("treinamentos", "tiles", "Treinamentos", f"Posição em {hoje:%d/%m/%Y}", "bi-mortarboard", itens=[
        {"rotulo": "Atrasados", "valor": atrasados, "tom": "critico" if atrasados else "ok"},
        {"rotulo": "Próximos 30 dias", "valor": proximos_qs.filter(data_prevista__lte=hoje + datetime.timedelta(days=30)).count(), "tom": "neutro"},
        {"rotulo": "Realizados no mês", "valor": realizados_mes, "tom": "ok"},
    ])]
    cards = [{"titulo": _corta(p.titulo, 100), "texto": "", "tom": "neutro",
              "tags": [f"{p.data_prevista:%d/%m/%Y}", f"em {(p.data_prevista - hoje).days} d", p.get_status_display()]
                      + ([p.local] if p.local and not resumo else [])} for p in proximos]
    for n, lote in enumerate(_lotes(cards, CARDS_POR_SLIDE), start=1):
        slides.append(_slide("treinamentos", "cards", "Próximos treinamentos", f"parte {n}" if len(cards) > CARDS_POR_SLIDE else "",
                             "bi-calendar-event", itens=lote))
    return slides


PROVEDORES: dict[str, Callable] = {
    "ocorrencias": slides_ocorrencias,
    "kpi": slides_kpi,
    "auditoria": slides_auditoria,
    "metrologia": slides_metrologia,
    "pcp": slides_pcp,
    "laboratorio": slides_laboratorio,
    "treinamentos": slides_treinamentos,
}

# Playlists (modelos de apresentação): nome -> provedores em ordem de rotação.
PLAYLISTS = {
    "geral": ("Geral", "bi-grid-1x2",
              ("ocorrencias", "kpi", "auditoria", "metrologia", "pcp", "laboratorio", "treinamentos")),
    "ocorrencias": ("Ocorrências", "bi-exclamation-triangle", ("ocorrencias",)),
    "kpi": ("Indicadores (KPI)", "bi-speedometer2", ("kpi",)),
    "auditoria": ("Auditorias", "bi-clipboard-check", ("auditoria",)),
    "qualidade": ("Qualidade", "bi-patch-check", ("auditoria", "kpi", "metrologia", "treinamentos")),
    "producao": ("Produção", "bi-gear-wide-connected", ("pcp", "laboratorio")),
    "metrologia": ("Metrologia", "bi-tools", ("metrologia",)),
    "pcp": ("PCP", "bi-clipboard-data", ("pcp",)),
    "laboratorio": ("Laboratório", "bi-droplet-half", ("laboratorio",)),
    "treinamentos": ("Treinamentos", "bi-mortarboard", ("treinamentos",)),
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
            itens = [(i.get("provedor"), i.get("duracao")) for i in (m.itens or []) if isinstance(i, dict)]
            return {"chave": m.chave, "nome": m.nome, "icone": m.icone or "bi-display", "itens": itens,
                    "duracao": m.duracao_padrao or DURACAO_PADRAO, "resumo": m.resumo}
    nome, icone, provedores = PLAYLISTS.get(chave, PLAYLISTS[PLAYLIST_PADRAO])
    chave = chave if chave in PLAYLISTS else PLAYLIST_PADRAO
    return {"chave": chave, "nome": nome, "icone": icone, "itens": [(p, None) for p in provedores],
            "duracao": None, "resumo": False}


def montar_playlist(user, playlist: str, resumo: bool = False) -> list[dict]:
    definicao = obter_playlist(user, playlist)
    resumo = resumo or definicao["resumo"]
    slides: list[dict] = []
    for chave, duracao in definicao["itens"]:
        if chave not in PROVEDORES:
            continue
        try:
            novos = PROVEDORES[chave](user, resumo=resumo)
        except Exception:  # um módulo com problema não derruba a rotação
            logger.exception("Telão: provedor %s falhou", chave)
            continue
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
