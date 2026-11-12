"""KPI por setor (hierárquico): KPI > Setor > Categoria > Subcategoria > Item, com consumo mensal e meta por item.

O consumo do item vem da importação do relatório de movimentação do almoxarifado, via códigos vinculados ao item
(kpi.insumos), ou de lançamento manual."""
import calendar
import datetime
import re
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Max, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.views.decorators.http import require_POST

from kpi import indicadores_insumo, insumos
from kpi.models import (HierCategoria, HierCodigo, HierConsumo, HierImportacao, HierItem, HierMovimento, HierSetor, HierSubcategoria,
                        IndicadorInsumo, KpiHierarquico)

JANELA_MESES = 12
LIMITE_ARQUIVO = 25 * 1024 * 1024


def _fim_do_mes(d):
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def _mes_param(txt):
    """'YYYY-MM' -> último dia do mês; vazio/inválido -> mês atual."""
    try:
        ano, mes = (txt or '').split('-')
        return _fim_do_mes(datetime.date(int(ano), int(mes), 1))
    except (ValueError, TypeError):
        return _fim_do_mes(timezone.localdate())


def _meses_ate(fim, n):
    out, y, m = [], fim.year, fim.month
    for _ in range(n):
        out.append(datetime.date(y, m, calendar.monthrange(y, m)[1]))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out[::-1]


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _decimal(txt):
    try:
        return Decimal((txt or '').strip().replace(',', '.'))
    except InvalidOperation:
        return None


def _sentido_comum(itens):
    """Comparação da série agregada: a dos itens, se todos usam a mesma; senão, ≤."""
    sentidos = {i.sentido for i in itens if i.meta}
    return sentidos.pop() if len(sentidos) == 1 else '<='


GRAFICOS = (('unica', 'Barra única', 'bi-bar-chart'), ('multiplas', 'Múltiplas barras', 'bi-bar-chart-steps'),
            ('empilhadas', 'Empilhadas', 'bi-layers'))


def _multi(dados, tipo, n):
    """Uma série por item com consumo no período. Se esses itens usam a mesma unidade, mostra o consumo real; senão
    (kg x UN...) mostra o % da meta de cada um, que é comparável (itens sem meta ficam de fora, e o aviso diz quais).
    Empilhadas: soma dos itens (e da meta) em cada período."""
    com_dados = [x for x in dados if any(v is not None for v in x['valores'])]
    mesma_un = len({x['unidade'] for x in com_dados}) <= 1
    series, fora = [], []
    for x in com_dados:
        if mesma_un:
            vals = x['valores']
        elif any(m for m in x['metas']):
            vals = [None if v is None or not m else round(v / m * 100, 1) for v, m in zip(x['valores'], x['metas'])]
        else:
            fora.append(x['nome'])
            continue
        series.append({'nome': x['nome'], 'valores': vals})
    if mesma_un:
        metas = None
        if tipo == 'empilhadas':
            somas = [sum(x['metas'][k] or 0 for x in com_dados) for k in range(n)]
            metas = [round(v, 2) if v else None for v in somas]
    else:
        metas = [100.0 * (len(series) if tipo == 'empilhadas' else 1)] * n
    aviso = ''
    if not mesma_un:
        aviso = 'Unidades diferentes entre os itens: cada barra mostra o % da meta do item'                 + (' (a soma dos % é a altura da pilha).' if tipo == 'empilhadas' else '.')
        if fora:
            aviso += f' Sem meta cadastrada (não aparecem): {", ".join(fora)}.'
    return {'tipo': tipo, 'series': series, 'metas': metas, 'modo': 'valor' if mesma_un else 'percentual',
            'unidade': (com_dados[0]['unidade'] if mesma_un and com_dados else '' if mesma_un else '%'),
            'aviso': aviso}


