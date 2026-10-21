import calendar
import datetime
import heapq
import re
from collections import OrderedDict
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils.http import urlencode
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from kpi import calculo, consolidacao
from kpi.forms import IndicadorForm, MedicaoForm
from kpi.models import Indicador, Medicao, Motivo

JANELAS = {'mensal': 12, 'semanal': 6, 'diaria': 15}  # barras exibidas por vez
LIMITES = {'mensal': 12, 'semanal': 52, 'diaria': 120}  # histórico enviado ao navegador (navegável pelas setas)
PERIODOS_MOTIVOS = [('30', 'Últimos 30 dias'), ('90', 'Últimos 90 dias'), ('365', 'Últimos 12 meses'), ('0', 'Todo o período'),
                    ('mes', 'Mês específico…'), ('periodo', 'Período específico…')]


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


def _serie(ind, gran, medicoes, meta=None):
    meds = heapq.nlargest(LIMITES[gran], (m for m in medicoes if m.granularidade == gran), key=lambda m: m.periodo)
    meds.reverse()
    return {
        'labels': [_rotulo(gran, m.periodo) for m in meds],
        'valores': [float(m.valor) for m in meds],
        'janela': JANELAS[gran],
        'meta': float(ind.meta if meta is None else meta),
        'sentido': ind.sentido,
        'entradas': [
            {'id': m.pk, 'data': m.periodo.isoformat(), 'valor': str(m.valor), 'obs': m.observacao, 'dados': m.dados or {}}
            for m in meds
        ],
    }


def _filtro_motivos(params):
    """Interpreta o filtro de período da tabela de motivos (GET). Retorna (inicio, fim, estado para a tela)."""
    mot = params.get('mot', '90')
    if mot not in dict(PERIODOS_MOTIVOS):
        mot = '90'
    mes, de, ate = params.get('mes', ''), params.get('de', ''), params.get('ate', '')
    inicio = fim = None
    if mot == 'mes':
        try:
            ano, m = (int(x) for x in mes.split('-'))
            inicio = datetime.date(ano, m, 1)
            fim = datetime.date(ano, m, calendar.monthrange(ano, m)[1])
        except (ValueError, TypeError):
            mot, mes = '0', ''
    elif mot == 'periodo':
        try:
            inicio = datetime.date.fromisoformat(de) if de else None
            fim = datetime.date.fromisoformat(ate) if ate else None
        except ValueError:
            inicio = fim = None
            de = ate = ''
        if inicio and fim and inicio > fim:
            inicio, fim, de, ate = fim, inicio, ate, de
    elif mot != '0':
        inicio = timezone.localdate() - datetime.timedelta(days=int(mot))
    qs = {k: v for k, v in (('mot', mot), ('mes', mes if mot == 'mes' else ''), ('de', de if mot == 'periodo' else ''),
                            ('ate', ate if mot == 'periodo' else '')) if v}
    fmt = lambda d: d.strftime('%d/%m/%Y')
    if mot == 'mes':
        rotulo = f'Mês {mes[5:7]}/{mes[:4]}'
    elif mot == 'periodo':
        rotulo = ('Período ' + ' – '.join(fmt(d) if d else '…' for d in (inicio, fim))) if (inicio or fim) else 'Todo o período'
    else:
        rotulo = dict(PERIODOS_MOTIVOS)[mot]
    return inicio, fim, {'mot': mot, 'mes': mes, 'de': de, 'ate': ate, 'qs': urlencode(qs), 'rotulo': rotulo}


DIAS_SEMANA = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']


def _vizinho(gran, d, sentido):
    """Período anterior (-1) ou seguinte (+1), já normalizado."""
    if gran == 'diaria':
        return d + datetime.timedelta(days=sentido)
    if gran == 'semanal':
        return d + datetime.timedelta(days=7 * sentido)
    ano, mes = d.year, d.month + sentido
    if mes == 0:
        ano, mes = ano - 1, 12
    elif mes == 13:
        ano, mes = ano + 1, 1
    return datetime.date(ano, mes, calendar.monthrange(ano, mes)[1])


