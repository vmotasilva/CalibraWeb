"""Slides com layout do Modo Apresentação: composição automática, slides manuais e "Personalizar".

Um slide de layout (`kind="layout"`) tem vários cards posicionados:
  {"kind": "layout", "titulo", "icone", "duracao", "layout": {"modo": "grade"|"livre", "colunas", "linhas"},
   "itens": [{"card_id", "pos": {x, y, w, h}, "visual": {...}, "conteudo": <slide do card: tiles/cards/bars/chart>}]}
Na grade `pos` está em células (COLUNAS x LINHAS de `cards`); na posição livre, em % do slide (0-100).

Configuração salva (`ModeloApresentacao.slides`, lista de):
  automático: {"origem": "auto", "duracao", "provedor", "filtros": {..., "layout": "2x2"}}
              {"origem": "auto", "tipo": "assunto", "titulo", "icone", "blocos": [{"provedor", "filtros"}]}
  manual:     {"origem": "manual", "duracao", "titulo", "icone", "layout": {"modo": ...},
               "itens": [{"card_id", "params": {"ref": <título da instância>}, "filtros", "pos", "visual"}]}
Os dados são sempre os atuais: o slide automático é remontado a cada execução; o manual só guarda a posição dos cards.
"""
import json
import re

from . import cards

# Disposições do modo automático: chave -> (rótulo, capacidade, posições (x, y, w, h) na grade COLUNAS x LINHAS)
LAYOUTS = {
    "1": ("Um card por slide (tela cheia)", 1, [(0, 0, 12, 8)]),
    "2": ("Dois cards lado a lado", 2, [(0, 0, 6, 8), (6, 0, 6, 8)]),
    "1+2": ("Um em cima e dois embaixo", 3, [(0, 0, 12, 4), (0, 4, 6, 4), (6, 4, 6, 4)]),
    "2x2": ("Quatro cards (2 x 2)", 4, [(0, 0, 6, 4), (6, 0, 6, 4), (0, 4, 6, 4), (6, 4, 6, 4)]),
}
AUTO = "auto"  # escolhe a disposição pela quantidade de cards de cada slide
_AUTO_POR_QTD = {1: "1", 2: "2", 3: "1+2", 4: "2x2"}
OPCOES_LAYOUT = [(AUTO, "Automática (até 4 cards por slide)")] + [(k, v[0]) for k, v in LAYOUTS.items()]

MAX_SLIDES = 60
MAX_ITENS_SLIDE = 12
MAX_BLOCOS = 6
_PARTE = re.compile(r"\s*·?\s*parte \d+(/\d+)?\s*$")
_FORMAS_COM_LISTA = ("tiles", "cards", "bars")


# ---------------------------------------------------------------------------
# Composição
# ---------------------------------------------------------------------------
def juntar_partes(slides: list[dict]) -> list[dict]:
    """Une as "partes" de um mesmo card (listas que o gerador divide em lotes) num só conteúdo, na ordem original."""
    ordem, por_chave = [], {}
    for s in slides:
        chave = (s.get("card_id"), s.get("titulo"))
        if chave not in por_chave:
            por_chave[chave] = {**s, "subtitulo": _PARTE.sub("", s.get("subtitulo") or ""),
                                "itens": list(s["itens"]) if "itens" in s else None}
            if por_chave[chave]["itens"] is None:
                del por_chave[chave]["itens"]
            ordem.append(chave)
        elif s.get("kind") in _FORMAS_COM_LISTA:
            por_chave[chave].setdefault("itens", []).extend(s.get("itens") or [])
    return [por_chave[c] for c in ordem]


def _slide_de_layout(provedor, titulo, icone, itens, modo="grade"):
    from . import providers

    return providers._slide(provedor, "layout", titulo, "", icone, layout={"modo": modo, "colunas": cards.COLUNAS, "linhas": cards.LINHAS},
                            itens=itens, card="", card_id="")