def _serie(itens, meses, consumos):
    """Um item: consumo real e a meta dele. Vários itens: média do % da meta (consumo ÷ meta), pois as unidades diferem."""
    por_item = {}
    for c in consumos:
        por_item.setdefault(c.item_id, {})[c.periodo] = c.valor
    rotulos = [f'{m:%m/%Y}' for m in meses]
    matriz = [{'nome': i.nome, 'unidade': i.unidade,
               'valores': [float(por_item[i.pk][m]) if m in por_item.get(i.pk, {}) else None for m in meses],
               'metas': [float(i.meta) if i.meta is not None else None] * len(meses)} for i in itens]
    if len(itens) == 1:
        item = itens[0]
        dados = por_item.get(item.pk, {})
        return {'modo': 'valor', 'labels': rotulos,
                'valores': [float(dados[m]) if m in dados else None for m in meses],
                'meta': float(item.meta) if item.meta is not None else None,
                'sentido': item.sentido, 'unidade': item.unidade, 'titulo': f'Consumo ({item.unidade})' if item.unidade else 'Consumo',
                '_itens': matriz}
    valores = []
    for m in meses:
        pcts = [por_item[i.pk][m] / i.meta * 100 for i in itens
                if i.meta and i.pk in por_item and m in por_item[i.pk]]
        valores.append(round(float(sum(pcts) / len(pcts)), 1) if pcts else None)
    return {'modo': 'percentual', 'labels': rotulos, 'valores': valores, 'meta': 100.0, 'unidade': '%',
            'sentido': _sentido_comum(itens), 'titulo': '% da meta de consumo (média dos itens com meta)', '_itens': matriz}


VISOES = (('dia', 'Dia a dia'), ('semana', 'Semana a semana'), ('mes', 'Mês a mês'))
JANELA_SEMANAS = 12


def _buckets(visao, fim):
    """Dia: os dias do mês escolhido. Semana: as últimas 12 semanas (seg–dom) até o fim do mês escolhido, ou até hoje
    se o mês ainda não acabou. Cada bucket é a lista de dias que ele cobre."""
    if visao == 'dia':
        dias = [fim.replace(day=d) for d in range(1, fim.day + 1)]
        return [[d] for d in dias], [f'{d:%d}' for d in dias], f'dias de {fim:%m/%Y}'
    ref = min(fim, timezone.localdate())
    ini = ref - datetime.timedelta(days=ref.weekday() + 7 * (JANELA_SEMANAS - 1))
    buckets = [[ini + datetime.timedelta(days=7 * w + k) for k in range(7)] for w in range(JANELA_SEMANAS)]
    sem = [b[0].isocalendar()[1] for b in buckets]
    return (buckets, [f'S{n:02d}' for n in sem],
            f'últimas {JANELA_SEMANAS} semanas (S{sem[0]:02d} a S{sem[-1]:02d}, de segunda a domingo)')


def _consumo_diario(itens, ini, fim):
    """{item_id: {data: consumo}} a partir das movimentações importadas (lançamento manual só existe por mês)."""
    total = Sum('quantidade')  # em unidades; o fator de conversão só entra nos indicadores que o pedem
    qs = (HierMovimento.objects.filter(codigo__item__in=itens, tipo__in=insumos.TIPOS_CONSUMO, data__range=(ini, fim))
          .order_by().values('codigo__item_id', 'data').annotate(total=total))
    out = {}
    for r in qs:
        out.setdefault(r['codigo__item_id'], {})[r['data']] = Decimal(r['total'])
    return out


def _meta_dia(item, dia):
    """Meta mensal diluída pelos dias do mês (ritmo esperado de consumo por dia)."""
    return item.meta / calendar.monthrange(dia.year, dia.month)[1] if item.meta is not None else None


