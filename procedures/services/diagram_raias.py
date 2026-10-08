# -*- coding: utf-8 -*-
"""
Regras de Raias (swimlanes) dos diagramas.

A ordem das raias é explícita na topologia:
  - `lanes`:        lista ordenada com os nomes das raias;
  - `raias_fixas`:  raias criadas sem nenhum bloco (continuam visíveis enquanto vazias).
Uma raia aparece se tiver blocos ou estiver em `raias_fixas`. Diagramas antigos (sem `lanes`)
usam a ordem de primeira aparição dos blocos, como o editor sempre fez.
"""

from ..models_diagram import Diagrama, DiagramaVersao, StatusDiagrama


def _nome_raia(valor) -> str:
    return (valor or 'Geral') if isinstance(valor, str) or valor is None else str(valor)


def raias_usadas(topologia: dict) -> list:
    """Raias referenciadas por blocos e linhas da grelha, na ordem de aparição."""
    usadas = []
    for n in topologia.get('nodes') or []:
        data = n.get('data') if isinstance(n, dict) and isinstance(n.get('data'), dict) else {}
        usadas.append(_nome_raia(data.get('lane')))
    for r in topologia.get('grid_data') or []:
        if isinstance(r, dict):
            usadas.append(_nome_raia(r.get('lane')))
    return [u for u in usadas if u]


def raias_do_diagrama(topologia: dict) -> list:
    """Lista ordenada das raias exibidas (mesma regra do editor)."""
    topologia = topologia or {}
    usadas = raias_usadas(topologia)
    visiveis = set(usadas) | {str(f) for f in (topologia.get('raias_fixas') or [])}
    lista = []
    for nome in topologia.get('lanes') or []:
        if nome in visiveis and nome not in lista:
            lista.append(nome)
    for nome in usadas:
        if nome not in lista:
            lista.append(nome)
    for nome in topologia.get('raias_fixas') or []:
        if nome not in lista:
            lista.append(nome)
    return lista or ['Geral']


def renomear_raia_na_topologia(topologia: dict, antigo: str, novo: str) -> bool:
    """Renomeia a raia dentro de uma topologia. Retorna True se algo mudou."""
    mudou = False

    def eh_antigo(valor):
        return _nome_raia(valor) == antigo

    for n in topologia.get('nodes') or []:
        if isinstance(n, dict) and isinstance(n.get('data'), dict) and eh_antigo(n['data'].get('lane')):
            n['data']['lane'] = novo
            mudou = True
    for r in topologia.get('grid_data') or []:
        if isinstance(r, dict) and eh_antigo(r.get('lane')):
            r['lane'] = novo
            mudou = True
    for chave in ('lanes', 'raias_fixas'):
        lista = topologia.get(chave)
        if isinstance(lista, list) and antigo in lista:
            topologia[chave] = [novo if x == antigo else x for x in lista]
            # evita duplicata quando a raia de destino já existia
            vistos, unica = set(), []
            for x in topologia[chave]:
                if x not in vistos:
                    vistos.add(x)
                    unica.append(x)
            topologia[chave] = unica
            mudou = True
    return mudou


def renomear_raia_em_rascunhos(antigo: str, novo: str) -> int:
    """Renomeia a raia em todas as revisões em Rascunho (revisões aprovadas permanecem imutáveis)."""
    alteradas = 0
    for versao in DiagramaVersao.objects.filter(status=StatusDiagrama.RASCUNHO):
        if renomear_raia_na_topologia(versao.dados_topologia, antigo, novo):
            versao.save(update_fields=['dados_topologia', 'atualizado_em'])
            alteradas += 1
    return alteradas


def uso_das_raias() -> dict:
    """
    {nome_em_minusculas: [ {raia, diagrama_id, identificador, titulo, versao_id, revisao, status}, ... ]}
    considerando a última revisão de cada diagrama ativo.
    """
    uso = {}
    for diagrama in Diagrama.objects.filter(ativo=True).prefetch_related('versoes').order_by('numero'):
        versoes = sorted(diagrama.versoes.all(), key=lambda v: -v.revisao)
        if not versoes:
            continue
        ultima = versoes[0]
        for nome in raias_do_diagrama(ultima.dados_topologia):
            uso.setdefault(nome.lower(), []).append({
                'raia': nome,
                'diagrama_id': str(diagrama.id),
                'identificador': diagrama.identificador,
                'titulo': diagrama.titulo,
                'versao_id': str(ultima.id),
                'revisao': ultima.revisao,
                'status': ultima.get_status_display(),
            })
    return uso
