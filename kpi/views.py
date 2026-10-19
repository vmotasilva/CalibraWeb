import calendar
import datetime
import re
from collections import OrderedDict
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from kpi import calculo
from kpi.forms import IndicadorForm, MedicaoForm
from kpi.models import Indicador, Medicao, Motivo

JANELAS = {'mensal': 12, 'semanal': 12, 'diaria': 31}
PERIODOS_MOTIVOS = [(30, 'Últimos 30 dias'), (90, 'Últimos 90 dias'), (365, 'Últimos 12 meses'), (0, 'Todo o período')]


def _normalizar(gran, d):
    """Mensal -> último dia do mês; semanal -> segunda-feira da semana; diária -> a própria data."""
    if gran == 'mensal':
        return d.replace(day=calendar.monthrange(d.year, d.month)[1])
    if gran == 'semanal':
        return d - datetime.timedelta(days=d.weekday())
    return d


def _rotulo(gran, d):
    if gran == 'mensal':
        return d.strftime('%m/%Y')
    if gran == 'semanal':
        return f'S{d.isocalendar()[1]} ({d:%d/%m})'
    return d.strftime('%d/%m')


def _serie(ind, gran, medicoes):
    meds = sorted((m for m in medicoes if m.granularidade == gran), key=lambda m: m.periodo)
    meds = meds[-JANELAS[gran]:]
    return {
        'labels': [_rotulo(gran, m.periodo) for m in meds],
        'valores': [float(m.valor) for m in meds],
        'meta': float(ind.meta),
        'sentido': ind.sentido,
        'entradas': [
            {'id': m.pk, 'data': m.periodo.isoformat(), 'valor': str(m.valor), 'obs': m.observacao, 'dados': m.dados or {}}
            for m in meds
        ],
    }


def _motivos(ind, dias):
    """Por granularidade: Top motivos (somados) e lançamentos agrupados por período."""
    corte = timezone.localdate() - datetime.timedelta(days=dias) if dias else None
    todos = [m for m in ind.motivos.all() if not corte or m.data >= corte]
    saida = OrderedDict()
    for gran, _ in Medicao.GRANULARIDADES[::-1]:  # diário, semanal, mensal
        itens = [m for m in todos if m.granularidade == gran]
        agregados = OrderedDict()
        periodos = OrderedDict()
        for m in itens:
            chave = m.descricao.strip().lower()
            ag = agregados.setdefault(chave, {'descricao': m.descricao.strip(), 'total': Decimal(0)})
            ag['total'] += m.quantidade
            periodos.setdefault(m.data, []).append(m)
        top = sorted(agregados.values(), key=lambda a: a['total'], reverse=True)[:10]
        soma = sum((a['total'] for a in agregados.values()), Decimal(0))
        for a in top:
            a['pct'] = float(a['total'] / soma * 100) if soma else 0
        saida[gran] = {
            'gran': gran,
            'nome': dict(Medicao.GRANULARIDADES)[gran].replace('Diária', 'Diário'),
            'top': top,
            'periodos': [
                {'data': d, 'rotulo': _rotulo(gran, d), 'itens': sorted(v, key=lambda x: -x.quantidade),
                 'total': sum((x.quantidade for x in v), Decimal(0))}
                for d, v in sorted(periodos.items(), reverse=True)
            ],
        }
    return list(saida.values())


