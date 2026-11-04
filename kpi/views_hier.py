"""KPI por setor (hierárquico): KPI > Setor > Categoria (máquina) > Subcategoria (item), com consumo mensal e meta por item."""
import calendar
import datetime
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.views.decorators.http import require_POST

from kpi.models import HierCategoria, HierConsumo, HierSetor, HierSubcategoria, KpiHierarquico

JANELA_MESES = 12


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


def _serie(itens, meses, consumos):
    """Um item: consumo real e a meta dele. Vários itens: média do % da meta (consumo ÷ meta), pois as unidades diferem."""
    por_item = {}
    for c in consumos:
        por_item.setdefault(c.subcategoria_id, {})[c.periodo] = c.valor
    rotulos = [f'{m:%m/%Y}' for m in meses]
    if len(itens) == 1:
        item = itens[0]
        dados = por_item.get(item.pk, {})
        return {'modo': 'valor', 'labels': rotulos,
                'valores': [float(dados[m]) if m in dados else None for m in meses],
                'meta': float(item.meta) if item.meta is not None else None,
                'unidade': item.unidade, 'titulo': f'Consumo ({item.unidade})' if item.unidade else 'Consumo'}
    valores = []
    for m in meses:
        pcts = [por_item[i.pk][m] / i.meta * 100 for i in itens
                if i.meta and i.pk in por_item and m in por_item[i.pk]]
        valores.append(round(float(sum(pcts) / len(pcts)), 1) if pcts else None)
    return {'modo': 'percentual', 'labels': rotulos, 'valores': valores, 'meta': 100.0, 'unidade': '%',
            'titulo': '% da meta de consumo (média dos itens com meta)'}


@login_required
def painel_view(request):
    kpis = list(KpiHierarquico.objects.filter(ativo=True))
    kpi = next((k for k in kpis if k.pk == _int(request.GET.get('kpi'))), kpis[0] if kpis else None)
    ctx = {'kpis': kpis, 'kpi': kpi}
    if not kpi:
        return render(request, 'kpi/hier_painel.html', ctx)

    setores = list(kpi.setores.all())
    setor = next((s for s in setores if s.pk == _int(request.GET.get('setor'))), None)
    categorias = list(setor.categorias.all()) if setor else []
    categoria = next((c for c in categorias if c.pk == _int(request.GET.get('categoria'))), None)
    subs = list(categoria.subcategorias.filter(ativo=True)) if categoria else []
    sub = next((s for s in subs if s.pk == _int(request.GET.get('sub'))), None)

    itens_qs = HierSubcategoria.objects.filter(ativo=True, categoria__setor__kpi=kpi).select_related('categoria__setor')
    if sub:
        itens_qs = itens_qs.filter(pk=sub.pk)
    elif categoria:
        itens_qs = itens_qs.filter(categoria=categoria)
    elif setor:
        itens_qs = itens_qs.filter(categoria__setor=setor)
    itens = list(itens_qs.order_by('categoria__setor__ordem', 'categoria__ordem', 'ordem', 'nome'))

    fim = _mes_param(request.GET.get('mes'))
    meses = _meses_ate(fim, JANELA_MESES)
    consumos = list(HierConsumo.objects.filter(subcategoria__in=itens, periodo__in=meses))
    atual = {c.subcategoria_id: c for c in consumos if c.periodo == fim}
    linhas = []
    for i in itens:
        c = atual.get(i.pk)
        v = c.valor if c else None
        linhas.append({'item': i, 'consumo': v, 'obs': c.observacao if c else '',
                       'pct': round(v / i.meta * 100) if v is not None and i.meta else None,
                       'ok': i.atingiu(v)})
    com_meta = [l for l in linhas if l['ok'] is not None]
    ctx.update(
        setores=setores, setor=setor, categorias=categorias, categoria=categoria, subs=subs, sub=sub,
        linhas=linhas, mes=fim, mes_valor=f'{fim:%Y-%m}', serie=_serie(itens, meses, consumos) if itens else None,
        dentro=sum(1 for l in com_meta if l['ok']), fora=sum(1 for l in com_meta if not l['ok']),
        sem_lancamento=sum(1 for l in linhas if l['consumo'] is None),
    )
    return render(request, 'kpi/hier_painel.html', ctx)


