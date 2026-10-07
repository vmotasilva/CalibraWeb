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