@login_required
def painel_view(request):
    try:
        dias = int(request.GET.get('mot', 90))
    except ValueError:
        dias = 90
    if dias not in dict(PERIODOS_MOTIVOS):
        dias = 90
    abas, charts, motivos_js, campos_js = [], {}, {}, {}
    for ind in Indicador.objects.filter(ativo=True).prefetch_related('medicoes', 'motivos'):
        meds = list(ind.medicoes.all())
        mensais = sorted((m for m in meds if m.granularidade == 'mensal'), key=lambda m: m.periodo, reverse=True)
        ultima = mensais[0] if mensais else None
        motivos_tabs = [t for t in _motivos(ind, dias) if ind.permite_motivos(t['gran'])]
        grans = ind.graficos()
        campos_js[str(ind.pk)] = {
            'campos': calculo.lista_campos(ind), 'formula': ind.formula,
            'motivos': [g for g in ('diaria', 'semanal', 'mensal') if ind.permite_motivos(g)],
            'unidade': ind.unidade,
        }
        charts[str(ind.pk)] = {g: _serie(ind, g, meds) for g in grans}
        motivos_js[str(ind.pk)] = [
            {'g': m.granularidade, 'd': m.data.isoformat(), 'desc': m.descricao, 'qtd': str(m.quantidade)}
            for m in ind.motivos.all()
        ]
        abas.append({
            'ind': ind,
            'ultima': ultima,
            'atingiu': ind.atingiu(ultima.valor) if ultima else None,
            'motivos_tabs': motivos_tabs,
        })
    ativo_pk = request.GET.get('ind')
    if not any(str(a['ind'].pk) == ativo_pk for a in abas) and abas:
        ativo_pk = str(abas[0]['ind'].pk)
    total = len(abas)
    ok = sum(1 for a in abas if a['atingiu'] is True)
    fora = sum(1 for a in abas if a['atingiu'] is False)
    return render(request, 'kpi/painel.html', {
        'abas': abas, 'charts': charts, 'campos_js': campos_js, 'motivos_js': motivos_js, 'ativo_pk': ativo_pk, 'mot_dias': dias, 'periodos_motivos': PERIODOS_MOTIVOS,
        'total': total, 'ok': ok, 'fora': fora, 'sem_dado': total - ok - fora,
    })


def _voltar(ind_pk, extra=''):
    return redirect(f"{reverse('kpi:painel')}?ind={ind_pk}{extra}")


@login_required
def indicadores_view(request):
    return render(request, 'kpi/indicadores.html', {'indicadores': Indicador.objects.all()})


@login_required
def indicador_form_view(request, pk=None):
    ind = get_object_or_404(Indicador, pk=pk) if pk else None
    form = IndicadorForm(request.POST or None, instance=ind)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        if not ind:
            obj.criado_por = request.user
        obj.save()
        messages.success(request, 'Indicador salvo.')
        return _voltar(obj.pk)
    return render(request, 'kpi/indicador_form.html', {'form': form, 'ind': ind})


@login_required
@require_POST
def indicador_mover_view(request, pk):
    """Move o indicador uma posição para cima/baixo na ordem das abas (renumera 1..n)."""
    lista = list(Indicador.objects.all())
    idx = next((i for i, x in enumerate(lista) if x.pk == pk), None)
    if idx is None:
        return redirect('kpi:indicadores')
    alvo = idx - 1 if request.POST.get('dir') == 'up' else idx + 1
    if 0 <= alvo < len(lista):
        lista[idx], lista[alvo] = lista[alvo], lista[idx]
    for n, x in enumerate(lista, start=1):
        if x.ordem != n:
            Indicador.objects.filter(pk=x.pk).update(ordem=n)
    return redirect('kpi:indicadores')


@login_required
def indicador_detalhe_view(request, pk):
    return _voltar(pk)


@login_required
@require_POST
def indicador_excluir_view(request, pk):
    get_object_or_404(Indicador, pk=pk).delete()
    messages.success(request, 'Indicador excluído.')
    return redirect('kpi:indicadores')


@login_required
@require_POST
def medicao_salvar_view(request, pk):
    ind = get_object_or_404(Indicador, pk=pk)
    post = request.POST.copy()
    campos = calculo.lista_campos(ind)
    dados = {}
    for n, nome in enumerate(campos):
        bruto = (post.get(f'campo_{n}') or '').strip().replace(',', '.')
        if bruto:
            try:
                dados[nome] = Decimal(bruto)
            except Exception:
                messages.error(request, f'Valor inválido no campo "{nome}".')
                return _voltar(ind.pk)
    if not (post.get('valor') or '').strip() and ind.formula:
        try:
            post['valor'] = str(calculo.calcular(ind.formula, dados))
        except (ValueError, ZeroDivisionError) as e:
            messages.error(request, f'Não foi possível calcular o valor: {e}')
            return _voltar(ind.pk)
    form = MedicaoForm(post)
    if not form.is_valid():
        messages.error(request, 'Informe data e valor válidos.')
        return _voltar(ind.pk)
    gran = form.cleaned_data['granularidade']
    if not ind.permite_valor(gran):
        messages.error(request, 'Este indicador não tem o gráfico semanal/diário habilitado.')
        return _voltar(ind.pk)
    periodo = _normalizar(gran, form.cleaned_data['periodo'])
    Medicao.objects.update_or_create(
        indicador=ind, periodo=periodo, granularidade=gran,
        defaults={
            'valor': form.cleaned_data['valor'],
            'observacao': form.cleaned_data['observacao'],
            'dados': {k: str(v) for k, v in dados.items()},
            'registrado_por': request.user,
        },
    )
    messages.success(request, f'Informação de {_rotulo(gran, periodo)} salva.')
    return _voltar(ind.pk)


