"""Importação diária dos formulários: alimenta só os lançamentos (respostas) e avalia o que foi ou não preenchido.

Usa as planilhas em uso (uma por formulário) como fonte. Nunca mexe na estrutura (páginas, itens, tipos, vigência): só grava
respostas nas páginas que já existem. Por padrão reimporta uma janela recente (últimos dias) e atualiza valores que mudaram
na planilha; células vazias nunca apagam nada.

Depois de importar, `avaliar_periodo` mostra o cumprimento no período: por página, quantas verificações devidas foram feitas
e quais itens ficaram sem preenchimento.
"""
import datetime

from pcp import pendencias
from pcp.importacao_registros import importar_registros
from pcp.models import Turno

DIAS_JANELA_PADRAO = 14
MAX_PENDENCIAS_LISTADAS = 40


def desde_padrao(hoje=None):
    return (hoje or datetime.date.today()) - datetime.timedelta(days=DIAS_JANELA_PADRAO)


def avaliar_periodo(formulario, desde, hoje=None):
    """Cumprimento do formulário (revisão vigente) de `desde` até ontem: totais, páginas com pendência e itens em aberto.

    Só prazos já encerrados contam (o dia de hoje ainda está em andamento). Retorna None quando não há revisão vigente."""
    hoje = hoje or datetime.date.today()
    ontem = hoje - datetime.timedelta(days=1)
    if formulario is None or formulario.versao_vigente is None:
        return None
    turnos = list(Turno.objects.filter(ativo=True))
    d = pendencias.dashboard(desde, ontem, turnos, formulario_id=formulario.pk, hoje=hoje)
    bloco = next((b for b in d['blocos'] if b['formulario_id'] == formulario.pk), None)
    if bloco is None:
        return None
    paginas = [dict(l, grupo=g['nome']) for g in bloco['grupos'] for l in g['linhas'] if l['devidos']]
    itens = sorted((i for i in d['itens'] if i['codigo'] == formulario.codigo and i['atrasados']),
                   key=lambda i: (-i['atrasados'], i['pagina'], i['numero']))
    return {
        'desde': desde, 'ate': ontem, 'devidos': bloco['devidos'], 'feitos': bloco['feitos'],
        'pendentes': bloco['devidos'] - bloco['feitos'], 'pct': bloco['pct'],
        'paginas_com_pendencia': sorted((p for p in paginas if p['atrasados']), key=lambda p: (p['pct'], -p['atrasados'])),
        'paginas_completas': sum(1 for p in paginas if not p['atrasados']),
        'itens_pendentes': itens[:MAX_PENDENCIAS_LISTADAS], 'itens_pendentes_total': len(itens),
        'paradas': d['paradas'],
    }


def importar_diario(arquivo, nome_arquivo=None, ano=None, desde=None, atualizar=True, simular=False, hoje=None):
    """Importa os lançamentos de UMA planilha e devolve (resumo da importação, avaliação do período).

    `desde`: primeira data reimportada (padrão: DIAS_JANELA_PADRAO dias atrás; use datetime.date(ano, 1, 1) para o ano todo)."""
    hoje = hoje or datetime.date.today()
    desde = desde or desde_padrao(hoje)
    resumo = importar_registros(arquivo, nome_arquivo=nome_arquivo, ano=ano or hoje.year, simular=simular, hoje=hoje,
                                desde=desde, atualizar=atualizar)
    if simular:  # a simulação desfaz a gravação: avaliar agora mostraria o estado de antes, não o resultado
        return resumo, None
    return resumo, avaliar_periodo(resumo['versao'].formulario, desde, hoje)