def _serie_curta(itens, visao, fim):
    """Série por dia ou semana. Meta proporcional = meta mensal ÷ dias do mês, somada nos dias do período."""
    buckets, rotulos, janela = _buckets(visao, fim)
    faixas = [f'{b[0]:%d/%m/%Y}' if len(b) == 1 else f'{b[0]:%d/%m/%y} a {b[-1]:%d/%m/%y}' for b in buckets]
    hoje = timezone.localdate()
    diario = _consumo_diario(itens, buckets[0][0], buckets[-1][-1])

    def consumo(i, b):
        if b[0] > hoje:
            return None
        return sum((diario.get(i.pk, {}).get(d, Decimal(0)) for d in b if d <= hoje), Decimal(0))

    def meta(i, b):
        # Período em andamento: a meta vale só até hoje, como o consumo (senão a semana atual pareceria folgada).
        metas = [_meta_dia(i, d) for d in b if d <= hoje or b[0] > hoje]
        return None if i.meta is None else float(sum(metas))

    matriz = [{'nome': i.nome, 'unidade': i.unidade,
               'valores': [None if consumo(i, b) is None else float(consumo(i, b)) for b in buckets],
               'metas': [meta(i, b) for b in buckets]} for i in itens]
    if len(itens) == 1:
        i = itens[0]
        return {'_itens': matriz, 'modo': 'valor', 'labels': rotulos, 'faixas': faixas, 'janela': janela, 'meta': None,
                'valores': [None if consumo(i, b) is None else round(float(consumo(i, b)), 2) for b in buckets],
                'metas': [None if meta(i, b) is None else round(meta(i, b), 2) for b in buckets], 'sentido': i.sentido,
                'unidade': i.unidade, 'titulo': f'Consumo ({i.unidade})' if i.unidade else 'Consumo',
                'meta_texto': 'meta proporcional (meta mensal ÷ dias do mês)' if i.meta is not None else ''}
    valores = []
    for b in buckets:
        pcts = [consumo(i, b) / Decimal(meta(i, b)) * 100 for i in itens if i.meta and consumo(i, b) is not None]
        valores.append(round(float(sum(pcts) / len(pcts)), 1) if pcts else None)
    return {'modo': 'percentual', 'labels': rotulos, 'faixas': faixas, 'janela': janela, 'valores': valores, 'meta': 100.0, 'metas': None, 'sentido': _sentido_comum(itens),
            'unidade': '%', 'titulo': '% da meta proporcional (média dos itens com meta)', 'meta_texto': 'meta 100%', '_itens': matriz}


def _tabela(serie):
    """Linhas da tabela de dados do gráfico (mesmos números do gráfico). Consumo: menor é melhor, então "na meta" = até a meta."""
    metas = serie.get('metas') or [serie.get('meta')] * len(serie['labels'])
    faixas = serie.get('faixas') or [''] * len(serie['labels'])
    linhas = []
    for rotulo, faixa, valor, meta in zip(serie['labels'], faixas, serie['valores'], metas):
        ok = None if valor is None or meta is None else HierItem.compara(valor, meta, serie.get('sentido', '<='))
        pct = round(valor / meta * 100) if serie['modo'] == 'valor' and valor is not None and meta else None
        linhas.append({'rotulo': rotulo, 'faixa': faixa, 'valor': valor, 'meta': meta, 'pct': pct, 'ok': ok})
    return linhas


