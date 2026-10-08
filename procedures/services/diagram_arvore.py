# -*- coding: utf-8 -*-
"""
Hierarquia do diagrama (espelho de static/procedures/js/diagrama/layout_arvore.js).
A árvore é formada pelas conexões com kind "hierarquia" (padrão); "relacao" são ligações livres.
Cada bloco tem no máximo um pai (a primeira conexão vence) e ciclos são ignorados.
"""

MODOS_ARVORE = ('organograma', 'logico', 'arvore')


def eh_hierarquia(aresta: dict) -> bool:
    return (aresta.get('kind') or 'hierarquia') == 'hierarquia'


def montar_arvore(nos: list, arestas: list) -> dict:
    ids = {str(n['id']) for n in nos if isinstance(n, dict) and 'id' in n}
    filhos = {i: [] for i in ids}
    pai = {}

    def eh_ancestral(candidato, no):
        atual, vistos = no, set()
        while atual is not None and atual not in vistos:
            if atual == candidato:
                return True
            vistos.add(atual)
            atual = pai.get(atual)
        return False

    for a in arestas:
        if not isinstance(a, dict) or not eh_hierarquia(a):
            continue
        origem, destino = str(a.get('source')), str(a.get('target'))
        if origem not in ids or destino not in ids or origem == destino or destino in pai:
            continue
        if eh_ancestral(destino, origem):
            continue
        pai[destino] = origem
        filhos[origem].append(destino)
    return {'filhos': filhos, 'pai': pai}


def descendentes(arvore: dict, no_id: str) -> set:
    resultado, pilha = set(), list(arvore['filhos'].get(no_id, []))
    while pilha:
        atual = pilha.pop()
        if atual in resultado:
            continue
        resultado.add(atual)
        pilha.extend(arvore['filhos'].get(atual, []))
    return resultado


def ramos_recolhidos(nos: list, arestas: list):
    """Retorna (ocultos, contagem): blocos escondidos por um ancestral recolhido e {id_recolhido: quantidade}."""
    arvore = montar_arvore(nos, arestas)
    ocultos, contagem = set(), {}
    for n in nos:
        dados = n.get('data') if isinstance(n.get('data'), dict) else {}
        if dados.get('collapsed'):
            desc = descendentes(arvore, str(n['id']))
            if desc:
                contagem[str(n['id'])] = len(desc)
                ocultos |= desc
    return ocultos, contagem