def compor(slides: list[dict], provedor: str, disposicao: str, titulo: str = "", icone: str = "") -> list[dict]:
    """Distribui os conteúdos (slides de um módulo, já filtrados) em slides de layout, na disposição escolhida."""
    from . import providers

    conteudos = juntar_partes(slides)
    if not conteudos:
        return []
    rotulo, ic = providers.ROTULOS_PROVEDORES.get(provedor, (provedor, "bi-display"))
    titulo, icone = titulo or rotulo, icone or ic
    cap = 4 if disposicao == AUTO else LAYOUTS[disposicao][1]
    grupos = [conteudos[i:i + cap] for i in range(0, len(conteudos), cap)]
    saida = []
    for n, grupo in enumerate(grupos, start=1):
        chave = _AUTO_POR_QTD[len(grupo)] if disposicao == AUTO else disposicao
        posicoes = LAYOUTS[chave][2]
        itens = [{"card_id": c.get("card_id") or "", "params": {"ref": c.get("titulo") or ""},
                  "pos": dict(zip("xywh", posicoes[k])), "visual": {"titulo": True, "max_itens": None}, "conteudo": c}
                 for k, c in enumerate(grupo)]
        saida.append(_slide_de_layout(provedor, titulo + (f" ({n}/{len(grupos)})" if len(grupos) > 1 else ""), icone, itens))
    return saida


def aplicar_visual(conteudo: dict, visual: dict | None) -> dict:
    """Roupagem do card: hoje, o número máximo de itens das listas (tiles/cards/bars)."""
    maximo = (visual or {}).get("max_itens")
    if maximo and conteudo.get("kind") in _FORMAS_COM_LISTA and len(conteudo.get("itens") or []) > maximo:
        return {**conteudo, "itens": conteudo["itens"][:maximo]}
    return conteudo


# ---------------------------------------------------------------------------
# Slides manuais: resolver cada item para o conteúdo atual
# ---------------------------------------------------------------------------
def _slides_do_modulo(user, provedor, filtros, resumo, embutidas, memo):
    from . import providers

    base = {k: v for k, v in (filtros or {}).items() if k not in ("cards", "layout")}
    if provedor == "kpi":  # card escolhido à mão aparece sempre (o padrão do módulo é só os indicadores fora da meta)
        base.setdefault("graficos", "todos")
        base.setdefault("_motivos", True)
    chave = (provedor, json.dumps(base, sort_keys=True, default=str))
    if chave not in memo:  # um módulo é calculado uma vez, mesmo com vários cards dele no slide
        memo[chave] = providers._slides_provedor(user, provedor, base, resumo, embutidas)
    return memo[chave]


def resolver_item(user, item: dict, resumo: bool, embutidas: list, memo: dict) -> dict | None:
    """Conteúdo atual do card (e da instância, se houver) ou None se não há dado/permissão."""
    cid = item.get("card_id") or ""
    if cid not in cards.CARDS:
        return None
    provedor = cid.split(".", 1)[0]
    slides = [s for s in _slides_do_modulo(user, provedor, item.get("filtros"), resumo, embutidas, memo) if s.get("card_id") == cid]
    ref = (item.get("params") or {}).get("ref")
    if ref:
        slides = [s for s in slides if s.get("titulo") == ref]
    juntos = juntar_partes(slides)
    return aplicar_visual(juntos[0], item.get("visual")) if juntos else None


def instancias(user, card_id: str, filtros: dict | None = None, resumo: bool = False) -> list[str]:
    """Títulos das instâncias que o card tem hoje (um por indicador, por relatório, por grupo...)."""
    if card_id not in cards.CARDS:
        return []
    provedor = card_id.split(".", 1)[0]
    slides = _slides_do_modulo(user, provedor, filtros, resumo, [], {})
    return [s["titulo"] for s in juntar_partes([s for s in slides if s.get("card_id") == card_id])]


