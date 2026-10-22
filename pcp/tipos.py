"""Ajuste do tipo dos itens a partir dos registros já lançados.

O importador de estrutura só DEDUZ o tipo de cada item pela especificação; os lançamentos reais mostram o que as pessoas de fato
preenchem. Esta rotina compara os dois e propõe a correção:

- item de lista em que quase tudo o que foi lançado é número  -> número;
- item de lista em que quase nada bate com as opções (nem com o vocabulário das listas) e não é número -> texto.
"""
import uuid
from collections import Counter, defaultdict

from django.db.models import Count
from django.utils import timezone

from pcp.importacao import RE_NUM, _chave
from pcp.models import AjusteCampo, Campo, ListaOpcoes, Resposta, ValorEquivalente

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


def aplicar_ajuste(formulario, campo, novo_tipo, usuario=None, lote=None, origem='tipo'):
    """Muda o tipo do item (e dos itens equivalentes nas revisões vigente e em rascunho) e zera a conformidade antiga,
    que tinha sido calculada pela lista. Devolve a quantidade de itens alterados."""
    paginas = formulario.paginas_equivalentes([campo.pagina.nome])
    alvo = Campo.objects.filter(pagina__in=paginas, item=campo.item, etapa=campo.etapa, descricao=campo.descricao)
    ids = list(alvo.values_list('pk', flat=True)) or [campo.pk]
    antes = {c.pk: snapshot(c) for c in Campo.objects.filter(pk__in=ids)}
    Campo.objects.filter(pk__in=ids).update(tipo=novo_tipo, lista=None)
    Resposta.objects.filter(campo_id__in=ids).update(conforme=None)
    _registrar(formulario, ids, antes, origem, lote, usuario)
    return len(ids)


# --------------------------------------------------------------------------------------
# Limites mínimo e máximo dos itens numéricos
# --------------------------------------------------------------------------------------
import re
from decimal import Decimal, InvalidOperation

from pcp.importacao import _dec, parse_faixa, parse_mais_menos

_NUM = r'(-?\d+(?:[.,]\d+)?)'
RE_MAIS_MENOS = re.compile(_NUM + r'\s*([^\d±+]{0,10}?)\s*(?:±|\+\s*/\s*-)\s*(\d+(?:[.,]\d+)?)')
RE_DESIGUALDADE_DUPLA = re.compile(_NUM + r'\s*(?:<=|<|≤)\s*[^<≤=\d]*?\s*(?:<=|<|≤)\s*' + _NUM)
RE_COLCHETES = re.compile(r'\[\s*' + _NUM + r'\s*[^\d\];,-]{0,6}[;,]\s*' + _NUM)
RE_FAIXA = re.compile(r'(?<![\w.,])' + _NUM + r'(?:\s*[-–]\s*|\s+(?:a|até)\s+)' + _NUM + r'(?!\d)', re.I)
RE_MAXIMO = re.compile(r'(?:até|<=|≤|<|m[aá]x(?:imo)?\.?)\s*:?\s*' + _NUM, re.I)
RE_MINIMO = re.compile(r'(?:>=|≥|>|m[ií]n(?:imo)?\.?)\s*:?\s*' + _NUM, re.I)
RE_UNIDADE = re.compile(r'\s*((?:°\s?[CF]|%|[A-Za-zµ/°³²]{1,8}))')
MIN_LANCAMENTOS_LIMITES = 10
COBERTURAS = [100, 99, 98, 95]


def _unidade_apos(texto, posicao):
    m = RE_UNIDADE.match(texto[posicao:])
    return m.group(1).strip() if m else ''


