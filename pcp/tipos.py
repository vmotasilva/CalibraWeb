"""Ajuste do tipo dos itens a partir dos registros já lançados.

O importador de estrutura só DEDUZ o tipo de cada item pela especificação; os lançamentos reais mostram o que as pessoas de fato
preenchem. Esta rotina compara os dois e propõe a correção:

- item de lista em que quase tudo o que foi lançado é número  -> número;
- item de lista em que quase nada bate com as opções (nem com o vocabulário das listas) e não é número -> texto.
"""
from collections import Counter, defaultdict

from django.db.models import Count

from pcp.importacao import RE_NUM, _chave
from pcp.models import Campo, ListaOpcoes, Resposta

MIN_LANCAMENTOS = 5
LIMIAR = 0.8


def propor_ajustes(versao):
    """[{campo, pagina, novo_tipo, total, pct_numerico, pct_reconhecido, exemplos}] dos itens da revisão que merecem ajuste."""
    vocabulario = {_chave(o.valor) for l in ListaOpcoes.objects.prefetch_related('opcoes') for o in l.opcoes.all()}
    pares = (Resposta.objects.filter(campo__pagina__versao=versao, campo__tipo=Campo.LISTA).exclude(valor='')
             .values('campo_id', 'valor').annotate(n=Count('id')))
    por_campo = defaultdict(list)
    for p in pares:
        por_campo[p['campo_id']].append((p['valor'], p['n']))
    campos = {c.pk: c for c in Campo.objects.filter(pk__in=por_campo).select_related('pagina', 'lista')}
    propostas = []
    for pk, valores in por_campo.items():
        campo = campos[pk]
        total = sum(n for _, n in valores)
        if total < MIN_LANCAMENTOS:
            continue
        numericos = sum(n for v, n in valores if RE_NUM.match(v))
        reconhecidos = sum(n for v, n in valores if _chave(v) in vocabulario)
        pct_num, pct_rec = numericos / total, reconhecidos / total
        if pct_num >= LIMIAR:
            novo = Campo.NUMERO
        elif pct_rec <= 1 - LIMIAR and pct_num < 0.5:
            novo = Campo.TEXTO
        else:
            continue
        exemplos = [v for v, _ in sorted(valores, key=lambda x: -x[1])[:4]]
        propostas.append({'campo': campo, 'pagina': campo.pagina, 'novo_tipo': novo, 'novo_tipo_nome': dict(Campo.TIPOS)[novo],
                          'total': total, 'pct_numerico': round(100 * pct_num), 'pct_reconhecido': round(100 * pct_rec),
                          'exemplos': exemplos})
    propostas.sort(key=lambda p: (p['pagina'].ordem, p['pagina'].nome, p['campo'].ordem))
    return propostas


def aplicar_ajuste(formulario, campo, novo_tipo):
    """Muda o tipo do item (e dos itens equivalentes nas revisões vigente e em rascunho) e zera a conformidade antiga,
    que tinha sido calculada pela lista. Devolve a quantidade de itens alterados."""
    paginas = formulario.paginas_equivalentes([campo.pagina.nome])
    alvo = Campo.objects.filter(pagina__in=paginas, item=campo.item, etapa=campo.etapa, descricao=campo.descricao)
    ids = list(alvo.values_list('pk', flat=True)) or [campo.pk]
    Campo.objects.filter(pk__in=ids).update(tipo=novo_tipo, lista=None)
    Resposta.objects.filter(campo_id__in=ids).update(conforme=None)
    return len(ids)
