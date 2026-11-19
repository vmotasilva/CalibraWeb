# -*- coding: utf-8 -*-
"""
Comparação de cotações de fornecedores.

- comparar_versoes(nova, anterior): o que mudou entre uma cotação obsoleta e a nova versão
  (valores por instrumento, custos adicionais, prazo e total).
- comparar_fornecedores(solicitacao): matriz instrumento x cotações ativas, com o menor preço
  em destaque.

Os dois devolvem "alertas": observações automáticas com a pergunta que vale fazer ao
fornecedor, para que a negociação parta dos questionamentos certos.
"""
from collections import defaultdict
from decimal import Decimal

ZERO = Decimal('0.00')
LIMITE_VARIACAO_ITEM = Decimal('0.10')        # 10% de variação por instrumento
LIMITE_DIFERENCA_FORNECEDORES = Decimal('0.15')  # 15% entre a proposta mais cara e a mais barata
LIMITE_CUSTOS_ADICIONAIS = Decimal('0.15')    # custos adicionais acima de 15% do total
DISPERSAO_REAJUSTE = Decimal('0.05')          # reajustes não uniformes (5 p.p. de diferença)


def brl(valor):
    """1234.5 -> 'R$ 1.234,50'."""
    texto = f"{Decimal(valor or 0):,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(valor):
    """Decimal(0.1234) -> '+12,3%'."""
    return f"{valor * 100:+.1f}%".replace(".", ",")


def _variacao(antes, depois):
    antes, depois = Decimal(antes or 0), Decimal(depois or 0)
    if antes == 0:
        return None
    return (depois - antes) / antes


def _alerta(nivel, texto, pergunta=''):
    return {'nivel': nivel, 'texto': texto, 'pergunta': pergunta}


def _itens(cotacao):
    """{instrumento_id: item} dos itens da cotação."""
    return {i.instrumento_id: i for i in cotacao.itens.select_related('instrumento')}


def _custos_por_tipo(cotacao):
    por_tipo = defaultdict(lambda: ZERO)
    rotulos = {}
    for c in cotacao.custos_adicionais.all():
        por_tipo[c.tipo] += c.valor_total
        rotulos[c.tipo] = c.get_tipo_display()
    return por_tipo, rotulos


def _atende(item):
    return bool(item) and item.pode_atender and item.valor_unitario and item.valor_unitario > 0


def _alerta_precos_inconsistentes(itens, prefixo=''):
    """Instrumentos de mesma descrição cotados com valores unitários diferentes."""
    grupos = defaultdict(list)
    for item in itens:
        if _atende(item):
            grupos[(item.instrumento.descricao or '').strip().lower()].append(item)
    alertas = []
    for itens_iguais in grupos.values():
        valores = {i.valor_unitario for i in itens_iguais}
        if len(itens_iguais) > 1 and len(valores) > 1:
            lista = ", ".join(f"{i.instrumento.tag} {brl(i.valor_unitario)}" for i in itens_iguais)
            alertas.append(_alerta(
                'warning',
                f"{prefixo}Instrumentos iguais ({itens_iguais[0].instrumento.descricao}) com valores diferentes: {lista}.",
                "Por que instrumentos iguais têm preços distintos? Existe diferença de faixa, pontos ou prazo?"))
    return alertas