def limites_da_especificacao(texto):
    """(mínimo, máximo, unidade) lidos do texto da especificação; None se ela não traz limites numéricos claros.
    Aceita "10 - 27 °C", "45°C ± 2°C", "-0,8 < P < -0,6", "[25, 35]", "até 75 °C", "≥ 3" e variações no meio do texto."""
    texto = texto or ''
    r = parse_faixa(texto)  # faixa no início do texto
    if r:
        return r
    m = RE_MAIS_MENOS.search(texto)
    if m and _dec(m.group(1)) is not None and _dec(m.group(3)) is not None:
        alvo, tol = _dec(m.group(1)), _dec(m.group(3))
        return alvo - tol, alvo + tol, (m.group(2).strip() or _unidade_apos(texto, m.end()))[:20]
    for regex in (RE_DESIGUALDADE_DUPLA, RE_COLCHETES, RE_FAIXA):
        m = regex.search(texto)
        if m:
            a, b = _dec(m.group(1)), _dec(m.group(2))
            if a is not None and b is not None and a <= b:
                return a, b, _unidade_apos(texto, m.end())[:20]
    m = RE_MAXIMO.search(texto)
    if m and _dec(m.group(1)) is not None:
        return None, _dec(m.group(1)), _unidade_apos(texto, m.end())[:20]
    m = RE_MINIMO.search(texto)
    if m and _dec(m.group(1)) is not None:
        return _dec(m.group(1)), None, _unidade_apos(texto, m.end())[:20]
    return None


def _valor_na_posicao(pares, k):
    """Valor na posição k (0-based) de uma lista ordenada de (valor, quantidade)."""
    acumulado = 0
    for valor, n in pares:
        acumulado += n
        if k < acumulado:
            return valor
    return pares[-1][0]


