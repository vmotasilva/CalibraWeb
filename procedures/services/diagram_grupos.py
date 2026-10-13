# -*- coding: utf-8 -*-
"""Geometria dos grupos (boundary) do diagrama. Espelha procedures/static/procedures/js/diagrama/grupos.js
(um teste compara as duas implementações)."""

PAD_BASE = 22
PAD_NIVEL = 10
TITULO_H = 24
RESUMO_W = 220
RESUMO_GAP = 12


def _visiveis(grupo: dict, caixas: dict) -> list:
    return [str(i) for i in (grupo.get('nos') or []) if str(i) in caixas]


def nivel_de_aninhamento(grupos: list, indice: int, caixas: dict) -> int:
    meus = _visiveis(grupos[indice], caixas)
    if not meus:
        return 0
    nivel = 0
    for j, outro in enumerate(grupos):
        if j == indice:
            continue
        deles = set(_visiveis(outro, caixas))
        if not all(i in deles for i in meus):
            continue
        if len(deles) > len(meus) or (len(deles) == len(meus) and j < indice):
            nivel += 1
    return nivel


def caixa_do_grupo(grupo: dict, caixas: dict, nivel: int = 0):
    """Retorna {x, y, w, h} ou None. `caixas` = {id_do_bloco: {x, y, w, h}}."""
    ids = _visiveis(grupo, caixas)
    if not ids:
        return None
    pad = PAD_BASE + PAD_NIVEL * (nivel or 0)
    x0 = min(caixas[i]['x'] for i in ids)
    y0 = min(caixas[i]['y'] for i in ids)
    x1 = max(caixas[i]['x'] + caixas[i]['w'] for i in ids)
    y1 = max(caixas[i]['y'] + caixas[i]['h'] for i in ids)
    x, y = max(2, x0 - pad), max(2, y0 - pad - TITULO_H)
    return {'x': x, 'y': y, 'w': (x1 + pad) - x, 'h': (y1 + pad) - y}


def grupos_validos(topologia: dict) -> list:
    """Grupos bem formados da topologia (ignora entradas inválidas)."""
    saida = []
    for g in topologia.get('grupos') or []:
        if isinstance(g, dict) and isinstance(g.get('nos'), list) and g.get('nos'):
            saida.append(g)
    return saida
