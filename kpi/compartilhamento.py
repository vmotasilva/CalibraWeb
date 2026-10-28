"""Variáveis compartilhadas: indicadores do mesmo grupo que têm uma variável com o mesmo nome dividem o valor lançado.
Sem grupo no indicador, nada aqui altera o comportamento: as funções devolvem os dados como vieram."""
from decimal import Decimal

from kpi import calculo, consolidacao
from kpi.models import Indicador, Medicao


def irmaos(ind):
    if not ind.grupo:
        return []
    return list(Indicador.objects.filter(ativo=True, grupo__iexact=ind.grupo).exclude(pk=ind.pk).prefetch_related('setores'))


def _setor_de(outro, setor):
    """(existe, setor equivalente no outro indicador, casando pelo nome). Geral (None) vale para todos."""
    if setor is None:
        return True, None
    achado = next((s for s in outro.setores.all() if s.nome.strip().lower() == setor.nome.strip().lower()), None)
    return achado is not None, achado


def completar(ind, setor, gran, periodo, dados):
    """Devolve `dados` acrescidos das variáveis que faltam e já foram lançadas, no mesmo período, em outro indicador do grupo."""
    if not ind.grupo:
        return dados
    faltam = [c for c in calculo.lista_campos(ind) if c not in dados]
    if not faltam:
        return dados
    saida = dict(dados)
    for outro in irmaos(ind):
        ok, alvo = _setor_de(outro, setor)
        if not ok:
            continue
        med = Medicao.objects.filter(indicador=outro, setor=alvo, granularidade=gran, periodo=periodo).first()
        if not med or not med.dados:
            continue
        guardado = {k.strip().lower(): v for k, v in med.dados.items()}
        for nome in faltam:
            if nome not in saida and nome.lower() in guardado:
                saida[nome] = Decimal(str(guardado[nome.lower()]))
    return saida


def propagar(ind, setor, gran, periodo, dados, usuario=None):
    """Replica as variáveis lançadas para os demais indicadores do grupo e recalcula o valor de cada um.
    Só mexe em indicador com fórmula e período habilitado; se ainda faltam variáveis, não grava nada nele.
    Divisão por zero (sem dado) remove o valor calculado antes, que ficaria desatualizado. Retorna a lista dos indicadores atualizados."""
    if not ind.grupo or not dados:
        return []
    comp = {k.strip().lower(): v for k, v in dados.items()}
    atualizados = []
    for outro in irmaos(ind):
        if not outro.formula or not outro.permite_valor(gran):
            continue
        ok, alvo = _setor_de(outro, setor)
        if not ok:
            continue
        novos = {c: Decimal(str(comp[c.lower()])) for c in calculo.lista_campos(outro) if c.lower() in comp}
        if not novos:
            continue
        atual = Medicao.objects.filter(indicador=outro, setor=alvo, granularidade=gran, periodo=periodo).first()
        base = {k: Decimal(str(v)) for k, v in (atual.dados or {}).items()} if atual else {}
        base.update(novos)
        base = completar(outro, alvo, gran, periodo, base)
        try:
            valor = calculo.calcular_ou_none(outro.formula, base)
        except ValueError:
            continue  # ainda faltam variáveis neste indicador
        if valor is None:
            if atual:
                atual.delete()
        else:
            Medicao.objects.update_or_create(
                indicador=outro, setor=alvo, periodo=periodo, granularidade=gran,
                defaults={'valor': valor, 'dados': {k: str(v) for k, v in base.items()}, 'registrado_por': usuario,
                          'observacao': atual.observacao if atual else 'Variáveis compartilhadas'})
            atualizados.append(outro)
        consolidacao.consolidar(outro, alvo.pk if alvo else None, gran, [periodo], usuario)
    return atualizados
