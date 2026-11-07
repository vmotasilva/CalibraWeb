"""Indicadores de insumos: cruzam o consumo de um item (códigos do almoxarifado) com a produção lançada nos KPIs principais.

Reproduz a lógica das abas "Materiais_Semanal/Mensal_Apresentação" da planilha de indicadores:

  rendimento  = produção × participação ÷ consumo        (ex.: Pad = lentes × 70% ÷ pads; Fita = lentes ÷ metros)
  consumo     = consumo ÷ produção × participação⁻¹      (ex.: Aloy = gramas ÷ lentes boas)
  uso         = consumo no período                       (ex.: filtros usados na semana)

O consumo já vem na unidade do item: o fator de conversão (35 m por rolo, 30 g por frasco...) é o `fator` do vínculo do
código no cadastro. A produção vem de uma variável de um KPI principal (Medicao.dados), no mesmo período; se o período
não tiver valor próprio, soma os lançamentos diários dentro dele."""
import calendar
import datetime
from dataclasses import dataclass
from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.utils import timezone

from kpi import insumos
from kpi.models import HierConsumo, HierMovimento, IndicadorInsumo, Medicao

VISOES = (('dia', 'Dia a dia'), ('semana', 'Semana a semana'), ('mes', 'Mês a mês'))
GRANULARIDADE = {'dia': 'diaria', 'semana': 'semanal', 'mes': 'mensal'}
JANELA_SEMANAS = 8
JANELA_MESES = 12
MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
UM_DIA = datetime.timedelta(days=1)


@dataclass(frozen=True)
class Periodo:
    ini: datetime.date
    fim: datetime.date
    rotulo: str

    @property
    def dias(self):
        return (self.fim - self.ini).days + 1


def fim_do_mes(d):
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def mes_param(txt, hoje=None):
    """'YYYY-MM' -> último dia do mês; vazio/inválido -> mês atual."""
    try:
        ano, mes = (txt or '').split('-')
        return fim_do_mes(datetime.date(int(ano), int(mes), 1))
    except (ValueError, TypeError):
        return fim_do_mes(hoje or timezone.localdate())


def periodos(visao, ref, hoje=None):
    """Períodos exibidos. Dia: os dias do mês de `ref`. Semana: as últimas 8 semanas (seg–dom) até a de `ref` (ou de
    hoje, se o mês ainda não acabou). Mês: os últimos 12 meses até o de `ref`."""
    hoje = hoje or timezone.localdate()
    if visao == 'dia':
        dias = [ref.replace(day=d) for d in range(1, calendar.monthrange(ref.year, ref.month)[1] + 1)]
        return [Periodo(d, d, f'{d:%d}') for d in dias]
    if visao == 'semana':
        segunda = min(ref, hoje) - datetime.timedelta(days=min(ref, hoje).weekday())
        out = []
        for i in range(JANELA_SEMANAS - 1, -1, -1):
            ini = segunda - datetime.timedelta(days=7 * i)
            out.append(Periodo(ini, ini + datetime.timedelta(days=6), f'SEM {ini.isocalendar()[1]}'))
        return out
    out, y, m = [], ref.year, ref.month
    for _ in range(JANELA_MESES):
        out.append(Periodo(datetime.date(y, m, 1), datetime.date(y, m, calendar.monthrange(y, m)[1]), f'{MESES[m - 1]}/{y % 100:02d}'))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out[::-1]


def titulo_janela(visao, pers):
    if visao == 'dia':
        return f'dias de {pers[0].ini:%m/%Y}'
    if visao == 'semana':
        return f'últimas {len(pers)} semanas (segunda a domingo)'
    return f'últimos {len(pers)} meses'


def _valor_variavel(medicao, variavel):
    if not variavel:
        return medicao.valor
    alvo = variavel.strip().casefold()
    for k, v in (medicao.dados or {}).items():
        if k.strip().casefold() == alvo:
            try:
                return Decimal(str(v))
            except Exception:  # valor não numérico lançado no campo
                return None
    return None


def producao_por_periodo(ind, visao, pers):
    """{período: produção} lida dos KPIs principais. None = sem lançamento no período."""
    if ind.modo == IndicadorInsumo.MODO_USO or not ind.producao_indicador_id:
        return {p: None for p in pers}
    qs = Medicao.objects.filter(indicador_id=ind.producao_indicador_id, setor_id=ind.producao_setor_id,
                                periodo__range=(pers[0].ini, pers[-1].fim))
    mapa = {(m.granularidade, m.periodo): _valor_variavel(m, ind.producao_variavel) for m in qs}
    diarias = {d: v for (g, d), v in mapa.items() if g == 'diaria' and v is not None}
    gran = GRANULARIDADE[visao]
    out = {}
    for p in pers:
        exato = mapa.get((gran, p.fim if visao == 'mes' else p.ini))
        if exato is not None:
            out[p] = exato
            continue
        dias = [v for d, v in diarias.items() if p.ini <= d <= p.fim]
        out[p] = sum(dias, Decimal(0)) if dias else None
    return out