def comparar_versoes(nova, anterior):
    """Compara a nova versão com a cotação obsoleta que ela substitui."""
    itens_ant, itens_nov = _itens(anterior), _itens(nova)
    ids = sorted(set(itens_ant) | set(itens_nov),
                 key=lambda i: (itens_nov.get(i) or itens_ant.get(i)).instrumento.tag)
    linhas, variacoes = [], []
    removidos, adicionados, deixaram_atender = [], [], []
    for i in ids:
        a, n = itens_ant.get(i), itens_nov.get(i)
        tag = (n or a).instrumento.tag
        v_ant = a.valor_total if a else None
        v_nov = n.valor_total if n else None
        var = _variacao(v_ant, v_nov) if (a and n) else None
        if a and n and var is not None:
            variacoes.append((tag, var, v_ant, v_nov))
        if a and not n:
            removidos.append(tag)
        elif n and not a:
            adicionados.append(tag)
        elif _atende(a) and not _atende(n):
            deixaram_atender.append(tag)
        linhas.append({
            'tag': tag, 'anterior': v_ant, 'nova': v_nov,
            'delta': (v_nov - v_ant) if (a and n) else None, 'variacao': var,
            'unit_anterior': a.valor_unitario if a else None, 'unit_nova': n.valor_unitario if n else None,
            'destaque': bool(var is not None and abs(var) > LIMITE_VARIACAO_ITEM),
        })

    serv_ant, serv_nov = anterior.get_valor_servicos(), nova.get_valor_servicos()
    cust_ant, cust_nov = anterior.get_valor_custos_adicionais(), nova.get_valor_custos_adicionais()
    tot_ant, tot_nov = serv_ant + cust_ant, serv_nov + cust_nov
    var_total = _variacao(tot_ant, tot_nov)

    # custos adicionais por tipo
    c_ant, rot_ant = _custos_por_tipo(anterior)
    c_nov, rot_nov = _custos_por_tipo(nova)
    linhas_custos = []
    for tipo in sorted(set(c_ant) | set(c_nov)):
        rotulo = rot_nov.get(tipo) or rot_ant.get(tipo)
        linhas_custos.append({'rotulo': rotulo, 'anterior': c_ant.get(tipo, ZERO), 'nova': c_nov.get(tipo, ZERO),
                              'delta': c_nov.get(tipo, ZERO) - c_ant.get(tipo, ZERO)})

    alertas = []
    if var_total is not None:
        if var_total > 0:
            alertas.append(_alerta(
                'warning', f"O valor total subiu {pct(var_total)} ({brl(tot_ant)} → {brl(tot_nov)}).",
                "Qual a justificativa do reajuste? Mudou o escopo, os pontos de calibração ou o prazo?"))
        elif var_total < 0:
            alertas.append(_alerta(
                'info', f"O valor total caiu {pct(var_total)} ({brl(tot_ant)} → {brl(tot_nov)}).",
                "O escopo foi mantido (mesmos instrumentos, pontos e prazo)? A redução vem de negociação ou de itens removidos?"))
        elif not removidos and not adicionados and not any(l['delta'] for l in linhas_custos):
            alertas.append(_alerta(
                'info', "A nova versão tem o mesmo valor total da anterior.",
                "Se a cotação foi refeita sem alterar valores, o que mudou (escopo, prazo, validade)?"))

    for tag, var, v_ant, v_nov in variacoes:
        if abs(var) > LIMITE_VARIACAO_ITEM:
            alertas.append(_alerta(
                'warning', f"{tag}: {pct(var)} ({brl(v_ant)} → {brl(v_nov)}).",
                f"Por que {tag} variou {'mais' if var > 0 else 'diferente'} do conjunto? O que justifica essa diferença?"))
    if len(variacoes) > 1:
        valores = [v for _t, v, _a, _n in variacoes]
        if max(valores) - min(valores) > DISPERSAO_REAJUSTE:
            alertas.append(_alerta(
                'warning', f"Os reajustes não são uniformes entre os instrumentos ({pct(min(valores))} a {pct(max(valores))}).",
                "Qual o critério de reajuste usado por item? Instrumentos semelhantes deveriam variar de forma parecida."))
    if removidos or deixaram_atender:
        tags = ", ".join(removidos + deixaram_atender)
        alertas.append(_alerta(
            'danger', f"Deixaram de ser cotados/atendidos: {tags}.",
            "Por que esses instrumentos saíram da proposta? O total ficou menor só por causa disso?"))
    if adicionados:
        alertas.append(_alerta('info', f"Instrumentos novos na versão: {', '.join(adicionados)}.", ''))

    for l in linhas_custos:
        if l['delta'] > 0:
            novo = "novo" if l['anterior'] == 0 else f"{brl(l['anterior'])} → {brl(l['nova'])}"
            alertas.append(_alerta(
                'warning', f"Custo adicional de {l['rotulo'].lower()}: {novo}.",
                f"O custo de {l['rotulo'].lower()} é negociável? Há alternativa mais econômica?"))
        elif l['delta'] < 0:
            alertas.append(_alerta('info', f"Custo adicional de {l['rotulo'].lower()} reduzido ({brl(l['anterior'])} → {brl(l['nova'])}).", ''))
    if tot_nov > 0 and cust_nov / tot_nov > LIMITE_CUSTOS_ADICIONAIS:
        alertas.append(_alerta(
            'warning', f"Os custos adicionais são {cust_nov / tot_nov * 100:.0f}% do total ({brl(cust_nov)}).",
            "Dá para reduzi-los (agrupar instrumentos, enviar ao laboratório, outro modal de transporte)?"))

    prazos_ant = [i.prazo_dias for i in itens_ant.values() if i.prazo_dias]
    prazos_nov = [i.prazo_dias for i in itens_nov.values() if i.prazo_dias]
    if prazos_ant and prazos_nov and max(prazos_nov) > max(prazos_ant):
        alertas.append(_alerta(
            'warning', f"O prazo aumentou de {max(prazos_ant)} para {max(prazos_nov)} dias.",
            "Por que o prazo aumentou? O valor menor, se houver, compensa o atraso?"))
    alertas += _alerta_precos_inconsistentes(list(itens_nov.values()))

    return {
        'linhas': linhas, 'linhas_custos': linhas_custos, 'alertas': alertas,
        'totais': {'servicos_ant': serv_ant, 'servicos_nov': serv_nov, 'custos_ant': cust_ant, 'custos_nov': cust_nov,
                   'total_ant': tot_ant, 'total_nov': tot_nov, 'delta': tot_nov - tot_ant, 'variacao': var_total},
    }