@login_required
def painel_view(request):
    kpis = list(KpiHierarquico.objects.filter(ativo=True))
    kpi = next((k for k in kpis if k.pk == _int(request.GET.get('kpi'))), kpis[0] if kpis else None)
    ctx = {'kpis': kpis, 'kpi': kpi}
    if not kpi:
        return render(request, 'kpi/hier_painel.html', ctx)

    # Filtros independentes: todos sempre ativos; escolher um nível mais baixo preenche os de cima.
    setores = list(kpi.setores.all())
    todas_cats = list(HierCategoria.objects.filter(setor__kpi=kpi).select_related('setor'))
    todas_subs = list(HierSubcategoria.objects.filter(categoria__setor__kpi=kpi).select_related('categoria__setor'))
    todos_itens = list(HierItem.objects.filter(ativo=True, subcategoria__categoria__setor__kpi=kpi)
                       .select_related('subcategoria__categoria__setor'))
    setor = next((s for s in setores if s.pk == _int(request.GET.get('setor'))), None)
    categoria = next((c for c in todas_cats if c.pk == _int(request.GET.get('categoria'))), None)
    sub = next((s for s in todas_subs if s.pk == _int(request.GET.get('sub'))), None)
    item = next((i for i in todos_itens if i.pk == _int(request.GET.get('item'))), None)
    # Deduz os níveis acima a partir do mais baixo escolhido (o mais baixo prevalece).
    if item:
        sub = item.subcategoria
    if sub:
        categoria = sub.categoria
    if categoria:
        setor = categoria.setor
    categorias = [c for c in todas_cats if not setor or c.setor_id == setor.pk]
    subs = [s for s in todas_subs if (not categoria or s.categoria_id == categoria.pk)
            and (not setor or s.categoria.setor_id == setor.pk)]
    itens_opcoes = [i for i in todos_itens if (not sub or i.subcategoria_id == sub.pk)
                    and (not categoria or i.subcategoria.categoria_id == categoria.pk)
                    and (not setor or i.subcategoria.categoria.setor_id == setor.pk)]
    arvore = {
        'setores': [{'id': s.pk, 'nome': s.nome} for s in setores],
        # 'ctx' = nome do pai, mostrado ao lado da opção quando o nível acima está em "Todos".
        'categorias': [{'id': c.pk, 'nome': c.nome, 'setor': c.setor_id, 'ctx': c.setor.nome} for c in todas_cats],
        'subs': [{'id': s.pk, 'nome': s.nome, 'categoria': s.categoria_id, 'setor': s.categoria.setor_id,
                  'ctx': s.categoria.nome} for s in todas_subs],
        'itens': [{'id': i.pk, 'nome': i.nome, 'sub': i.subcategoria_id, 'categoria': i.subcategoria.categoria_id,
                   'setor': i.subcategoria.categoria.setor_id, 'ctx': i.subcategoria.nome} for i in todos_itens],
    }

    itens_qs = (HierItem.objects.filter(ativo=True, subcategoria__categoria__setor__kpi=kpi)
                .select_related('subcategoria__categoria__setor').prefetch_related('codigos'))
    if item:
        itens_qs = itens_qs.filter(pk=item.pk)
    elif sub:
        itens_qs = itens_qs.filter(subcategoria=sub)
    elif categoria:
        itens_qs = itens_qs.filter(subcategoria__categoria=categoria)
    elif setor:
        itens_qs = itens_qs.filter(subcategoria__categoria__setor=setor)
    itens = list(itens_qs.order_by('subcategoria__categoria__setor__ordem', 'subcategoria__categoria__ordem',
                                   'subcategoria__ordem', 'ordem', 'nome'))

    fim = _mes_param(request.GET.get('mes'))
    visao = request.GET.get('visao') if request.GET.get('visao') in dict(VISOES) else 'mes'
    meses = _meses_ate(fim, JANELA_MESES)
    consumos = list(HierConsumo.objects.filter(item__in=itens, periodo__in=meses))
    atual = {c.item_id: c for c in consumos if c.periodo == fim}
    linhas = []
    for i in itens:
        c = atual.get(i.pk)
        v = c.valor if c else None
        linhas.append({'item': i, 'consumo': v, 'origem': c.origem if c else '',
                       'codigos': [x.codigo for x in i.codigos.all()],
                       'pct': round(v / i.meta * 100) if v is not None and i.meta else None,
                       'ok': i.atingiu(v)})
    com_meta = [l for l in linhas if l['ok'] is not None]
    ctx.update(
        setores=setores, setor=setor, categorias=categorias, categoria=categoria, subs=subs, sub=sub,
        itens_opcoes=itens_opcoes, item=item, arvore=arvore,
        niveis=(('setor', 'Setor'), ('categoria', 'Categoria'), ('sub', 'Subcategoria'), ('item', 'Item')),
        linhas=linhas, mes=fim, mes_valor=f'{fim:%Y-%m}', visao=visao, visoes=VISOES,
        serie=(_serie_curta(itens, visao, fim) if visao != 'mes' else _serie(itens, meses, consumos)) if itens else None,
        dentro=sum(1 for l in com_meta if l['ok']), fora=sum(1 for l in com_meta if not l['ok']),
        sem_lancamento=sum(1 for l in linhas if l['consumo'] is None),
    )
    grafico = request.GET.get('grafico') if request.GET.get('grafico') in dict((g[0], 1) for g in GRAFICOS) else 'unica'
    ctx.update(grafico=grafico, graficos=GRAFICOS, atualizado_ate=HierMovimento.objects.aggregate(m=Max('data'))['m'],
               ultimo_consumo=(HierMovimento.objects.filter(codigo__item__in=itens, tipo__in=insumos.TIPOS_CONSUMO)
                               .aggregate(m=Max('data'))['m'] if itens else None),
               itens_sem_meta=sum(1 for i in itens if i.meta is None),
               total_itens=len(linhas))
    if ctx['serie']:
        matriz = ctx['serie'].pop('_itens')
        ctx['serie']['tabela'] = _tabela(ctx['serie'])
        ctx['varios'] = len(itens) > 1
        if len(itens) == 1:
            # Indicadores de insumo ativos deste item (um por aba); a lista é dinâmica: nenhum, um ou vários.
            ctx['indicadores_item'] = [
                {'ind': ind, 'serie': indicadores_insumo.serie(ind, visao, fim)}
                for ind in IndicadorInsumo.objects.filter(item=itens[0], ativo=True)
                .select_related('producao_indicador', 'producao_setor')]
        if len(itens) > 1 and grafico != 'unica':
            ctx['serie']['multi'] = _multi(matriz, grafico, len(ctx['serie']['labels']))
    return render(request, 'kpi/hier_painel.html', ctx)


