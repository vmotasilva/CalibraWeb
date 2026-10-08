# -*- coding: utf-8 -*-
"""Comparação entre duas revisões (topologias) de um diagrama."""

CAMPOS_NO = (('label', 'Texto'), ('lane', 'Raia'), ('type', 'Tipo'), ('documentRef', 'Documento'))


def _no_info(node: dict) -> dict:
    data = node.get('data') if isinstance(node.get('data'), dict) else {}
    return {
        'id': str(node.get('id')),
        'type': node.get('type') or 'process',
        'label': (data.get('label') or '').strip(),
        'lane': data.get('lane') or 'Geral',
        'documentRef': data.get('documentRef') or '',
        'tags': ', '.join(str(t) for t in (data.get('customTags') or [])),
    }


def _nome(info: dict) -> str:
    return info['label'] or f"Bloco #{info['id']}"


def comparar_topologias(antiga: dict, nova: dict) -> dict:
    """Retorna blocos/conexões adicionados, removidos e alterados entre a revisão antiga e a nova."""
    antiga, nova = antiga or {}, nova or {}
    nos_a = {str(n['id']): _no_info(n) for n in antiga.get('nodes') or [] if isinstance(n, dict) and 'id' in n}
    nos_b = {str(n['id']): _no_info(n) for n in nova.get('nodes') or [] if isinstance(n, dict) and 'id' in n}

    adicionados = [nos_b[i] for i in nos_b if i not in nos_a]
    removidos = [nos_a[i] for i in nos_a if i not in nos_b]

    alterados = []
    for i, b in nos_b.items():
        a = nos_a.get(i)
        if not a:
            continue
        mudancas = []
        for campo, rotulo in CAMPOS_NO + (('tags', 'Marcadores'),):
            if a.get(campo, '') != b.get(campo, ''):
                mudancas.append({'campo': rotulo, 'de': a.get(campo) or '(vazio)', 'para': b.get(campo) or '(vazio)'})
        if mudancas:
            alterados.append({'id': i, 'nome': _nome(b), 'mudancas': mudancas})

    def chaves(topo, nos):
        resultado = {}
        for e in topo.get('edges') or []:
            if isinstance(e, dict) and 'source' in e and 'target' in e:
                resultado[(str(e['source']), str(e['target']))] = (e.get('label') or '').strip()
        return resultado

    ed_a, ed_b = chaves(antiga, nos_a), chaves(nova, nos_b)

    def descricao(par, nos_ref_a, nos_ref_b):
        origem = (nos_ref_b.get(par[0]) or nos_ref_a.get(par[0]) or {'label': '', 'id': par[0]})
        destino = (nos_ref_b.get(par[1]) or nos_ref_a.get(par[1]) or {'label': '', 'id': par[1]})
        return f"{_nome(origem)} → {_nome(destino)}"

    conexoes_adicionadas = [{'texto': descricao(p, nos_a, nos_b), 'rotulo': ed_b[p]} for p in ed_b if p not in ed_a]
    conexoes_removidas = [{'texto': descricao(p, nos_a, nos_b), 'rotulo': ed_a[p]} for p in ed_a if p not in ed_b]
    conexoes_alteradas = [
        {'texto': descricao(p, nos_a, nos_b), 'de': ed_a[p] or '(sem rótulo)', 'para': ed_b[p] or '(sem rótulo)'}
        for p in ed_b if p in ed_a and ed_a[p] != ed_b[p]
    ]

    for lista in (adicionados, removidos):
        for info in lista:
            info['nome'] = _nome(info)

    total = (len(adicionados) + len(removidos) + len(alterados) +
             len(conexoes_adicionadas) + len(conexoes_removidas) + len(conexoes_alteradas))
    return {
        'blocos_adicionados': adicionados,
        'blocos_removidos': removidos,
        'blocos_alterados': alterados,
        'conexoes_adicionadas': conexoes_adicionadas,
        'conexoes_removidas': conexoes_removidas,
        'conexoes_alteradas': conexoes_alteradas,
        'total_mudancas': total,
        'sem_mudancas': total == 0,
    }
