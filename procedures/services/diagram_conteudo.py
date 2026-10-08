# -*- coding: utf-8 -*-
"""
Conteúdo dos blocos no PDF (espelho de static/procedures/js/diagrama/conteudo.js):
marcadores (prioridade, progresso, bandeira, estrela, pessoa), vagas e contagem de efetivo por ramo.
Um teste compara o catálogo e as contagens com a implementação em JavaScript.
"""

CORES = {
    'vermelho': '#ef4444', 'laranja': '#f59e0b', 'azul': '#3b82f6', 'roxo': '#8b5cf6',
    'verde': '#22c55e', 'ciano': '#06b6d4', 'cinza': '#94a3b8',
}
_CORES_DOS_GRUPOS = ('vermelho', 'laranja', 'azul', 'roxo', 'verde', 'cinza')
_NOMES = {'vermelho': 'vermelha', 'laranja': 'laranja', 'azul': 'azul', 'roxo': 'roxa', 'verde': 'verde', 'cinza': 'cinza'}


def _cor_prioridade(n):
    return CORES['vermelho' if n == 1 else 'laranja' if n == 2 else 'azul' if n == 3 else 'cinza']


GRUPOS = [
    {'id': 'prioridade', 'nome': 'Prioridade', 'itens': [
        {'id': f'prio-{n}', 'tipo': 'numero', 'valor': n, 'rotulo': f'Prioridade {n}', 'cor': _cor_prioridade(n)}
        for n in range(1, 8)]},
    {'id': 'progresso', 'nome': 'Progresso', 'itens': [
        {'id': f'prog-{p}', 'tipo': 'progresso', 'valor': p, 'rotulo': f'{p}% concluído', 'cor': CORES['verde']}
        for p in (0, 25, 50, 75, 100)]},
    {'id': 'bandeira', 'nome': 'Bandeira', 'itens': [
        {'id': f'band-{c}', 'tipo': 'bandeira', 'valor': c, 'rotulo': f'Bandeira {_NOMES[c]}', 'cor': CORES[c]}
        for c in _CORES_DOS_GRUPOS]},
    {'id': 'estrela', 'nome': 'Estrela', 'itens': [
        {'id': f'estr-{c}', 'tipo': 'estrela', 'valor': c, 'rotulo': f'Estrela {_NOMES[c]}', 'cor': CORES[c]}
        for c in _CORES_DOS_GRUPOS]},
    {'id': 'pessoa', 'nome': 'Pessoa', 'itens': [
        {'id': f'pess-{c}', 'tipo': 'pessoa', 'valor': c, 'rotulo': f'Pessoa {_NOMES[c]}', 'cor': CORES[c]}
        for c in _CORES_DOS_GRUPOS]},
]

POR_ID = {m['id']: m for g in GRUPOS for m in g['itens']}
ORDEM = [m['id'] for g in GRUPOS for m in g['itens']]

MAX_MARCADORES = 8
MAX_LINKS = 5
MAX_NOTA = 2000


def marcador_valido(marcador_id) -> bool:
    return isinstance(marcador_id, str) and marcador_id in POR_ID


def _dados(no: dict) -> dict:
    return no.get('data') if isinstance(no.get('data'), dict) else {}


def marcadores_em_uso(nos: list) -> list:
    usados = set()
    for n in nos:
        for m in _dados(n).get('markers') or []:
            if marcador_valido(m):
                usados.add(m)
    return [i for i in ORDEM if i in usados]


def eh_vaga(no: dict) -> bool:
    return _dados(no).get('vaga') is True


def eh_pessoa(no: dict) -> bool:
    return not eh_vaga(no) and bool(_dados(no).get('colab'))


def contagem_efetivo(nos: list, arvore: dict) -> dict:
    """{id: {'pessoas', 'vagas'}} na subárvore de cada bloco (inclui o próprio)."""
    por_id = {str(n['id']): n for n in nos}
    memo = {}

    def contar(no_id, pilha):
        if no_id in memo:
            return memo[no_id]
        no = por_id[no_id]
        total = {'pessoas': 1 if eh_pessoa(no) else 0, 'vagas': 1 if eh_vaga(no) else 0}
        if no_id in pilha:
            return total
        pilha.add(no_id)
        for f in arvore['filhos'].get(no_id, []):
            c = contar(f, pilha)
            total['pessoas'] += c['pessoas']
            total['vagas'] += c['vagas']
        pilha.discard(no_id)
        memo[no_id] = total
        return total

    return {no_id: dict(contar(no_id, set())) for no_id in por_id}


import math


def _ocupacao(c):
    quadro = c['pessoas'] + c['vagas']
    return None if quadro == 0 else math.floor(c['pessoas'] / quadro * 1000 + 0.5) / 10  # meio para cima, como Math.round


def resumo_por_ramo(nos: list, arvore: dict) -> dict:
    efetivo = contagem_efetivo(nos, arvore)
    por_id = {str(n['id']): n for n in nos}
    linhas = []
    raizes = [i for i in arvore['filhos'] if i not in arvore['pai']]
    for raiz in raizes:
        for f in arvore['filhos'][raiz]:
            dados = _dados(por_id[f])
            colab = dados.get('colab') if isinstance(dados.get('colab'), dict) else None
            nome = (colab.get('nome') or dados.get('label')) if colab else dados.get('label')
            c = efetivo[f]
            linhas.append({'id': f, 'nome': nome or f'Bloco {f}', 'pessoas': c['pessoas'], 'vagas': c['vagas'],
                           'total': c['pessoas'] + c['vagas'], 'ocupacao': _ocupacao(c)})
    total = {'pessoas': sum(efetivo[r]['pessoas'] for r in raizes), 'vagas': sum(efetivo[r]['vagas'] for r in raizes)}
    total['total'] = total['pessoas'] + total['vagas']
    total['ocupacao'] = _ocupacao(total)
    return {'linhas': linhas, 'total': total}
