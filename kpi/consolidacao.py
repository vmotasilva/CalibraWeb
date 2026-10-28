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


OBS_SEMANAS = 'Consolidado das semanas'


def _mes_da_semana(segunda):
    """Regra ISO: a semana (segunda a domingo) pertence ao mês em que cai a sua quinta-feira."""
    return (segunda + datetime.timedelta(days=3)).replace(day=1)


def consolidar_mensal_das_semanas(ind, setor_id, semanas, usuario=None):
    """Recalcula o mês de cada semana lançada: soma as variáveis das semanas do mês e aplica a memória de cálculo.
    Só para indicador com fórmula e sem lançamento diário (o diário é mais preciso e já consolida o mês).
    Nunca sobrescreve um mês lançado de outra forma (à mão, importado ou por outro processo): só o que este mesmo processo criou."""
    if not ind.formula or ind.exibir_diario:
        return
    from kpi.views import _normalizar

    um_dia = datetime.timedelta(days=1)
    for ini in {_mes_da_semana(_normalizar('semanal', d)) for d in semanas}:
        fim = (ini.replace(day=28) + datetime.timedelta(days=4)).replace(day=1) - um_dia
        atual = Medicao.objects.filter(indicador=ind, setor_id=setor_id, granularidade='mensal', periodo=fim).first()
        if atual is not None and atual.observacao != OBS_SEMANAS:
            continue
        # semanas cuja quinta-feira cai no mês: a segunda-feira vai de 3 dias antes do dia 1 a 3 dias antes do último dia
        doc = list(Medicao.objects.filter(indicador=ind, setor_id=setor_id, granularidade='semanal',
                                          periodo__range=(ini - 3 * um_dia, fim - 3 * um_dia)))
        valor, dados = None, {}
        if doc and all(m.dados for m in doc):
            soma = defaultdict(Decimal)
            for m in doc:
                for k, v in m.dados.items():
                    soma[k] += Decimal(str(v))
            try:
                valor, dados = calculo.calcular_ou_none(ind.formula, soma), {k: str(v) for k, v in soma.items()}
            except ValueError:
                valor = None
        if valor is None:
            if atual is not None:
                atual.delete()
            continue
        Medicao.objects.update_or_create(
            indicador=ind, setor_id=setor_id, periodo=fim, granularidade='mensal',
            defaults={'valor': valor, 'observacao': OBS_SEMANAS, 'dados': dados, 'registrado_por': usuario})


def consolidar(ind, setor_id, gran, periodos, usuario=None):
    """Ponto único após gravar ou excluir valores: diário compõe semana e mês; semanal compõe o mês."""
    if gran == 'diaria':
        consolidar_valores(ind, setor_id, periodos, usuario)
    elif gran == 'semanal':
        consolidar_mensal_das_semanas(ind, setor_id, periodos, usuario)