def _rotulo_longo(gran, d):
    if gran == 'diaria':
        return f'Dia {d:%d/%m/%Y} ({DIAS_SEMANA[d.weekday()]})'
    if gran == 'semanal':
        return f'Semana {d:%d/%m} – {d + datetime.timedelta(days=6):%d/%m/%Y} (S{d.isocalendar()[1]})'
    return f'Mês {d:%m/%Y}'


def _url_nav(get, ind_pk, setor_id, remover=(), **mudar):
    """Link do painel mantendo o filtro atual, com o indicador/setor desta aba e as mudanças pedidas."""
    p = get.copy()
    p['ind'] = ind_pk
    if setor_id:
        p['setor'] = setor_id
    else:
        p.pop('setor', None)
    for k in remover:
        p.pop(k, None)
    for k, v in mudar.items():
        p[k] = v
    return '?' + p.urlencode()


def _motivos(ind, inicio, fim, setor_id, get, rotulo_acum):
    """Por granularidade: Top motivos (somados) de UM período navegável (dia/semana/mês) ou acumulado
    (filtro de período), e os lançamentos agrupados por período.
    Visão geral (setor_id=None) considera todos os motivos, de qualquer setor; com setor, só os dele."""
    nomes = {s.pk: s.nome for s in ind.setores.all()}
    base = [m for m in ind.motivos.all() if setor_id is None or m.setor_id == setor_id]
    for m in base:
        m.setor_nome = nomes.get(m.setor_id, '')
    hoje = timezone.localdate()
    saida = []
    for gran, _ in Medicao.GRANULARIDADES[::-1]:  # diário, semanal, mensal
        param = 'p_' + gran
        do_gran = [m for m in base if m.granularidade == gran]
        acum = get.get(param) == 'acum'
        ref = None
        if not acum:
            try:
                ref = _normalizar(gran, datetime.date.fromisoformat(get.get(param, '')))
            except ValueError:
                ref = None
            if ref is None:  # padrão: período mais recente com motivos (ou o atual, se não houver nenhum)
                ref = max((_normalizar(gran, m.data) for m in do_gran), default=None) or _normalizar(gran, hoje)
            itens = [m for m in do_gran if _normalizar(gran, m.data) == ref]
        else:
            itens = [m for m in do_gran if (not inicio or m.data >= inicio) and (not fim or m.data <= fim)]
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
        ctx = {'ind_pk': ind.pk, 'setor_id': setor_id}
        nav = {'acum': acum, 'rotulo': rotulo_acum if acum else _rotulo_longo(gran, ref), 'ref': ref}
        if acum:
            nav['por_periodo'] = _url_nav(get, ind.pk, setor_id, remover=(param,), mtab=gran)
        else:
            nav['prev'] = _url_nav(get, ind.pk, setor_id, mtab=gran, **{param: _vizinho(gran, ref, -1).isoformat()})
            nav['next'] = _url_nav(get, ind.pk, setor_id, mtab=gran, **{param: _vizinho(gran, ref, 1).isoformat()})
            nav['recente'] = _url_nav(get, ind.pk, setor_id, remover=(param,), mtab=gran)
            nav['acumulado'] = _url_nav(get, ind.pk, setor_id, mtab=gran, **{param: 'acum'})
        saida.append({
            'gran': gran,
            'nome': dict(Medicao.GRANULARIDADES)[gran].replace('Diária', 'Diário'),
            'top': top,
            'nav': nav,
            'data_ref': ref.isoformat() if ref and not acum else '',
            'periodos': [
                {'data': d, 'rotulo': _rotulo(gran, d), 'itens': sorted(v, key=lambda x: -x.quantidade),
                 'total': sum((x.quantidade for x in v), Decimal(0))}
                for d, v in sorted(periodos.items(), reverse=True)
            ],
        })
    return saida


