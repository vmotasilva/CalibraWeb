"""Cobrança de causas e análises: períodos fora da meta sem causa/análise e sem dispensa, por responsável."""
from kpi.models import AnaliseCausa, Indicador, Medicao

# quantos períodos recentes de cada gráfico entram na cobrança (os mesmos que o painel carrega)
LIMITES = {'mensal': 12, 'semanal': 52, 'diaria': 120}


def responsavel_do_escopo(ind, setor):
    """Responsável pela causa e análise: o do setor, ou o geral do indicador quando o setor não tem."""
    if setor is not None and setor.responsavel_analise_id:
        return setor.responsavel_analise
    return ind.responsavel_analise if ind.responsavel_analise_id else None


def contar_pendentes(ind, setor):
    """Períodos fora da meta, sem registro (causa/análise ou dispensa), no escopo (geral ou setor)."""
    meta = setor.meta_efetiva if setor is not None else ind.meta
    total = 0
    for gran in ind.graficos():
        meds = list(Medicao.objects.filter(indicador=ind, setor=setor, granularidade=gran).order_by('-periodo')[:LIMITES[gran]])
        fora = [m.periodo for m in meds if ind.atingiu(m.valor, meta) is False]
        if not fora:
            continue
        tratados = set(AnaliseCausa.objects.filter(indicador=ind, setor=setor, granularidade=gran, periodo__in=fora)
                       .values_list('periodo', flat=True))
        total += sum(1 for p in fora if p not in tratados)
    return total


def pendentes_do_usuario(user):
    """Total de períodos pendentes dos escopos em que `user` é o responsável."""
    if not getattr(user, 'is_authenticated', False):
        return 0
    total = 0
    indicadores = (Indicador.objects.filter(ativo=True)
                   .select_related('responsavel_analise').prefetch_related('setores__responsavel_analise'))
    for ind in indicadores:
        escopos = [None] + list(ind.setores.all())
        for setor in escopos:
            resp = responsavel_do_escopo(ind, setor)
            if resp is not None and resp.pk == user.pk:
                total += contar_pendentes(ind, setor)
    return total