def consumo_por_periodo(ind, visao, pers, hoje=None):
    """{período: consumo do item na unidade do item}. No mês vale o consumo do mês (manual prevalece sobre o importado);
    em dia e semana, a soma das movimentações. Períodos que ainda não começaram ficam None."""
    hoje = hoje or timezone.localdate()
    total = Sum(ExpressionWrapper(F('quantidade') * F('codigo__fator'), output_field=DecimalField(max_digits=24, decimal_places=6)))
    movs = (HierMovimento.objects.filter(codigo__item_id=ind.item_id, tipo__in=insumos.TIPOS_CONSUMO,
                                         data__range=(pers[0].ini, pers[-1].fim))
            .order_by().values('data').annotate(total=total))
    por_dia = {r['data']: Decimal(r['total']) for r in movs}
    mensal = {}
    if visao == 'mes':
        mensal = {c.periodo: c.valor for c in HierConsumo.objects.filter(item_id=ind.item_id, periodo__in=[p.fim for p in pers])}
    out = {}
    for p in pers:
        if p.ini > hoje:
            out[p] = None
        elif p.fim in mensal:
            out[p] = mensal[p.fim]
        else:
            out[p] = sum((v for d, v in por_dia.items() if p.ini <= d <= p.fim), Decimal(0))
    return out


def calcular_valor(ind, producao, consumo):
    """Valor do indicador no período; None quando não dá para calcular (sem produção, ou consumo zero no rendimento)."""
    if consumo is None:
        return None
    mult, parte = ind.multiplicador, ind.participacao / Decimal(100)
    if ind.modo == IndicadorInsumo.MODO_USO:
        v = consumo * mult
    elif producao is None:
        return None
    elif ind.modo == IndicadorInsumo.MODO_RENDIMENTO:
        if consumo <= 0:
            return None
        v = producao * parte / consumo * mult
    else:
        if producao * parte <= 0:
            return None
        v = consumo / (producao * parte) * mult
    return v.quantize(Decimal(1).scaleb(-ind.casas))


def meta_do_periodo(ind, visao, p):
    """Mês: meta geral. Semana/dia: a meta própria; sem ela, a meta geral (razões) ou a meta mensal proporcional aos dias (uso)."""
    if visao == 'mes':
        return ind.meta
    propria = ind.meta_semanal if visao == 'semana' else ind.meta_diaria
    if propria is not None:
        return propria
    if ind.modo == IndicadorInsumo.MODO_USO and ind.meta is not None:
        return ind.meta * p.dias / calendar.monthrange(p.fim.year, p.fim.month)[1]
    return ind.meta


def serie(ind, visao, ref, hoje=None):
    """Série do indicador: uma linha por período com produção, consumo, valor, meta e se atingiu."""
    hoje = hoje or timezone.localdate()
    pers = periodos(visao, ref, hoje)
    prod = producao_por_periodo(ind, visao, pers)
    cons = consumo_por_periodo(ind, visao, pers, hoje)
    linhas = []
    for p in pers:
        valor = calcular_valor(ind, prod[p], cons[p])
        meta = meta_do_periodo(ind, visao, p)
        linhas.append({'rotulo': p.rotulo, 'ini': p.ini, 'fim': p.fim, 'producao': prod[p], 'consumo': cons[p],
                       'valor': valor, 'meta': meta, 'ok': ind.atingiu(valor, meta)})
    com_valor = [l for l in linhas if l['valor'] is not None]
    avaliados = [l for l in linhas if l['ok'] is not None]
    return {'visao': visao, 'janela': titulo_janela(visao, pers), 'linhas': linhas,
            'ultimo': com_valor[-1] if com_valor else None,
            'dentro': sum(1 for l in avaliados if l['ok']), 'fora': sum(1 for l in avaliados if not l['ok'])}


def _f(v):
    return None if v is None else float(v)


def para_grafico(ind, s):
    """Dados do gráfico (Chart.js): barras do realizado, verdes na meta e vermelhas fora, e a linha da meta."""
    sentido = 'maior' if ind.sentido == 'maior' else 'menor'
    return {
        'labels': [l['rotulo'] for l in s['linhas']],
        'faixas': [f'{l["ini"]:%d/%m}' if l['ini'] == l['fim'] else f'{l["ini"]:%d/%m} a {l["fim"]:%d/%m}' for l in s['linhas']],
        'valores': [_f(l['valor']) for l in s['linhas']],
        'metas': [_f(l['meta']) for l in s['linhas']],
        'producao': [_f(l['producao']) for l in s['linhas']],
        'consumo': [_f(l['consumo']) for l in s['linhas']],
        'unidade': ind.unidade, 'sentido': sentido, 'titulo': ind.nome,
    }