@login_required
def painel_view(request):
    inicio, fim, filtro = _filtro_motivos(request.GET)
    abas, charts, motivos_js, campos_js = [], {}, {}, {}
    ativo_req = request.GET.get('ind')
    for ind in Indicador.objects.filter(ativo=True).prefetch_related('medicoes', 'motivos', 'setores'):
        todas = list(ind.medicoes.all())
        setores = list(ind.setores.all())
        # setor selecionado só vale para o indicador da aba ativa; sem setor = acompanhamento geral
        setor = None
        if str(ind.pk) == ativo_req and request.GET.get('setor', '').isdigit():
            setor = next((x for x in setores if x.pk == int(request.GET['setor'])), None)
        setor_id = setor.pk if setor else None
        meta = setor.meta_efetiva if setor else ind.meta
        meds = [m for m in todas if m.setor_id == setor_id]
        mensais = sorted((m for m in meds if m.granularidade == 'mensal'), key=lambda m: m.periodo, reverse=True)
        ultima = mensais[0] if mensais else None
        gerais = sorted((m for m in todas if m.setor_id is None and m.granularidade == 'mensal'),
                        key=lambda m: m.periodo, reverse=True)
        motivos_tabs = [t for t in _motivos(ind, inicio, fim, setor_id, request.GET, filtro['rotulo'])
                        if ind.permite_motivos(t['gran'])]
        mtab = request.GET.get('mtab') if str(ind.pk) == ativo_req else None
        if motivos_tabs:
            ativa = mtab if mtab in [t['gran'] for t in motivos_tabs] else motivos_tabs[0]['gran']
            for t in motivos_tabs:
                t['ativo'] = t['gran'] == ativa
        campos_js[str(ind.pk)] = {
            'campos': calculo.lista_campos(ind), 'formula': ind.formula,
            'motivos': [g for g in ('diaria', 'semanal', 'mensal') if ind.permite_motivos(g)],
            'unidade': ind.unidade, 'setor': setor_id or '', 'setor_nome': setor.nome if setor else '',
        }
        charts[str(ind.pk)] = {g: _serie(ind, g, meds, meta) for g in ind.graficos()}
        motivos_js[str(ind.pk)] = [
            {'g': m.granularidade, 'd': m.data.isoformat(), 'desc': m.descricao, 'qtd': str(m.quantidade)}
            for m in ind.motivos.all() if m.setor_id == setor_id
        ]
        abas.append({
            'ind': ind,
            'ultima': ultima,
            'atingiu': ind.atingiu(gerais[0].valor) if gerais else None,  # situação geral (cards e marcador da aba)
            'atingiu_escopo': ind.atingiu(ultima.valor, meta) if ultima else None,
            'setores': setores,
            'setor': setor,
            'meta': meta,
            'motivos_tabs': motivos_tabs,
        })
    ativo_pk = request.GET.get('ind')
    if not any(str(a['ind'].pk) == ativo_pk for a in abas) and abas:
        ativo_pk = str(abas[0]['ind'].pk)
    total = len(abas)
    ok = sum(1 for a in abas if a['atingiu'] is True)
    fora = sum(1 for a in abas if a['atingiu'] is False)
    return render(request, 'kpi/painel.html', {
        'abas': abas, 'charts': charts, 'campos_js': campos_js, 'motivos_js': motivos_js, 'ativo_pk': ativo_pk, 'filtro': filtro, 'periodos_motivos': PERIODOS_MOTIVOS,
        'total': total, 'ok': ok, 'fora': fora, 'sem_dado': total - ok - fora,
    })


def _voltar(ind_pk, extra='', setor=None):
    extra += f'&setor={setor.pk}' if setor else ''
    return redirect(f"{reverse('kpi:painel')}?ind={ind_pk}{extra}")


def _setor_do_post(request, ind):
    """Setor enviado no formulário (vazio = geral). Retorna (setor, valido)."""
    bruto = (request.POST.get('setor') or '').strip()
    if not bruto:
        return None, True
    setor = ind.setores.filter(pk=bruto).first() if bruto.isdigit() else None
    return setor, setor is not None


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
        form.salvar_setores(obj)
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
    setor, setor_ok = _setor_do_post(request, ind)
    if not setor_ok:
        messages.error(request, 'Setor inválido para este indicador.')
        return _voltar(ind.pk)
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
        return _voltar(ind.pk, setor=setor)
    gran = form.cleaned_data['granularidade']
    if not ind.permite_valor(gran):
        messages.error(request, 'Este indicador não tem o gráfico semanal/diário habilitado.')
        return _voltar(ind.pk, setor=setor)
    periodo = _normalizar(gran, form.cleaned_data['periodo'])
    Medicao.objects.update_or_create(
        indicador=ind, setor=setor, periodo=periodo, granularidade=gran,
        defaults={
            'valor': form.cleaned_data['valor'],
            'observacao': form.cleaned_data['observacao'],
            'dados': {k: str(v) for k, v in dados.items()},
            'registrado_por': request.user,
        },
    )
    if gran == 'diaria':
        consolidacao.consolidar_valores(ind, setor.pk if setor else None, [periodo], request.user)
    messages.success(request, f'Informação de {_rotulo(gran, periodo)} salva' + (f' ({setor.nome}).' if setor else '.'))
    return _voltar(ind.pk, setor=setor)