def montar_manual(user, cfg: dict, resumo: bool, embutidas: list, memo: dict, duracao_padrao=None) -> list[dict]:
    itens = []
    for it in cfg.get("itens") or []:
        conteudo = resolver_item(user, it, resumo, embutidas, memo)
        if conteudo:
            itens.append({"card_id": it["card_id"], "pos": it.get("pos") or {}, "visual": it.get("visual") or {}, "conteudo": conteudo})
    if not itens:
        return []
    lay = cfg.get("layout") or {}
    slide = _slide_de_layout("layout", cfg.get("titulo") or "Slide", cfg.get("icone") or "bi-layout-text-window", itens,
                             modo="livre" if lay.get("modo") == "livre" else "grade")
    if cfg.get("duracao") or duracao_padrao:
        slide["duracao"] = int(cfg.get("duracao") or duracao_padrao)
    return [slide]


# ---------------------------------------------------------------------------
# Montagem de um slide da configuração (automático ou manual) e "Personalizar"
# ---------------------------------------------------------------------------
def pares_do_slide(cfg: dict) -> list[tuple[str, dict]]:
    """(módulo, filtros) de tudo que o slide usa — serve para decidir quais ocorrências ficam embutidas nos módulos."""
    if cfg.get("origem") == "manual":
        return [(i["card_id"].split(".", 1)[0], {"cards": [i["card_id"].split(".", 1)[1]]})
                for i in cfg.get("itens") or [] if i.get("card_id") in cards.CARDS]
    if cfg.get("tipo") == "assunto":
        return [(b.get("provedor"), b.get("filtros") or {}) for b in cfg.get("blocos") or []]
    return [(cfg.get("provedor"), cfg.get("filtros") or {})]


def montar_slide(user, cfg: dict, resumo: bool, embutidas: list, memo: dict) -> list[dict]:
    from . import providers

    if cfg.get("origem") == "manual":
        return montar_manual(user, cfg, resumo, embutidas, memo)
    if cfg.get("tipo") == "assunto":
        novos = providers._slide_assunto(user, cfg, resumo, embutidas)
    else:
        novos = providers._slides_provedor(user, cfg.get("provedor"), cfg.get("filtros") or {}, resumo, embutidas)
    if cfg.get("duracao"):
        for s in novos:
            s["duracao"] = int(cfg["duracao"])
    return novos


def _manual_de_layout(slide: dict, duracao) -> dict:
    return {"origem": "manual", "duracao": duracao, "titulo": slide["titulo"], "icone": slide["icone"],
            "layout": {"modo": "grade", "colunas": cards.COLUNAS, "linhas": cards.LINHAS},
            "itens": [{"card_id": i["card_id"], "params": i["params"] if "params" in i else {"ref": i["conteudo"].get("titulo", "")},
                       "pos": i["pos"], "visual": i["visual"]} for i in slide["itens"] if i["card_id"] in cards.CARDS]}


def materializar(user, cfg: dict, resumo: bool = False) -> list[dict]:
    """"Personalizar": congela um slide automático em um ou mais slides manuais, com a disposição atual dos cards.
    O resultado é só a configuração (posições e instâncias): os dados continuam vindo ao vivo."""
    from . import providers

    if cfg.get("origem") == "manual":
        return [cfg]
    duracao = cfg.get("duracao")
    if cfg.get("tipo") == "assunto":
        brutos = []
        for b in cfg.get("blocos") or []:
            brutos += providers._slides_provedor(user, b.get("provedor"), {k: v for k, v in (b.get("filtros") or {}).items() if k != "layout"}, resumo, [])
        base = compor(brutos, "assunto", AUTO, cfg.get("titulo") or "Assunto", cfg.get("icone") or "bi-layout-text-window")
    else:
        filtros = {**(cfg.get("filtros") or {})}
        if filtros.get("layout") not in LAYOUTS:
            filtros["layout"] = AUTO
        base = providers._slides_provedor(user, cfg.get("provedor"), filtros, resumo, [])
    return [_manual_de_layout(s, duracao) for s in base if s.get("kind") == "layout"]


