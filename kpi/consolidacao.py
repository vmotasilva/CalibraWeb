"""Composição automática dos valores semanais e mensais a partir das variáveis lançadas por dia."""
import datetime
from collections import defaultdict
from decimal import Decimal

from kpi import calculo
from kpi.models import Medicao

OBS_CONSOLIDADO = 'Consolidado dos lançamentos diários'


def consolidar_valores(ind, setor_id, datas_diarias, usuario=None):
    """Recalcula a semana e o mês de cada data diária: soma cada variável nos dias do período e aplica a
    memória de cálculo. Só vale para indicadores com fórmula e quando todos os dias do período têm variáveis.
    Semana/mês com observação própria (tratado à mão) nunca é sobrescrito."""
    if not ind.formula:
        return
    from kpi.views import _normalizar

    periodos = {(g, _normalizar(g, d)) for d in datas_diarias for g in ('semanal', 'mensal') if ind.permite_valor(g)}
    for g, periodo in periodos:
        ini, fim = (periodo, periodo + datetime.timedelta(days=6)) if g == 'semanal' else (periodo.replace(day=1), periodo)
        soma, usados, total = defaultdict(Decimal), 0, 0
        for m in Medicao.objects.filter(indicador=ind, setor_id=setor_id, granularidade='diaria', periodo__range=(ini, fim)):
            total += 1
            if m.dados:
                usados += 1
                for k, v in m.dados.items():
                    soma[k] += Decimal(str(v))
        if usados != total:
            continue  # há dias sem variáveis (lançados só com o valor): somar parte dos dias distorceria o período
        atual = Medicao.objects.filter(indicador=ind, setor_id=setor_id, granularidade=g, periodo=periodo).first()
        if atual is not None and atual.observacao not in ('', OBS_CONSOLIDADO):
            continue  # semana/mês com observação própria foi tratado à mão: não sobrescrever
        if not usados:
            if atual is not None and atual.observacao == OBS_CONSOLIDADO:
                atual.delete()
            continue
        try:
            valor = calculo.calcular(ind.formula, soma)
        except (ValueError, ZeroDivisionError):
            if atual is not None and atual.observacao == OBS_CONSOLIDADO:
                atual.delete()
            continue
        Medicao.objects.update_or_create(
            indicador=ind, setor_id=setor_id, periodo=periodo, granularidade=g,
            defaults={'valor': valor, 'observacao': OBS_CONSOLIDADO,
                      'dados': {k: str(v) for k, v in soma.items()}, 'registrado_por': usuario})
