# -*- coding: utf-8 -*-
"""
Validação de schema da topologia (nodes/edges/grid_data) enviada pelo editor de diagramas.
Sem dependências externas: usada pelo endpoint de auto-save.
"""

MAX_NODES = 1000
MAX_EDGES = 3000
MAX_SUBTITULOS = 20
MAX_RAIAS = 100
MODOS_LAYOUT = ('raias', 'organograma', 'logico', 'arvore')
TIPOS_CONEXAO = ('hierarquia', 'relacao')


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

    if topologia.get('layout_modo') is not None and topologia['layout_modo'] not in MODOS_LAYOUT:
        return [f"'layout_modo' inválido. Use um destes: {', '.join(MODOS_LAYOUT)}."]
    versao_schema = topologia.get('schema_version')
    if versao_schema is not None and (isinstance(versao_schema, bool) or not isinstance(versao_schema, int)):
        return ["'schema_version' deve ser um número inteiro."]

    for chave in ('lanes', 'raias_fixas'):
        lista = topologia.get(chave)
        if lista is not None and (not isinstance(lista, list) or len(lista) > MAX_RAIAS
                                  or not all(isinstance(x, str) and 0 < len(x) <= 100 for x in lista)):
            return [f"'{chave}' deve ser uma lista de até {MAX_RAIAS} nomes de raia (até 100 caracteres)."]

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
        data = node.get('data', {})
        if not isinstance(data, dict):
            erros.append(f"Campo 'data' inválido no nó {nid}.")
        else:
            subs = data.get('subtitles')
            if subs is not None and (not isinstance(subs, list) or len(subs) > MAX_SUBTITULOS
                                     or not all(isinstance(t, str) and len(t) <= 300 for t in subs)):
                erros.append(f"Subtítulos inválidos no nó {nid} (máx. {MAX_SUBTITULOS}, até 300 caracteres cada).")
            if data.get('collapsed') is not None and not isinstance(data['collapsed'], bool):
                erros.append(f"Campo 'collapsed' inválido no nó {nid}.")
            colab = data.get('colab')
            if colab is not None and (not isinstance(colab, dict) or not isinstance(colab.get('id'), int)
                                      or isinstance(colab.get('id'), bool)):
                erros.append(f"Dados de colaborador inválidos no nó {nid}.")

    ids_arestas = set()
    for edge in edges:
        if not isinstance(edge, dict) or not all(k in edge for k in ('id', 'source', 'target')):
            erros.append("Cada aresta requer 'id', 'source' e 'target'.")
            continue
        if edge.get('kind') is not None and edge['kind'] not in TIPOS_CONEXAO:
            erros.append(f"Tipo de conexão inválido em '{edge.get('id')}' (use hierarquia ou relacao).")
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