@login_required
def consumo_itens_view(request):
    """Tela de insumos: um gráfico de consumo por item, lado a lado e agrupados por setor (dia, semana ou mês)."""
    visao = request.GET.get('visao') if request.GET.get('visao') in dict(VISOES) else 'mes'
    fim = _mes_param(request.GET.get('mes'))
    todos = list(HierItem.objects.filter(ativo=True).select_related('subcategoria__categoria__setor')
                 .order_by('subcategoria__categoria__setor__ordem', 'subcategoria__categoria__ordem',
                           'subcategoria__ordem', 'ordem', 'nome'))
    setores = {}
    for i in todos:
        s = i.subcategoria.categoria.setor
        setores[s.pk] = s
    setor = setores.get(_int(request.GET.get('setor')))
    itens = [i for i in todos if not setor or i.subcategoria.categoria.setor_id == setor.pk]
    meses = _meses_ate(fim, JANELA_MESES)
    consumos = list(HierConsumo.objects.filter(item__in=itens, periodo__in=meses)) if visao == 'mes' else []
    grupos = []
    for i in itens:
        serie = _serie_curta([i], visao, fim) if visao != 'mes' else _serie([i], meses, consumos)
        serie.pop('_itens', None)
        if serie.get('metas') is None:
            serie['metas'] = [serie.get('meta')] * len(serie['labels'])
        if not serie.get('faixas'):
            serie['faixas'] = [f'{m:%m/%Y}' for m in meses]
        linhas = _tabela(serie)
        com_valor = [l for l in linhas if l['valor'] is not None]
        sc = i.subcategoria.categoria.setor
        card = {'item': i, 'grafico': serie, 'linhas': linhas, 'dom_id': f'dados-item-{i.pk}',
                'ultimo': com_valor[-1] if com_valor else None,
                'dentro': sum(1 for l in linhas if l['ok']), 'fora': sum(1 for l in linhas if l['ok'] is False),
                'caminho': f'{i.subcategoria.categoria.nome} › {i.subcategoria.nome}'}
        if not grupos or grupos[-1]['setor'].pk != sc.pk:
            grupos.append({'setor': sc, 'cards': []})
        grupos[-1]['cards'].append(card)
    return render(request, 'kpi/hier_consumo.html', {
        'grupos': grupos, 'visao': visao, 'visoes': VISOES, 'mes': fim, 'mes_valor': f'{fim:%Y-%m}',
        'setores': sorted(setores.values(), key=lambda s: (s.ordem, s.nome)), 'setor': setor, 'sem_itens': not todos,
    })


def _voltar_painel(post):
    params = {k: post.get(k) for k in ('kpi', 'setor', 'categoria', 'sub', 'item', 'mes', 'visao', 'grafico') if post.get(k)}
    return redirect(reverse('kpi:hier_painel') + ('?' + urlencode(params) if params else ''))


@login_required
@require_POST
def lancar_view(request):
    """Grava o consumo do mês de cada item enviado (campos valor_<id>). Em branco ou igual ao já importado não altera nada;
    um valor diferente vira lançamento manual, que prevalece sobre o importado."""
    periodo = _mes_param(request.POST.get('mes'))
    gravados = 0
    metas = 0
    for chave, bruto in request.POST.items():  # metas reajustadas no grid (em branco = sem meta)
        if not chave.startswith('meta_'):
            continue
        item = HierItem.objects.filter(pk=_int(chave[5:])).first()
        if not item:
            continue
        nova = None if not (bruto or '').strip() else _decimal(bruto)
        if (bruto or '').strip() and (nova is None or nova < 0):
            messages.error(request, f'Meta inválida para "{item}".')
            continue
        nova = nova.quantize(Decimal('0.01')) if nova is not None else None
        if nova != item.meta:
            item.meta = nova
            item.save(update_fields=['meta'])
            metas += 1
    if metas:
        messages.success(request, f'Meta atualizada em {metas} item(ns).')
    for chave, bruto in request.POST.items():
        if not chave.startswith('valor_') or not (bruto or '').strip():
            continue
        item = HierItem.objects.filter(pk=_int(chave[6:])).first()
        valor = _decimal(bruto)
        if not item or valor is None or valor < 0:
            messages.error(request, f'Valor inválido para "{item or chave}".')
            continue
        atual = HierConsumo.objects.filter(item=item, periodo=periodo).first()
        if atual and atual.origem == HierConsumo.ORIGEM_IMPORTADO and atual.valor == valor.quantize(Decimal('0.01')):
            continue
        HierConsumo.objects.update_or_create(
            item=item, periodo=periodo,
            defaults={'valor': valor, 'registrado_por': request.user, 'origem': HierConsumo.ORIGEM_MANUAL,
                      'observacao': (request.POST.get(f'obs_{item.pk}') or '').strip()[:255]})
        gravados += 1
    if gravados:
        messages.success(request, f'Consumo de {periodo:%m/%Y} salvo ({gravados} item(ns)).')
    return _voltar_painel(request.POST)