def estatisticas(pares, cobertura):
    """Faixa observada, mediana e a faixa que cobre `cobertura`% dos lançamentos (corta as caudas em partes iguais)."""
    pares = sorted(pares)
    total = sum(n for _, n in pares)
    corte = int(total * (100 - cobertura) / 200)
    return {'total': total, 'obs_min': pares[0][0], 'obs_max': pares[-1][0], 'mediana': _valor_na_posicao(pares, total // 2),
            'faixa_min': _valor_na_posicao(pares, corte), 'faixa_max': _valor_na_posicao(pares, total - 1 - corte)}


def propor_limites(versao, cobertura=99):
    """Sugestões de mínimo/máximo para itens numéricos sem limites: da especificação quando ela os traz; senão do histórico."""
    pares = (Resposta.objects.filter(campo__pagina__versao=versao, campo__tipo=Campo.NUMERO,
                                     campo__minimo__isnull=True, campo__maximo__isnull=True)
             .exclude(valor='').values('campo_id', 'valor').annotate(n=Count('id')))
    por_campo = defaultdict(list)
    for p in pares:
        d = _dec(p['valor'])
        if d is not None:
            por_campo[p['campo_id']].append((d, p['n']))
    campos = {c.pk: c for c in Campo.objects.filter(pk__in=por_campo).select_related('pagina')}
    propostas = []
    for pk, valores in por_campo.items():
        campo = campos[pk]
        total = sum(n for _, n in valores)
        if total < MIN_LANCAMENTOS_LIMITES:
            continue
        est = estatisticas(valores, cobertura)
        spec = limites_da_especificacao(campo.especificacao)
        if spec and (spec[0] is not None or spec[1] is not None):
            minimo, maximo, unidade, fonte = spec[0], spec[1], spec[2] or campo.unidade, 'especificação'
            if minimo is None or maximo is None:  # a especificação só dá um lado: o outro vem do histórico
                if minimo is None and est['faixa_min'] < maximo:
                    minimo, fonte = est['faixa_min'], 'especificação + histórico'
                elif maximo is None and est['faixa_max'] > minimo:
                    maximo, fonte = est['faixa_max'], 'especificação + histórico'
        elif est['faixa_min'] < est['faixa_max']:
            minimo, maximo, unidade, fonte = est['faixa_min'], est['faixa_max'], campo.unidade, 'histórico'
        else:
            continue  # sem variação: não há faixa a sugerir
        dentro = sum(n for v, n in valores if (minimo is None or v >= minimo) and (maximo is None or v <= maximo))
        propostas.append({
            'campo': campo, 'pagina': campo.pagina, 'minimo': minimo, 'maximo': maximo, 'unidade': unidade, 'fonte': fonte,
            'pct_dentro': round(100 * dentro / total), 'total': total, **est})
    propostas.sort(key=lambda p: (p['pagina'].ordem, p['pagina'].nome, p['campo'].ordem))
    return propostas


def aplicar_limites(formulario, campo, minimo, maximo, unidade='', usuario=None, lote=None):
    """Grava os limites no item e nos equivalentes (revisões vigente/rascunho) e recalcula a conformidade dos lançamentos."""
    paginas = formulario.paginas_equivalentes([campo.pagina.nome])
    alvo = Campo.objects.filter(pagina__in=paginas, item=campo.item, etapa=campo.etapa, descricao=campo.descricao)
    ids = list(alvo.values_list('pk', flat=True)) or [campo.pk]
    antes = {c.pk: snapshot(c) for c in Campo.objects.filter(pk__in=ids)}
    dados = {'minimo': minimo, 'maximo': maximo}
    if unidade and not campo.unidade:
        dados['unidade'] = unidade[:20]
    Campo.objects.filter(pk__in=ids).update(**dados)
    for k, v in dados.items():
        setattr(campo, k, v)
    _registrar(formulario, ids, antes, 'limites', lote, usuario)
    for valor in set(Resposta.objects.filter(campo_id__in=ids).values_list('valor', flat=True)):
        Resposta.objects.filter(campo_id__in=ids, valor=valor).update(conforme=campo.avaliar(valor))
    return Resposta.objects.filter(campo_id__in=ids, conforme=False).count()


# --------------------------------------------------------------------------------------
# Histórico e desfazer
# --------------------------------------------------------------------------------------

def _num(x):
    """Decimal em texto canônico ('10.0000' e '10' -> '10'), para comparar estados."""
    return None if x is None else format(Decimal(x).normalize(), 'f')


def snapshot(campo):
    """Estado do item que os ajustes podem alterar."""
    return {'tipo': campo.tipo, 'lista': campo.lista_id, 'minimo': _num(campo.minimo), 'maximo': _num(campo.maximo), 'unidade': campo.unidade or ''}


def novo_lote():
    return uuid.uuid4().hex[:16]


def _registrar(formulario, ids, antes, origem, lote, usuario):
    for campo in Campo.objects.filter(pk__in=ids):
        depois = snapshot(campo)
        if depois != antes.get(campo.pk):
            AjusteCampo.objects.create(formulario=formulario, campo=campo, origem=origem, lote=lote or novo_lote(),
                                       antes=antes[campo.pk], depois=depois, criado_por=usuario)


def recalcular_conformidade(campo):
    """Recalcula a conformidade dos lançamentos do item pelo tipo atual (lista: própria lista, vínculos e vocabulário das listas)."""
    valores = set(Resposta.objects.filter(campo=campo).values_list('valor', flat=True))
    if campo.tipo == Campo.LISTA and campo.lista_id:
        propria = {o.valor: o.conforme for o in campo.lista.opcoes.all()}
        vinculos = {v.chave: v.opcao.conforme for v in ValorEquivalente.objects.filter(lista_id=campo.lista_id).select_related('opcao')}
        vocabulario = {}
        for l in ListaOpcoes.objects.prefetch_related('opcoes'):
            for o in l.opcoes.all():
                vocabulario.setdefault(_chave(o.valor), o.conforme)

        def conforme(valor):
            if valor in propria:
                return propria[valor]
            k = _chave(valor)
            return vinculos.get(k, vocabulario.get(k))
    elif campo.tipo == Campo.NUMERO:
        conforme = campo.avaliar
    else:
        def conforme(valor):
            return None
    for valor in valores:
        Resposta.objects.filter(campo=campo, valor=valor).update(conforme=conforme(valor))


def desfazer(ajuste, usuario=None):
    """Volta o item ao estado anterior ao ajuste. Retorna 'ok', 'ja' (já desfeito) ou 'alterado' (o item mudou depois do ajuste)."""
    if ajuste.desfeito:
        return 'ja'
    campo = Campo.objects.get(pk=ajuste.campo_id)
    if snapshot(campo) != ajuste.depois:
        return 'alterado'
    a = ajuste.antes
    Campo.objects.filter(pk=campo.pk).update(
        tipo=a['tipo'], lista_id=a['lista'], minimo=a['minimo'], maximo=a['maximo'], unidade=a['unidade'])
    campo.refresh_from_db()
    recalcular_conformidade(campo)
    ajuste.desfeito_em, ajuste.desfeito_por = timezone.now(), usuario
    ajuste.save(update_fields=['desfeito_em', 'desfeito_por'])
    return 'ok'