@login_required
@require_POST
def medicao_excluir_view(request, pk):
    m = get_object_or_404(Medicao, pk=pk)
    ind_pk = m.indicador_id
    m.delete()
    messages.success(request, 'Informação excluída.')
    return _voltar(ind_pk)


@login_required
@require_POST
def motivo_salvar_view(request, pk):
    """Grava os motivos de um período (dia/semana/mês): substitui os existentes pelos enviados."""
    ind = get_object_or_404(Indicador, pk=pk)
    gran = request.POST.get('granularidade')
    if gran not in dict(Medicao.GRANULARIDADES):
        messages.error(request, 'Selecione o tipo de período.')
        return _voltar(ind.pk, '&mot=0')
    if not ind.permite_motivos(gran):
        messages.error(request, 'A tabela de motivos deste período não está habilitada para o indicador.')
        return _voltar(ind.pk, '&mot=0')
    try:
        data = _normalizar(gran, datetime.date.fromisoformat(request.POST.get('data', '')))
    except ValueError:
        messages.error(request, 'Informe uma data válida.')
        return _voltar(ind.pk, '&mot=0')
    linhas = []
    for desc, qtd in zip(request.POST.getlist('descricao'), request.POST.getlist('quantidade')):
        desc = desc.strip()[:200]
        if not desc:
            continue
        try:
            q = Decimal((qtd or '1').replace(',', '.'))
        except Exception:
            q = Decimal(1)
        linhas.append((desc, q))
    with transaction.atomic():
        ind.motivos.filter(granularidade=gran, data=data).delete()
        Motivo.objects.bulk_create([
            Motivo(indicador=ind, granularidade=gran, data=data, descricao=d, quantidade=q, registrado_por=request.user)
            for d, q in linhas
        ])
    if linhas:
        messages.success(request, f'{len(linhas)} motivo(s) salvo(s) para {_rotulo(gran, data)}.')
    else:
        messages.success(request, f'Motivos de {_rotulo(gran, data)} removidos.')
    return _voltar(ind.pk, '&mot=0')


@login_required
def importar_view(request):
    from kpi import importacao
    resultado = None
    gran = request.POST.get('granularidade', 'mensal')
    if request.method == 'POST':
        arquivo = request.FILES.get('arquivo')
        if gran not in importacao.NOMES or not arquivo:
            messages.error(request, 'Escolha o tipo do modelo e envie o arquivo .xlsx.')
        else:
            resultado = importacao.importar(arquivo, gran, request.user)
    return render(request, 'kpi/importar.html', {
        'resultado': resultado, 'gran': gran, 'indicadores': Indicador.objects.filter(ativo=True)})


@login_required
def modelo_importacao_view(request, gran):
    from django.http import Http404, HttpResponse
    from kpi import importacao
    if gran not in importacao.NOMES:
        raise Http404
    ind = get_object_or_404(Indicador, pk=request.GET['ind']) if request.GET.get('ind', '').isdigit() else None
    resp = HttpResponse(
        importacao.gerar_modelo(gran, ind),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    sufixo = '_' + re.sub(r'[^a-z0-9]+', '_', ind.nome.lower()).strip('_') if ind else ''
    resp['Content-Disposition'] = f'attachment; filename="modelo_kpi_{importacao.NOMES[gran].lower()}{sufixo}.xlsx"'
    return resp