def _voltar_painel(post):
    params = {k: post.get(k) for k in ('kpi', 'setor', 'categoria', 'sub', 'mes') if post.get(k)}
    return redirect(reverse('kpi:hier_painel') + ('?' + urlencode(params) if params else ''))


@login_required
@require_POST
def lancar_view(request):
    """Grava o consumo do mês de cada item enviado (campos valor_<id>). Campo em branco não altera nada."""
    periodo = _mes_param(request.POST.get('mes'))
    gravados = 0
    for chave, bruto in request.POST.items():
        if not chave.startswith('valor_') or not (bruto or '').strip():
            continue
        item = HierSubcategoria.objects.filter(pk=_int(chave[6:])).first()
        valor = _decimal(bruto)
        if not item or valor is None or valor < 0:
            messages.error(request, f'Valor inválido para "{item or chave}".')
            continue
        HierConsumo.objects.update_or_create(
            subcategoria=item, periodo=periodo,
            defaults={'valor': valor, 'registrado_por': request.user,
                      'observacao': (request.POST.get(f'obs_{item.pk}') or '').strip()[:255]})
        gravados += 1
    if gravados:
        messages.success(request, f'Consumo de {periodo:%m/%Y} salvo ({gravados} item(ns)).')
    return _voltar_painel(request.POST)


@login_required
@require_POST
def consumo_excluir_view(request, sub_pk):
    """Exclui o consumo de um item no mês informado."""
    periodo = _mes_param(request.POST.get('mes'))
    apagados, _ = HierConsumo.objects.filter(subcategoria_id=sub_pk, periodo=periodo).delete()
    if apagados:
        messages.success(request, 'Consumo excluído.')
    return _voltar_painel(request.POST)


# ----- Cadastro da árvore -----

@login_required
def cadastro_view(request):
    kpis = KpiHierarquico.objects.prefetch_related('setores__categorias__subcategorias')
    return render(request, 'kpi/hier_cadastro.html', {'kpis': kpis})


@login_required
@require_POST
def cadastro_salvar_view(request):
    """Cria/edita um nó. tipo: kpi | setor | categoria | sub; pk (edição) ou pai (criação)."""
    p, tipo = request.POST, request.POST.get('tipo')
    nome = (p.get('nome') or '').strip()
    pk, pai = _int(p.get('pk')), _int(p.get('pai'))
    if not nome:
        messages.error(request, 'Informe o nome.')
        return redirect('kpi:hier_cadastro')
    if tipo not in ('kpi', 'setor', 'categoria', 'sub'):
        messages.error(request, 'Tipo inválido.')
        return redirect('kpi:hier_cadastro')
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
        else:
            obj = get_object_or_404(HierSubcategoria, pk=pk) if pk else HierSubcategoria(categoria=get_object_or_404(HierCategoria, pk=pai))
            meta = (p.get('meta') or '').strip()
            if meta and _decimal(meta) is None:
                messages.error(request, 'Meta inválida.')
                return redirect('kpi:hier_cadastro')
            obj.nome, obj.unidade = nome, (p.get('unidade') or '').strip()[:20]
            obj.meta = _decimal(meta) if meta else None
        if pk and 'ativo_form' in p and hasattr(obj, 'ativo'):
            obj.ativo = p.get('ativo') == 'on'
        with transaction.atomic():
            obj.save()
    except IntegrityError:
        messages.error(request, 'Já existe um item com esse nome neste nível.')
        return redirect('kpi:hier_cadastro')
    messages.success(request, 'Salvo.')
    return redirect('kpi:hier_cadastro')


@login_required
@require_POST
def cadastro_excluir_view(request):
    modelos = {'kpi': KpiHierarquico, 'setor': HierSetor, 'categoria': HierCategoria, 'sub': HierSubcategoria}
    modelo = modelos.get(request.POST.get('tipo'))
    if modelo:
        get_object_or_404(modelo, pk=_int(request.POST.get('pk'))).delete()
        messages.success(request, 'Excluído (inclui o que estava dentro e os consumos lançados).')
    return redirect('kpi:hier_cadastro')
