"""Composição automática dos valores semanais e mensais a partir das variáveis lançadas por dia."""
import datetime
from collections import defaultdict
from decimal import Decimal

from kpi import calculo
from kpi.models import Medicao

OBS_CONSOLIDADO = 'Consolidado dos lançamentos diários'
OBS_MEDIA = 'Média dos lançamentos diários'


def consolidar_valores(ind, setor_id, datas_diarias, usuario=None):
    """Recalcula a semana e o mês de cada data diária. Só para indicadores com fórmula.
    - Todos os dias com variáveis: soma cada variável e aplica a memória de cálculo (valor exato).
    - Há dias lançados só com o valor (sem variáveis): usa a média dos valores dos dias, apenas para criar o período
      ou atualizar o que o próprio sistema criou assim, nunca um valor que já exista (importado ou lançado à mão).
    Semana/mês com observação própria (tratado à mão) nunca é sobrescrito."""
    if not ind.formula:
        return
    from kpi.views import _normalizar

    periodos = {(g, _normalizar(g, d)) for d in datas_diarias for g in ('semanal', 'mensal') if ind.permite_valor(g)}
    for g, periodo in periodos:
        ini, fim = (periodo, periodo + datetime.timedelta(days=6)) if g == 'semanal' else (periodo.replace(day=1), periodo)
        diarias = list(Medicao.objects.filter(indicador=ind, setor_id=setor_id, granularidade='diaria', periodo__range=(ini, fim)))
        atual = Medicao.objects.filter(indicador=ind, setor_id=setor_id, granularidade=g, periodo=periodo).first()
        marcas = ('', OBS_CONSOLIDADO, OBS_MEDIA)
        if atual is not None and atual.observacao not in marcas:
            continue  # semana/mês com observação própria foi tratado à mão: não sobrescrever
        gerado = atual is not None and atual.observacao in (OBS_CONSOLIDADO, OBS_MEDIA)
        if not diarias:
            if gerado:
                atual.delete()
            continue
        soma = defaultdict(Decimal)
        com_dados = [m for m in diarias if m.dados]
        for m in com_dados:
            for k, v in m.dados.items():
                soma[k] += Decimal(str(v))
        valor, obs, dados = None, OBS_CONSOLIDADO, {}
        if len(com_dados) == len(diarias):
            try:
                valor, dados = calculo.calcular(ind.formula, soma), {k: str(v) for k, v in soma.items()}
            except (ValueError, ZeroDivisionError):
                valor = None
        else:
            if atual is not None and not gerado:
                continue  # já existe um valor (importado ou lançado): não trocar por uma média
            valor = (sum(m.valor for m in diarias) / len(diarias)).quantize(Decimal('0.01'))
            obs = OBS_MEDIA
        if valor is None:
            if gerado:
                atual.delete()
            continue
        Medicao.objects.update_or_create(
            indicador=ind, setor_id=setor_id, periodo=periodo, granularidade=g,
            defaults={'valor': valor, 'observacao': obs, 'dados': dados, 'registrado_por': usuario})