@login_required
@require_POST
def consumo_excluir_view(request, item_pk):
    """Exclui o lançamento manual do item no mês (volta a valer o importado, se houver). Importado só some desvinculando códigos."""
    periodo = _mes_param(request.POST.get('mes'))
    consumo = HierConsumo.objects.filter(item_id=item_pk, periodo=periodo).first()
    if not consumo:
        return _voltar_painel(request.POST)
    if consumo.origem == HierConsumo.ORIGEM_IMPORTADO:
        messages.warning(request, 'Este consumo vem do relatório importado. Para tirá-lo, desvincule os códigos do item.')
        return _voltar_painel(request.POST)
    consumo.delete()
    insumos.recalcular({item_pk})
    messages.success(request, 'Lançamento manual excluído.')
    return _voltar_painel(request.POST)


# ----- Importação do relatório de movimentação -----

@login_required
def importar_view(request):
    ctx = {'resumo': None, 'pendentes': HierCodigo.objects.filter(item__isnull=True, ignorado=False).count(),
           'tipos_consumo': sorted(insumos.TIPOS_CONSUMO)}
    if request.method == 'POST':
        arq = request.FILES.get('arquivo')
        if not arq:
            messages.error(request, 'Escolha o arquivo do relatório.')
        elif arq.size > LIMITE_ARQUIVO:
            messages.error(request, 'Arquivo muito grande (limite de 25 MB).')
        else:
            try:
                linhas, datemode = insumos.ler_linhas(arq.read(), arq.name)
                lido = insumos.interpretar(linhas, datemode)
                resumo = insumos.importar(lido['registros'])
                resumo.update(ignoradas=lido['ignoradas'], estornos=lido['estornos'])
                ctx['resumo'] = resumo
                HierImportacao.objects.create(
                    arquivo=arq.name[:200], inicio=resumo['inicio'], fim=resumo['fim'], lidas=resumo['lidas'],
                    adicionadas=resumo['adicionadas'], ja_existiam=resumo['ja_existiam'],
                    criado_por=request.user if request.user.is_authenticated else None)
                ctx['pendentes'] = HierCodigo.objects.filter(item__isnull=True, ignorado=False).count()
                messages.success(request, f'Importação concluída: {resumo["adicionadas"]} movimentação(ões) nova(s).')
            except insumos.ErroImportacao as e:
                messages.error(request, str(e))
    ctx['atualizado_ate'] = HierMovimento.objects.aggregate(m=Max('data'))['m']
    ctx['importacoes'] = HierImportacao.objects.select_related('criado_por')[:30]
    return render(request, 'kpi/hier_importar.html', ctx)


# ----- Códigos de insumo -----

def _codigos_filtrados(params):
    qs = HierCodigo.objects.all()
    q = (params.get('q') or '').strip()
    if q:
        filtro = Q(descricao__icontains=q) | Q(familia__icontains=q)
        if q.isdigit():
            filtro |= Q(codigo=int(q))
        qs = qs.filter(filtro)
    if params.get('familia'):
        qs = qs.filter(familia=params['familia'])
    status = params.get('status') or 'pendente'
    if status == 'pendente':
        qs = qs.filter(item__isnull=True, ignorado=False)
    elif status == 'vinculado':
        qs = qs.filter(item__isnull=False)
    elif status == 'ignorado':
        qs = qs.filter(ignorado=True)
    return qs, status