# ---------------------------------------------------------------------------
# Editor visual: conversão do formato antigo, prévia por card
# ---------------------------------------------------------------------------
def legado_para_slides(itens) -> list[dict]:
    """Conteúdos do formato antigo (`ModeloApresentacao.itens`) como slides automáticos equivalentes."""
    saida = []
    for i in itens or []:
        if not isinstance(i, dict):
            continue
        if i.get("tipo") == "assunto":
            saida.append({"origem": "auto", "tipo": "assunto", "duracao": i.get("duracao"), "titulo": i.get("titulo") or "Assunto",
                          "icone": i.get("icone") or "", "blocos": [b for b in i.get("blocos") or [] if isinstance(b, dict)]})
        elif i.get("provedor"):
            saida.append({"origem": "auto", "duracao": i.get("duracao"), "provedor": i["provedor"], "filtros": i.get("filtros") or {}})
    return saida


def slides_do_modelo(modelo) -> list[dict]:
    """Slides do modelo: os salvos ou, se o modelo ainda é do formato antigo, a conversão dos seus conteúdos."""
    return list(modelo.slides) if modelo.slides else legado_para_slides(modelo.itens)


def slides_da_geral() -> list[dict]:
    from . import providers

    return [{"origem": "auto", "provedor": p, "filtros": {}} for p in providers.PLAYLISTS[providers.PLAYLIST_PADRAO][2]]


def previa(user, cfg, resumo: bool = False) -> dict:
    """Conteúdo atual de um slide para o editor. Manual: {"itens": [conteúdo ou None, ...]} alinhado aos itens enviados
    (None = sem dado ou sem permissão). Automático: {"slides": [...]} com o que o gerador monta hoje (até 6)."""
    memo: dict = {}
    if isinstance(cfg, dict) and cfg.get("origem") == "manual":
        modo = "livre" if (cfg.get("layout") or {}).get("modo") == "livre" else "grade"
        saida = []
        for bruto in (cfg.get("itens") or [])[:MAX_ITENS_SLIDE]:
            item = limpar_item(bruto, modo, user)
            saida.append(resolver_item(user, item, resumo, [], memo) if item else None)
        return {"itens": saida}
    limpo = limpar_slide(cfg, user)
    return {"slides": montar_slide(user, limpo, resumo, [], memo)[:6] if limpo else []}


# ---------------------------------------------------------------------------
# Sanitização (entrada vinda do editor)
# ---------------------------------------------------------------------------
def _inteiro(v, minimo, maximo, padrao):
    try:
        return min(max(int(v), minimo), maximo)
    except (TypeError, ValueError):
        return padrao


def _decimal(v, minimo, maximo, padrao):
    try:
        return round(min(max(float(v), minimo), maximo), 2)
    except (TypeError, ValueError):
        return padrao


def limpar_pos(pos, modo: str) -> dict:
    pos = pos if isinstance(pos, dict) else {}
    if modo == "livre":
        x, y = _decimal(pos.get("x"), 0, 99, 0), _decimal(pos.get("y"), 0, 99, 0)
        return {"x": x, "y": y, "w": _decimal(pos.get("w"), 1, 100 - x, min(50, 100 - x)), "h": _decimal(pos.get("h"), 1, 100 - y, min(50, 100 - y))}
    x, y = _inteiro(pos.get("x"), 0, cards.COLUNAS - 1, 0), _inteiro(pos.get("y"), 0, cards.LINHAS - 1, 0)
    return {"x": x, "y": y, "w": _inteiro(pos.get("w"), 1, cards.COLUNAS - x, min(6, cards.COLUNAS - x)),
            "h": _inteiro(pos.get("h"), 1, cards.LINHAS - y, min(4, cards.LINHAS - y))}