@login_required
@require_POST
def medicao_excluir_view(request, pk):
    m = get_object_or_404(Medicao, pk=pk)
    ind_pk, setor = m.indicador_id, m.setor
    m.delete()
    if m.granularidade == 'diaria':
        consolidacao.consolidar_valores(m.indicador, m.setor_id, [m.periodo], request.user)
    messages.success(request, 'Informação excluída.')
    return _voltar(ind_pk, setor=setor)


@login_required
@require_POST
def motivo_salvar_view(request, pk):
    """Grava os motivos de um período (dia/semana/mês): substitui os existentes pelos enviados."""
    ind = get_object_or_404(Indicador, pk=pk)
    setor, setor_ok = _setor_do_post(request, ind)
    if not setor_ok:
        messages.error(request, 'Setor inválido para este indicador.')
        return _voltar(ind.pk, '&mot=0')
    gran = request.POST.get('granularidade')
    if gran not in dict(Medicao.GRANULARIDADES):
        messages.error(request, 'Selecione o tipo de período.')
        return _voltar(ind.pk, '&mot=0', setor)
    if not ind.permite_motivos(gran):
        messages.error(request, 'A tabela de motivos deste período não está habilitada para o indicador.')
        return _voltar(ind.pk, '&mot=0', setor)
    try:
        data = _normalizar(gran, datetime.date.fromisoformat(request.POST.get('data', '')))
    except ValueError:
        messages.error(request, 'Informe uma data válida.')
        return _voltar(ind.pk, '&mot=0', setor)
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
        ind.motivos.filter(granularidade=gran, data=data, setor=setor).delete()
        Motivo.objects.bulk_create([
            Motivo(indicador=ind, setor=setor, granularidade=gran, data=data, descricao=d, quantidade=q, registrado_por=request.user)
            for d, q in linhas
        ])
    if linhas:
        messages.success(request, f'{len(linhas)} motivo(s) salvo(s) para {_rotulo(gran, data)}.')
    else:
        messages.success(request, f'Motivos de {_rotulo(gran, data)} removidos.')
    return _voltar(ind.pk, '&mot=0', setor)


@login_required
def importar_view(request):
    from kpi import importacao
    resultado = None
    gran = request.POST.get('granularidade', 'mensal')
    tipo = request.POST.get('tipo', 'valores')
    if request.method == 'POST':
        arquivo = request.FILES.get('arquivo')
        if gran not in importacao.NOMES or tipo not in importacao.TIPOS or not arquivo:
            messages.error(request, 'Escolha o período e envie o arquivo .xlsx.')
        else:
            resultado = importacao.importar(arquivo, gran, request.user, tipo)
    return render(request, 'kpi/importar.html', {
        'resultado': resultado, 'gran': gran, 'tipo': tipo, 'tipos': importacao.TIPOS,
        'indicadores': Indicador.objects.filter(ativo=True).prefetch_related('setores')})


@login_required
def modelo_importacao_view(request, tipo, gran):
    from django.http import Http404, HttpResponse
    from kpi import importacao
    if gran not in importacao.NOMES or tipo not in importacao.TIPOS:
        raise Http404
    ind = get_object_or_404(Indicador, pk=request.GET['ind']) if request.GET.get('ind', '').isdigit() else None
    resp = HttpResponse(
        importacao.gerar_modelo(gran, ind, tipo),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    sufixo = '_' + re.sub(r'[^a-z0-9]+', '_', ind.nome.lower()).strip('_') if ind else ''
    resp['Content-Disposition'] = f'attachment; filename="modelo_kpi_{tipo}_{importacao.NOMES[gran].lower()}{sufixo}.xlsx"'
    return resp