def comparar_fornecedores(solicitacao):
    """Matriz instrumento x cotações ativas com valores preenchidos (None se há menos de 2)."""
    cotacoes = [c for c in solicitacao.cotacoes_fornecedores.filter(ativa=True)
                .select_related('fornecedor').prefetch_related('itens__instrumento', 'custos_adicionais')
                if c.get_valor_servicos() > 0]
    if len(cotacoes) < 2:
        return None
    por_cotacao = {c.id: _itens(c) for c in cotacoes}
    instrumentos = {}
    for itens in por_cotacao.values():
        for iid, item in itens.items():
            instrumentos[iid] = item.instrumento
    ordem = sorted(instrumentos, key=lambda i: instrumentos[i].tag)

    linhas, menores = [], defaultdict(list)
    sem_cobertura = defaultdict(list)
    for iid in ordem:
        celulas, validos = [], {}
        for c in cotacoes:
            item = por_cotacao[c.id].get(iid)
            if _atende(item):
                validos[c.id] = item.valor_total
                celulas.append({'cotacao': c, 'valor': item.valor_total, 'prazo': item.prazo_dias})
            else:
                celulas.append({'cotacao': c, 'valor': None, 'prazo': None})
                sem_cobertura[c.id].append(instrumentos[iid].tag)
        menor = min(validos.values()) if validos else None
        for cel in celulas:
            cel['menor'] = menor is not None and cel['valor'] == menor and len(validos) > 1
            if cel['menor']:
                menores[cel['cotacao'].id].append(instrumentos[iid].tag)
        linhas.append({'tag': instrumentos[iid].tag, 'descricao': instrumentos[iid].descricao, 'celulas': celulas})

    totais = []
    for c in cotacoes:
        serv, cust = c.get_valor_servicos(), c.get_valor_custos_adicionais()
        totais.append({'cotacao': c, 'servicos': serv, 'custos': cust, 'total': serv + cust,
                       'completa': not sem_cobertura.get(c.id)})
    # propostas incompletas não são comparáveis: o "menor total" só vale entre as completas
    base = [t for t in totais if t['completa']] or totais
    menor_total = min(t['total'] for t in base)
    for t in totais:
        t['menor'] = t in base and t['total'] == menor_total and len(base) > 1
        t['acima'] = _variacao(menor_total, t['total']) if t in base else None

    alertas = []
    mais_cara = max(base, key=lambda t: t['total'])
    mais_barata = min(base, key=lambda t: t['total'])
    dif = _variacao(mais_barata['total'], mais_cara['total']) if len(base) > 1 else None
    if dif is not None and dif > LIMITE_DIFERENCA_FORNECEDORES:
        alertas.append(_alerta(
            'warning',
            f"{mais_cara['cotacao'].fornecedor.empresa} está {pct(dif)} acima de {mais_barata['cotacao'].fornecedor.empresa} "
            f"({brl(mais_cara['total'])} × {brl(mais_barata['total'])}).",
            "O escopo (pontos, faixas, prazo) é equivalente? Vale pedir revisão ou negociar com o mais caro?"))
    for t in totais:
        c = t['cotacao']
        faltam = sem_cobertura.get(c.id)
        if faltam:
            alertas.append(_alerta(
                'danger', f"{c.fornecedor.empresa} não cotou/atende: {', '.join(faltam)}. Os totais não são comparáveis.",
                f"{c.fornecedor.empresa} consegue atender esses instrumentos? Sem isso a comparação de totais é injusta."))
        if t['total'] > 0 and t['custos'] / t['total'] > LIMITE_CUSTOS_ADICIONAIS:
            alertas.append(_alerta(
                'warning', f"{c.fornecedor.empresa}: custos adicionais são {t['custos'] / t['total'] * 100:.0f}% do total ({brl(t['custos'])}).",
                "Esses custos são negociáveis? Compare com enviar os instrumentos ao laboratório."))
        alertas += _alerta_precos_inconsistentes(list(por_cotacao[c.id].values()), prefixo=f"{c.fornecedor.empresa}: ")
    donos = {cid: tags for cid, tags in menores.items() if tags}
    if len(donos) > 1:
        partes = "; ".join(f"{next(t['cotacao'].fornecedor.empresa for t in totais if t['cotacao'].id == cid)}: {', '.join(tags)}"
                           for cid, tags in donos.items())
        alertas.append(_alerta(
            'info', f"O menor preço por instrumento está dividido entre fornecedores ({partes}).",
            "Contratar separado compensa frente aos custos de deslocamento e à gestão de dois fornecedores?"))

    return {'cotacoes': cotacoes, 'linhas': linhas, 'totais': totais, 'alertas': alertas}