def limpar_filtros_dict(provedor: str, bruto, user) -> dict:
    """Como `providers.limpar_filtros`, mas a partir de um dicionário (JSON), descartando o que não é opção válida."""
    from . import providers

    bruto = bruto if isinstance(bruto, dict) else {}
    filtros = {}
    for c in providers.campos_filtro(provedor, user):
        v = bruto.get(c["nome"])
        validos = {str(x) for x, _ in c["opcoes"]}
        if c["tipo"] == "multi":
            marcados = [str(x) for x in (v if isinstance(v, list) else []) if str(x) in validos]
            if marcados:
                filtros[c["nome"]] = marcados
        elif c["tipo"] == "select":
            if v and str(v) in validos:
                filtros[c["nome"]] = str(v)
        elif c["tipo"] == "bool" and v is True:
            filtros[c["nome"]] = True
    return filtros


def _icone(v) -> str:
    v = (v or "").strip() if isinstance(v, str) else ""
    return v if v.startswith("bi-") and len(v) <= 40 else ""


def limpar_item(it, modo: str, user) -> dict | None:
    from . import providers

    if not isinstance(it, dict) or it.get("card_id") not in cards.CARDS:
        return None
    provedor = it["card_id"].split(".", 1)[0]
    visual = it.get("visual") if isinstance(it.get("visual"), dict) else {}
    params = it.get("params") if isinstance(it.get("params"), dict) else {}
    saida = {"card_id": it["card_id"], "pos": limpar_pos(it.get("pos"), modo),
             "visual": {"titulo": visual.get("titulo") is not False,
                        "max_itens": _inteiro(visual.get("max_itens"), 1, 50, None) if visual.get("max_itens") else None}}
    if visual.get("moldura") == "sem":  # sem fundo/borda do card
        saida["visual"]["moldura"] = "sem"
    if params.get("ref"):
        saida["params"] = {"ref": str(params["ref"])[:200]}
    filtros = limpar_filtros_dict(provedor, it.get("filtros"), user)
    filtros.pop("cards", None)
    filtros.pop("layout", None)
    if filtros:
        saida["filtros"] = filtros
    return saida


def limpar_slide(cfg, user) -> dict | None:
    from . import providers

    if not isinstance(cfg, dict):
        return None
    duracao = _inteiro(cfg.get("duracao"), 5, 120, None) if cfg.get("duracao") else None
    if cfg.get("origem") == "manual":
        lay = cfg.get("layout") if isinstance(cfg.get("layout"), dict) else {}
        modo = "livre" if lay.get("modo") == "livre" else "grade"
        itens = [i for i in (limpar_item(x, modo, user) for x in (cfg.get("itens") or [])[:MAX_ITENS_SLIDE]) if i]
        return {"origem": "manual", "duracao": duracao, "titulo": str(cfg.get("titulo") or "Slide").strip()[:100] or "Slide",
                "icone": _icone(cfg.get("icone")), "layout": {"modo": modo, "colunas": cards.COLUNAS, "linhas": cards.LINHAS}, "itens": itens}
    if cfg.get("tipo") == "assunto":
        blocos = [{"provedor": b["provedor"], "filtros": limpar_filtros_dict(b["provedor"], b.get("filtros"), user)}
                  for b in (cfg.get("blocos") or [])[:MAX_BLOCOS] if isinstance(b, dict) and b.get("provedor") in providers.PROVEDORES]
        if not blocos:
            return None
        return {"origem": "auto", "tipo": "assunto", "duracao": duracao, "titulo": str(cfg.get("titulo") or "Assunto").strip()[:100] or "Assunto",
                "icone": _icone(cfg.get("icone")), "blocos": blocos}
    if cfg.get("provedor") not in providers.PROVEDORES:
        return None
    return {"origem": "auto", "duracao": duracao, "provedor": cfg["provedor"],
            "filtros": limpar_filtros_dict(cfg["provedor"], cfg.get("filtros"), user)}


def limpar_slides(lista, user) -> list[dict]:
    return [s for s in (limpar_slide(c, user) for c in (lista if isinstance(lista, list) else [])[:MAX_SLIDES]) if s]
