# -*- coding: utf-8 -*-
"""
Validação de schema da topologia (nodes/edges/grid_data) enviada pelo editor de diagramas.
Sem dependências externas: usada pelo endpoint de auto-save.
"""

MAX_NODES = 1000
MAX_EDGES = 3000


def _numero(valor):
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def validar_topologia(topologia: dict) -> list:
    """Retorna a lista de erros encontrados (vazia quando a topologia é válida)."""
    erros = []
    nodes = topologia.get('nodes')
    edges = topologia.get('edges')
    grid = topologia.get('grid_data', [])

    if not isinstance(nodes, list):
        return ["'nodes' deve ser uma lista."]
    if not isinstance(edges, list):
        return ["'edges' deve ser uma lista."]
    if not isinstance(grid, list):
        return ["'grid_data' deve ser uma lista."]
    if len(nodes) > MAX_NODES:
        return [f"Limite de {MAX_NODES} nós por diagrama excedido."]
    if len(edges) > MAX_EDGES:
        return [f"Limite de {MAX_EDGES} conexões por diagrama excedido."]

    ids_nos = set()
    for node in nodes:
        if not isinstance(node, dict) or 'id' not in node:
            erros.append("Cada nó deve ser um objeto com 'id'.")
            continue
        nid = str(node['id'])
        if nid in ids_nos:
            erros.append(f"ID de nó duplicado: {nid}")
        ids_nos.add(nid)
        pos = node.get('position')
        if not isinstance(pos, dict) or not (_numero(pos.get('x')) and _numero(pos.get('y'))):
            erros.append(f"Coordenadas x/y inválidas no nó {nid}.")
        if not isinstance(node.get('data', {}), dict):
            erros.append(f"Campo 'data' inválido no nó {nid}.")

    ids_arestas = set()
    for edge in edges:
        if not isinstance(edge, dict) or not all(k in edge for k in ('id', 'source', 'target')):
            erros.append("Cada aresta requer 'id', 'source' e 'target'.")
            continue
        eid = str(edge['id'])
        if eid in ids_arestas:
            erros.append(f"ID de aresta duplicado: {eid}")
        ids_arestas.add(eid)

    for linha in grid:
        if not isinstance(linha, dict):
            erros.append("Cada linha de 'grid_data' deve ser um objeto.")
            break

    return erros[:10]


def _rotulo_no(node: dict) -> str:
    return (node.get('data') or {}).get('label', '').strip() if isinstance(node.get('data'), dict) else ''


def validar_para_submissao(topologia: dict) -> list:
    """
    Regras de consistência exigidas antes de submeter o diagrama para aprovação.
    Retorna a lista de problemas (vazia quando está apto).

    As regras de fluxograma (Início/Fim, decisões) só valem quando o diagrama usa esses tipos de bloco;
    organogramas e mapas mentais não são obrigados a ter Início/Fim.
    """
    topologia = topologia or {}
    nodes = [n for n in (topologia.get('nodes') or []) if isinstance(n, dict) and 'id' in n]
    edges = [e for e in (topologia.get('edges') or []) if isinstance(e, dict)]
    problemas = []

    if not nodes:
        return ["O diagrama não possui blocos."]

    ids = {str(n['id']): n for n in nodes}
    saidas = {i: 0 for i in ids}
    entradas = {i: 0 for i in ids}

    for e in edges:
        origem, destino = str(e.get('source')), str(e.get('target'))
        if origem not in ids or destino not in ids:
            problemas.append(f"Conexão '{e.get('id')}' aponta para um bloco que não existe.")
            continue
        saidas[origem] += 1
        entradas[destino] += 1

    for i, n in ids.items():
        if not _rotulo_no(n):
            problemas.append(f"Bloco #{i} está sem texto.")

    eh_fluxograma = any(n.get('type') in ('start', 'end', 'decision') for n in nodes)
    if eh_fluxograma:
        if not any(n.get('type') == 'start' for n in nodes):
            problemas.append("O fluxograma precisa de um bloco de Início.")
        if not any(n.get('type') == 'end' for n in nodes):
            problemas.append("O fluxograma precisa de um bloco de Fim.")
        for i, n in ids.items():
            if n.get('type') == 'decision' and saidas[i] < 2:
                problemas.append(f"A decisão '{_rotulo_no(n) or i}' precisa de pelo menos 2 saídas (ex.: Sim / Não).")

    if len(nodes) > 1:
        for i, n in ids.items():
            if saidas[i] == 0 and entradas[i] == 0:
                problemas.append(f"O bloco '{_rotulo_no(n) or i}' está isolado (sem nenhuma conexão).")

    return problemas