def _opcoes_itens():
    itens = (HierItem.objects.select_related('subcategoria__categoria__setor__kpi')
             .order_by('subcategoria__categoria__setor__kpi__nome', 'subcategoria__categoria__setor__ordem',
                       'subcategoria__categoria__ordem', 'subcategoria__ordem', 'ordem', 'nome'))
    return [(i.pk, f'{i.subcategoria.categoria.setor.nome} › {i.subcategoria.categoria.nome} › {i.subcategoria.nome} › {i.nome}')
            for i in itens]


@login_required
def codigos_view(request):
    qs, status = _codigos_filtrados(request.GET)
    qs = (qs.select_related('item__subcategoria__categoria__setor')
          .annotate(n_mov=Count('movimentos'), qtd=Sum('movimentos__quantidade')).order_by('-n_mov', 'codigo'))
    pagina = Paginator(qs, 50).get_page(request.GET.get('page'))
    filtro = {k: request.GET.get(k, '') for k in ('q', 'familia', 'status') if request.GET.get(k)}
    ctx = {
        'pagina': pagina, 'status': status, 'q': request.GET.get('q', ''), 'familia': request.GET.get('familia', ''),
        'familias': list(HierCodigo.objects.exclude(familia='').order_by('familia').values_list('familia', flat=True).distinct()),
        'itens': _opcoes_itens(), 'total': pagina.paginator.count, 'filtro_qs': urlencode(filtro),
        'contagens': {
            'pendente': HierCodigo.objects.filter(item__isnull=True, ignorado=False).count(),
            'vinculado': HierCodigo.objects.filter(item__isnull=False).count(),
            'ignorado': HierCodigo.objects.filter(ignorado=True).count(),
        },
    }
    return render(request, 'kpi/hier_codigos.html', ctx)


@login_required
@require_POST
def codigos_acao_view(request):
    """Ação em lote nos códigos marcados (ou em todos os do filtro): vincular a um item, desvincular, ignorar,
    reativar ou salvar fatores de conversão. Recalcula o consumo dos itens afetados."""
    p, acao = request.POST, request.POST.get('acao')
    if p.get('todos_filtro') == '1':
        ids = [c.pk for c in _codigos_filtrados(p)[0]]
    else:
        ids = [x for x in (_int(v) for v in p.getlist('sel')) if x]
    qs = HierCodigo.objects.filter(pk__in=ids)
    afetados = set(qs.exclude(item__isnull=True).values_list('item_id', flat=True))
    if not ids:
        messages.warning(request, 'Marque ao menos um código.')
    elif acao == 'vincular':
        item = HierItem.objects.filter(pk=_int(p.get('item'))).first()
        if item is None:
            messages.warning(request, 'Escolha o item de destino na lista "Vincular a qual item?" antes de vincular. '
                                      'Se a lista estiver vazia, cadastre os itens em Cadastro.')
        else:
            qs.update(item=item, ignorado=False)
            afetados.add(item.pk)
            messages.success(request, f'{len(ids)} código(s) vinculado(s) a "{item.nome}".')
    elif acao == 'desvincular':
        qs.update(item=None)
        messages.success(request, f'{len(ids)} código(s) desvinculado(s).')
    elif acao == 'ignorar':
        qs.update(item=None, ignorado=True)
        messages.success(request, f'{len(ids)} código(s) ignorado(s).')
    elif acao == 'reativar':
        qs.update(ignorado=False)
        messages.success(request, f'{len(ids)} código(s) reativado(s).')
    elif acao == 'fatores':
        n = 0
        for c in qs:
            f = _decimal(p.get(f'fator_{c.pk}'))
            if f is not None and f > 0 and f != c.fator:
                c.fator = f
                c.save(update_fields=['fator'])
                n += 1
        messages.success(request, f'{n} fator(es) atualizado(s).')
    else:
        messages.error(request, 'Ação inválida.')
    if afetados:
        insumos.recalcular(afetados)
    volta = {k: p.get(k) for k in ('q', 'familia', 'status', 'page') if p.get(k)}
    return redirect(reverse('kpi:hier_codigos') + ('?' + urlencode(volta) if volta else ''))


# ----- Cadastro da árvore -----

@login_required
def cadastro_view(request):
    kpis = KpiHierarquico.objects.prefetch_related('setores__categorias__subcategorias__itens__codigos')
    return render(request, 'kpi/hier_cadastro.html', {'kpis': kpis})


def _sincronizar_codigos(request, item, texto):
    """Deixa o item com exatamente os códigos informados (números separados por vírgula/espaço). Retorna os itens afetados."""
    numeros, invalidos = [], []
    for token in re.split(r'[\s,;]+', texto or ''):
        if not token:
            continue
        if token.isdigit() and 0 < int(token) < 2 ** 31:
            numeros.append(int(token))
        else:
            invalidos.append(token)
    afetados = {item.pk}
    for n in numeros:
        codigo, _ = HierCodigo.objects.get_or_create(codigo=n)
        if codigo.item_id and codigo.item_id != item.pk:
            afetados.add(codigo.item_id)
            messages.warning(request, f'O código {n} estava em "{codigo.item.nome}" e foi movido para "{item.nome}".')
        if codigo.item_id != item.pk or codigo.ignorado:
            codigo.item, codigo.ignorado = item, False
            codigo.save(update_fields=['item', 'ignorado'])
    HierCodigo.objects.filter(item=item).exclude(codigo__in=numeros).update(item=None)
    if invalidos:
        messages.warning(request, 'Códigos ignorados por não serem números: ' + ', '.join(invalidos))
    return afetados


@login_required
@require_POST
def cadastro_salvar_view(request):
    """Cria/edita um nó. tipo: kpi | setor | categoria | sub | item; pk (edição) ou pai (criação)."""
    p, tipo = request.POST, request.POST.get('tipo')
    nome = (p.get('nome') or '').strip()
    pk, pai = _int(p.get('pk')), _int(p.get('pai'))
    if not nome:
        messages.error(request, 'Informe o nome.')
        return redirect('kpi:hier_cadastro')
    if tipo not in ('kpi', 'setor', 'categoria', 'sub', 'item'):
        messages.error(request, 'Tipo inválido.')
        return redirect('kpi:hier_cadastro')
    afetados = set()
    try:
        if tipo == 'kpi':
            obj = get_object_or_404(KpiHierarquico, pk=pk) if pk else KpiHierarquico()
            obj.nome, obj.descricao = nome, (p.get('descricao') or '').strip()[:255]
        elif tipo == 'setor':
            obj = get_object_or_404(HierSetor, pk=pk) if pk else HierSetor(kpi=get_object_or_404(KpiHierarquico, pk=pai))
            obj.nome = nome
        elif tipo == 'categoria':
            obj = get_object_or_404(HierCategoria, pk=pk) if pk else HierCategoria(setor=get_object_or_404(HierSetor, pk=pai))
            obj.nome = nome
        elif tipo == 'sub':
            obj = get_object_or_404(HierSubcategoria, pk=pk) if pk else HierSubcategoria(categoria=get_object_or_404(HierCategoria, pk=pai))
            obj.nome = nome
        else:
            obj = get_object_or_404(HierItem, pk=pk) if pk else HierItem(subcategoria=get_object_or_404(HierSubcategoria, pk=pai))
            meta = (p.get('meta') or '').strip()
            if meta and _decimal(meta) is None:
                messages.error(request, 'Meta inválida.')
                return redirect('kpi:hier_cadastro')
            obj.nome, obj.unidade = nome, (p.get('unidade') or '').strip()[:20]
            obj.sentido = p.get('sentido') if p.get('sentido') in dict(HierItem.SENTIDOS) else '<='
            obj.meta = _decimal(meta) if meta else None
        if pk and 'ativo_form' in p and hasattr(obj, 'ativo'):
            obj.ativo = p.get('ativo') == 'on'
        with transaction.atomic():
            obj.save()
            if tipo == 'item' and 'codigos' in p:
                afetados = _sincronizar_codigos(request, obj, p.get('codigos'))
    except IntegrityError:
        messages.error(request, 'Já existe um item com esse nome neste nível.')
        return redirect('kpi:hier_cadastro')
    if afetados:
        insumos.recalcular(afetados)
    messages.success(request, 'Salvo.')
    return redirect('kpi:hier_cadastro')


@login_required
@require_POST
def cadastro_excluir_view(request):
    modelos = {'kpi': KpiHierarquico, 'setor': HierSetor, 'categoria': HierCategoria, 'sub': HierSubcategoria, 'item': HierItem}
    modelo = modelos.get(request.POST.get('tipo'))
    if modelo:
        get_object_or_404(modelo, pk=_int(request.POST.get('pk'))).delete()
        messages.success(request, 'Excluído (inclui o que estava dentro e os consumos lançados; os códigos voltam a ficar sem vínculo).')
    return redirect('kpi:hier_cadastro')
