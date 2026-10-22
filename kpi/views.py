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

from kpi import calculo, consolidacao, pendencias
from kpi.forms import IndicadorForm, MedicaoForm
from kpi.models import Indicador, Medicao, Motivo
from shared.permissions import has_view_access

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
    abas, charts, motivos_js, campos_js, analises_js = [], {}, {}, {}, {}
    ativo_req = request.GET.get('ind')
    for ind in Indicador.objects.filter(ativo=True).prefetch_related('medicoes', 'motivos', 'setores', 'analises__itens'):
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
            'resp_analise': _nome_usuario(pendencias.responsavel_do_escopo(ind, setor)),
        }
        charts[str(ind.pk)] = {g: _serie(ind, g, meds, meta) for g in ind.graficos()}
        analises_js[str(ind.pk)] = {}
        for a in ind.analises.all():
            if a.setor_id == setor_id:
                analises_js[str(ind.pk)].setdefault(a.granularidade, {})[a.periodo.isoformat()] = _resumo_registro(a)
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
        'abas': abas, 'charts': charts, 'campos_js': campos_js, 'analises_js': analises_js, 'motivos_js': motivos_js, 'ativo_pk': ativo_pk, 'filtro': filtro, 'periodos_motivos': PERIODOS_MOTIVOS,
        'total': total, 'ok': ok, 'fora': fora, 'sem_dado': total - ok - fora,
        'pode_editar_dados': has_view_access(request.user, 'kpi:medicao_salvar'),
        'pode_excluir_dados': has_view_access(request.user, 'kpi:medicao_excluir'),
        'pode_analisar': has_view_access(request.user, 'kpi:analise_salvar'),
        'pode_dispensar': has_view_access(request.user, 'kpi:analise_dispensar'),
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


@login_required
def colagem_view(request):
    """Registro por colagem: escolhe o modelo, o período e cola os números; confere antes de gravar."""
    from kpi import colagem
    from kpi.models import ModeloColagem
    modelos = list(ModeloColagem.objects.all())
    ctx = {'modelos': modelos, 'gran': request.POST.get('granularidade', 'diaria'),
           'data': request.POST.get('data') or timezone.localdate().isoformat(),
           'modelo_id': request.POST.get('modelo', ''), 'texto': request.POST.get('texto', '')}
    if request.method == 'POST':
        modelo = next((m for m in modelos if str(m.pk) == ctx['modelo_id']), None)
        try:
            data = datetime.date.fromisoformat(ctx['data'])
        except ValueError:
            data = None
        if ctx['gran'] not in JANELAS or modelo is None or data is None:
            messages.error(request, 'Escolha o modelo, o período e a data.')
        else:
            linhas, erros = colagem.interpretar_modelo(modelo.linhas)
            valores, erros_v = colagem.interpretar_valores(ctx['texto'])
            erros += erros_v
            extra = len(valores) - len(linhas)
            if not erros_v and extra < 0:
                erros.append(f'O modelo "{modelo.nome}" tem {len(linhas)} posições e a colagem tem {len(valores)} linhas.')
            ctx['excesso_ok'] = request.POST.get('excesso_ok') == '1'
            if not erros and extra > 0:
                if ctx['excesso_ok']:
                    valores = valores[:len(linhas)]  # o usuário aceitou ignorar as linhas a mais
                else:
                    sobra = valores[len(linhas):]
                    ctx['excesso'] = {'n': extra, 'vazias': all(v is None for v in sobra), 'modelo': modelo.nome, 'posicoes': len(linhas)}
                    erros = None
            if erros:
                ctx['erros'] = erros
            elif erros is None:
                pass  # aguardando a decisão do usuário sobre as linhas a mais
            else:
                gravar = request.POST.get('confirmar') == '1'
                res = colagem.aplicar(linhas, valores, ctx['gran'], data, request.user, gravar)
                ctx.update(res, linhas=[dict(l, valor=v) for l, v in zip(linhas, valores)], gravado=gravar)
                if gravar:
                    messages.success(request, f'{res["salvos"]} indicador(es) atualizado(s) em {_rotulo(ctx["gran"], res["periodo"])}.')
    return render(request, 'kpi/colagem.html', ctx)


@login_required
def colagem_modelos_view(request):
    from kpi.models import ModeloColagem
    return render(request, 'kpi/colagem_modelos.html', {'modelos': ModeloColagem.objects.all()})


@login_required
def colagem_modelo_form_view(request, pk=None):
    from kpi import colagem
    from kpi.models import ModeloColagem
    modelo = get_object_or_404(ModeloColagem, pk=pk) if pk else None
    erros = []
    nome = request.POST.get('nome', modelo.nome if modelo else '')
    linhas_txt = request.POST.get('linhas', modelo.linhas if modelo else '')
    if request.method == 'POST':
        nome = nome.strip()
        _, erros = colagem.interpretar_modelo(linhas_txt)
        if not nome:
            erros.insert(0, 'Informe o nome do modelo.')
        elif ModeloColagem.objects.filter(nome__iexact=nome).exclude(pk=pk).exists():
            erros.insert(0, 'Já existe um modelo com esse nome.')
        if not erros:
            modelo = modelo or ModeloColagem(criado_por=request.user)
            modelo.nome, modelo.linhas = nome[:100], linhas_txt.strip()
            modelo.save()
            messages.success(request, 'Modelo salvo.')
            return redirect('kpi:colagem_modelos')
    return render(request, 'kpi/colagem_modelo_form.html', {
        'modelo': modelo, 'nome': nome, 'linhas': linhas_txt, 'erros': erros,
        'ind_dados': {i.nome: {'variaveis': calculo.lista_campos(i), 'setores': [x.nome for x in i.setores.all()]}
                      for i in Indicador.objects.filter(ativo=True).prefetch_related('setores')}})


@login_required
@require_POST
def colagem_modelo_excluir_view(request, pk):
    from kpi.models import ModeloColagem
    get_object_or_404(ModeloColagem, pk=pk).delete()
    messages.success(request, 'Modelo excluído.')
    return redirect('kpi:colagem_modelos')


# ---------------------------------------------------------------- causas e análises (períodos fora da meta)
def _nome_usuario(u):
    return (u.get_full_name() or u.get_username()) if u else ''


def _janela(gran, periodo):
    if gran == 'semanal':
        return periodo, periodo + datetime.timedelta(days=6)
    if gran == 'mensal':
        return periodo.replace(day=1), periodo
    return periodo, periodo


def _num(v):
    return f'{Decimal(v):.2f}'.rstrip('0').rstrip('.').replace('.', ',')


def _dias_fora_da_meta(ind, setor_id, gran, periodo, meta):
    """Dias fora da meta de uma semana ou mês (informação de apoio, não vira card)."""
    if gran == 'diaria':
        return []
    ini, fim = _janela(gran, periodo)
    dias = Medicao.objects.filter(indicador=ind, setor_id=setor_id, granularidade='diaria',
                                  periodo__range=(ini, fim)).order_by('periodo')
    return [{'dia': f'{m.periodo:%d/%m}', 'valor': _num(m.valor)} for m in dias if ind.atingiu(m.valor, meta) is False]


def _cards_sugeridos(ind, setor_id, gran, periodo):
    """Cards-base para a análise do período:
    - um card por principal motivo registrado no período (até 5);
    - os cards já registrados nos dias da semana (ou nas semanas do mês; dias só quando a semana dele não tem análise).
    Cada card traz `origem` (de onde veio a sugestão) para o usuário conferir."""
    from kpi.models import AnaliseCausa
    ini, fim = _janela(gran, periodo)
    cards = []

    def de_registro(a, origem):
        for it in a.itens.all():
            if it.causa.strip() or it.analise.strip() or it.acao.strip():
                cards.append({'causa': it.causa, 'analise': it.analise, 'acao': it.acao,
                              'ocorrencias': list(it.ocorrencias.values_list('pk', flat=True)), 'origem': origem})

    if gran == 'semanal':
        for a in AnaliseCausa.objects.filter(indicador=ind, setor_id=setor_id, granularidade='diaria', dispensada=False,
                                             periodo__range=(ini, fim)).prefetch_related('itens__ocorrencias').order_by('periodo'):
            de_registro(a, f'Dia {a.periodo:%d/%m}')
    elif gran == 'mensal':
        semanas = list(AnaliseCausa.objects.filter(indicador=ind, setor_id=setor_id, granularidade='semanal', dispensada=False,
                                                   periodo__range=(ini - datetime.timedelta(days=6), fim))
                       .prefetch_related('itens__ocorrencias').order_by('periodo'))
        cobertas = set()
        for a in semanas:
            if any(i.causa.strip() or i.analise.strip() or i.acao.strip() for i in a.itens.all()):
                cobertas.add(a.periodo)
            de_registro(a, f'Semana de {a.periodo:%d/%m}')
        for a in AnaliseCausa.objects.filter(indicador=ind, setor_id=setor_id, granularidade='diaria', dispensada=False,
                                             periodo__range=(ini, fim)).prefetch_related('itens__ocorrencias').order_by('periodo'):
            if a.periodo - datetime.timedelta(days=a.periodo.weekday()) not in cobertas:
                de_registro(a, f'Dia {a.periodo:%d/%m}')
    soma = {}
    for desc, q in Motivo.objects.filter(indicador=ind, setor_id=setor_id, data__range=(ini, fim),
                                         consolidado=False).values_list('descricao', 'quantidade'):
        soma[desc.strip()] = soma.get(desc.strip(), Decimal(0)) + q
    motivos = [{'causa': f'{d} ({_num(q)})', 'analise': '', 'acao': '', 'ocorrencias': [], 'origem': 'Motivo registrado'}
               for d, q in sorted(soma.items(), key=lambda x: x[1], reverse=True)[:5]]
    return motivos + cards


def _ocorrencias_periodo(gran, periodo):
    """Ocorrências do laboratório que estiveram abertas em algum momento do período (para o usuário vincular)."""
    from django.db.models import Q
    from laboratorio.models import OcorrenciaLaboratorio
    ini, fim = _janela(gran, periodo)
    inicio = timezone.make_aware(datetime.datetime.combine(ini, datetime.time.min))
    limite = timezone.make_aware(datetime.datetime.combine(fim, datetime.time.max))
    qs = (OcorrenciaLaboratorio.objects.filter(data_abertura__lte=limite)
          .filter(Q(data_encerramento__isnull=True) | Q(data_encerramento__gte=inicio))
          .select_related('categoria', 'responsavel').order_by('-data_abertura')[:200])
    saida = []
    for o in qs:
        saida.append({
            'id': o.pk, 'assunto': o.assunto, 'categoria': o.categoria.nome if o.categoria else '',
            'responsavel': (o.responsavel.get_full_name() or o.responsavel.get_username()) if o.responsavel else '',
            'abertura': timezone.localtime(o.data_abertura).strftime('%d/%m %H:%M'),
            'encerramento': timezone.localtime(o.data_encerramento).strftime('%d/%m %H:%M') if o.data_encerramento else '',
            'impacto': o.get_impacto_display() if hasattr(o, 'get_impacto_display') else o.impacto,
        })
    return saida


def _itens_json(registro):
    return [{'causa': i.causa, 'analise': i.analise, 'acao': i.acao,
             'ocorrencias': list(i.ocorrencias.values_list('pk', flat=True))} for i in registro.itens.all()]


def _resumo_registro(registro):
    """Resumo para a lista: primeira causa e quantidade de cards."""
    itens = list(registro.itens.all())
    primeira = next((i.causa for i in itens if i.causa.strip()), '')
    return {'c': (primeira or registro.causa)[:140], 'a': any(i.analise.strip() or i.acao.strip() for i in itens) or bool(registro.analise.strip()),
            'n': len(itens), 'd': registro.dispensada, 'm': registro.motivo_dispensa}


def _parametros_analise(request, ind, origem):
    """(gran, periodo, setor, erro) a partir do GET/POST."""
    gran = origem.get('gran', '')
    try:
        data = datetime.date.fromisoformat(origem.get('data', ''))
    except ValueError:
        return None, None, None, 'Data inválida.'
    if gran not in JANELAS:
        return None, None, None, 'Período inválido.'
    setor = None
    bruto = (origem.get('setor') or '').strip()
    if bruto:
        setor = ind.setores.filter(pk=bruto).first() if bruto.isdigit() else None
        if setor is None:
            return None, None, None, 'Setor inválido.'
    return gran, _normalizar(gran, data), setor, None


@login_required
def analise_dados_view(request, pk):
    from django.http import JsonResponse
    from kpi.models import AnaliseCausa
    ind = get_object_or_404(Indicador, pk=pk)
    gran, periodo, setor, erro = _parametros_analise(request, ind, request.GET)
    if erro:
        return JsonResponse({'erro': erro}, status=400)
    setor_id = setor.pk if setor else None
    meta = setor.meta_efetiva if setor else ind.meta
    med = Medicao.objects.filter(indicador=ind, setor_id=setor_id, granularidade=gran, periodo=periodo).first()
    atual = AnaliseCausa.objects.filter(indicador=ind, setor_id=setor_id, granularidade=gran, periodo=periodo).prefetch_related('itens').first()
    return JsonResponse({
        'rotulo': _rotulo(gran, periodo), 'data': periodo.isoformat(), 'meta': float(meta), 'unidade': ind.unidade,
        'valor': float(med.valor) if med else None,
        'atingiu': ind.atingiu(med.valor, meta) if med else None,
        'itens': _itens_json(atual) if atual and not atual.dispensada else [],
        'dispensada': bool(atual and atual.dispensada), 'motivo_dispensa': atual.motivo_dispensa if atual else '',
        'cards_sugeridos': _cards_sugeridos(ind, setor_id, gran, periodo),
        'dias_fora': _dias_fora_da_meta(ind, setor_id, gran, periodo, meta),
        'ocorrencias': _ocorrencias_periodo(gran, periodo),
    })


def _itens_do_post(post):
    """Cards enviados: JSON em `itens` ou, por compatibilidade, os campos únicos causa/analise/acao."""
    import json
    bruto = post.get('itens')
    if bruto is not None:
        try:
            lista = json.loads(bruto)
        except ValueError:
            raise ValueError('Cards inválidos.')
        if not isinstance(lista, list):
            raise ValueError('Cards inválidos.')
    else:
        lista = [{'causa': post.get('causa', ''), 'analise': post.get('analise', ''), 'acao': post.get('acao', '')}]
    itens = []
    for i in lista[:50]:
        if not isinstance(i, dict):
            continue
        causa, analise, acao = (str(i.get(k, '')).strip() for k in ('causa', 'analise', 'acao'))
        ocs = [int(x) for x in (i.get('ocorrencias') or []) if str(x).isdigit()]
        if causa or analise or acao or ocs:
            itens.append({'causa': causa, 'analise': analise, 'acao': acao, 'ocorrencias': ocs})
    return itens


def _gravar_itens(registro, itens):
    from laboratorio.models import OcorrenciaLaboratorio
    registro.itens.all().delete()
    for n, i in enumerate(itens):
        card = registro.itens.create(ordem=n, causa=i['causa'], analise=i['analise'], acao=i['acao'])
        if i['ocorrencias']:
            card.ocorrencias.set(OcorrenciaLaboratorio.objects.filter(pk__in=i['ocorrencias']))
    primeiro = itens[0] if itens else {'causa': '', 'analise': ''}
    registro.causa, registro.analise = primeiro['causa'], primeiro['analise']  # resumo do primeiro card
    registro.save(update_fields=['causa', 'analise', 'atualizado_em'])


@login_required
@require_POST
def analise_salvar_view(request, pk):
    from django.http import JsonResponse
    from kpi.models import AnaliseCausa
    ind = get_object_or_404(Indicador, pk=pk)
    gran, periodo, setor, erro = _parametros_analise(request, ind, request.POST)
    if erro:
        return JsonResponse({'erro': erro}, status=400)
    try:
        itens = _itens_do_post(request.POST)
    except ValueError as e:
        return JsonResponse({'erro': str(e)}, status=400)
    filtro = dict(indicador=ind, setor=setor, granularidade=gran, periodo=periodo)
    if AnaliseCausa.objects.filter(**filtro, dispensada=True).exists():
        return JsonResponse({'erro': 'Este período está dispensado de análise. Reative-o para registrar causa e análise.'}, status=400)
    if not itens:
        AnaliseCausa.objects.filter(**filtro).delete()
        return JsonResponse({'ok': True, 'removida': True})
    registro, _ = AnaliseCausa.objects.get_or_create(**filtro, defaults={'registrado_por': request.user})
    registro.registrado_por = request.user
    _gravar_itens(registro, itens)
    registro = AnaliseCausa.objects.prefetch_related('itens').get(pk=registro.pk)
    return JsonResponse({'ok': True, 'data': periodo.isoformat(), **_resumo_registro(registro)})


@login_required
@require_POST
def analise_dispensar_view(request, pk):
    """Dispensa um período fora da meta de causa e análise (ou reativa um dispensado). Exige autorização especial."""
    from django.http import JsonResponse
    from kpi.models import AnaliseCausa
    ind = get_object_or_404(Indicador, pk=pk)
    gran, periodo, setor, erro = _parametros_analise(request, ind, request.POST)
    if erro:
        return JsonResponse({'erro': erro}, status=400)
    filtro = dict(indicador=ind, setor=setor, granularidade=gran, periodo=periodo)
    if request.POST.get('acao') == 'reativar':
        AnaliseCausa.objects.filter(**filtro, dispensada=True).delete()
        return JsonResponse({'ok': True, 'reativada': True, 'data': periodo.isoformat()})
    motivo = request.POST.get('motivo', '').strip()[:200]
    if not motivo:
        return JsonResponse({'erro': 'Informe o motivo da dispensa.'}, status=400)
    existente = AnaliseCausa.objects.filter(**filtro).first()
    if existente and not existente.dispensada:
        return JsonResponse({'erro': 'Este período já tem causa/análise registrada: remova o registro antes de dispensar.'}, status=400)
    AnaliseCausa.objects.update_or_create(**filtro, defaults={
        'dispensada': True, 'motivo_dispensa': motivo, 'causa': '', 'analise': '', 'registrado_por': request.user})
    return JsonResponse({'ok': True, 'data': periodo.isoformat(), 'motivo': motivo})


def _parametros_lote(request, ind):
    """(gran, setor, [períodos normalizados], erro) para as ações em massa: `datas` = datas ISO separadas por vírgula."""
    gran, _periodo, setor, erro = _parametros_analise(request, ind, dict(request.POST.items(), data=datetime.date.today().isoformat()))
    if erro:
        return None, None, [], erro
    periodos = []
    for bruto in (request.POST.get('datas') or '').split(','):
        bruto = bruto.strip()
        if not bruto:
            continue
        try:
            periodos.append(_normalizar(gran, datetime.date.fromisoformat(bruto)))
        except ValueError:
            return None, None, [], f'Data inválida: {bruto}.'
    periodos = sorted(set(periodos))
    if not periodos:
        return None, None, [], 'Selecione ao menos um período.'
    if len(periodos) > 400:
        return None, None, [], 'Selecione no máximo 400 períodos por vez.'
    return gran, setor, periodos, None


@login_required
@require_POST
def analise_salvar_massa_view(request, pk):
    """Aplica a mesma causa/análise a vários períodos. Períodos dispensados ou que já têm análise são preservados."""
    from django.http import JsonResponse
    from kpi.models import AnaliseCausa
    ind = get_object_or_404(Indicador, pk=pk)
    gran, setor, periodos, erro = _parametros_lote(request, ind)
    if erro:
        return JsonResponse({'erro': erro}, status=400)
    causa, analise = request.POST.get('causa', '').strip(), request.POST.get('analise', '').strip()
    if not causa and not analise:
        return JsonResponse({'erro': 'Informe a causa ou a análise.'}, status=400)
    existentes = {a.periodo: a for a in AnaliseCausa.objects.filter(indicador=ind, setor=setor, granularidade=gran, periodo__in=periodos)}
    aplicados, ignorados = {}, 0
    for p in periodos:
        if p in existentes:
            ignorados += 1
            continue
        registro = AnaliseCausa.objects.create(indicador=ind, setor=setor, granularidade=gran, periodo=p, registrado_por=request.user)
        _gravar_itens(registro, [{'causa': causa, 'analise': analise, 'acao': request.POST.get('acao', '').strip(), 'ocorrencias': []}])
        aplicados[p.isoformat()] = {'c': causa[:140], 'a': bool(analise), 'n': 1, 'd': False, 'm': ''}
    return JsonResponse({'ok': True, 'aplicados': aplicados, 'ignorados': ignorados})


@login_required
@require_POST
def analise_dispensar_massa_view(request, pk):
    """Dispensa vários períodos de uma vez, com o mesmo motivo. Períodos com análise registrada são preservados."""
    from django.http import JsonResponse
    from kpi.models import AnaliseCausa
    ind = get_object_or_404(Indicador, pk=pk)
    gran, setor, periodos, erro = _parametros_lote(request, ind)
    if erro:
        return JsonResponse({'erro': erro}, status=400)
    motivo = request.POST.get('motivo', '').strip()[:200]
    if not motivo:
        return JsonResponse({'erro': 'Informe o motivo da dispensa.'}, status=400)
    existentes = {a.periodo: a for a in AnaliseCausa.objects.filter(indicador=ind, setor=setor, granularidade=gran, periodo__in=periodos)}
    aplicados, ignorados = {}, 0
    for p in periodos:
        atual = existentes.get(p)
        if atual is not None and not atual.dispensada:
            ignorados += 1
            continue
        AnaliseCausa.objects.update_or_create(indicador=ind, setor=setor, granularidade=gran, periodo=p, defaults={
            'dispensada': True, 'motivo_dispensa': motivo, 'causa': '', 'analise': '', 'registrado_por': request.user})
        aplicados[p.isoformat()] = {'c': '', 'a': False, 'd': True, 'm': motivo}
    return JsonResponse({'ok': True, 'aplicados': aplicados, 'ignorados': ignorados})


# ---------------------------------------------------------------- base de motivos de perdas e de retorno
def _tipo_motivo(valor, padrao='perda'):
    from kpi.models import MotivoCadastro
    return valor if valor in dict(MotivoCadastro.TIPOS) else padrao


def _lista_motivos(request, tipo):
    from kpi.models import MotivoCadastro
    return render(request, 'kpi/motivos_cadastro.html', {
        'tipo': tipo, 'tipos': MotivoCadastro.TIPOS,
        'nome_tipo': dict(MotivoCadastro.TIPOS)[tipo],
        'itens': MotivoCadastro.objects.filter(tipo=tipo),
        'pode_editar': has_view_access(request.user, 'kpi:motivo_cadastro_salvar'),
        'pode_excluir': has_view_access(request.user, 'kpi:motivo_cadastro_excluir'),
        'ver_perda': has_view_access(request.user, 'kpi:motivos_perdas'),
        'ver_retorno': has_view_access(request.user, 'kpi:motivos_retorno'),
    })


@login_required
def motivos_perdas_view(request):
    return _lista_motivos(request, 'perda')


@login_required
def motivos_retorno_view(request):
    return _lista_motivos(request, 'retorno')


@login_required
@require_POST
def motivo_cadastro_salvar_view(request):
    """Cria ou atualiza um motivo da base (id vazio = novo)."""
    from kpi.models import MotivoCadastro
    pk = request.POST.get('id', '').strip()
    item = get_object_or_404(MotivoCadastro, pk=pk) if pk.isdigit() else None
    tipo = item.tipo if item else _tipo_motivo(request.POST.get('tipo'), '')
    destino = 'kpi:motivos_retorno' if tipo == 'retorno' else 'kpi:motivos_perdas'
    if not tipo:
        messages.error(request, 'Tipo de motivo inválido.')
        return redirect('kpi:motivos_perdas')
    nome = request.POST.get('nome', '').strip()[:150]
    if not nome:
        messages.error(request, 'Informe o motivo.')
        return redirect(destino)
    if MotivoCadastro.objects.filter(tipo=tipo, nome__iexact=nome).exclude(pk=item.pk if item else None).exists():
        messages.error(request, f'Já existe "{nome}" neste cadastro.')
        return redirect(destino)
    item = item or MotivoCadastro(tipo=tipo)
    item.nome = nome
    item.descricao = request.POST.get('descricao', '').strip()[:255]
    ordem = request.POST.get('ordem', '').strip()
    if ordem.isdigit():
        item.ordem = int(ordem)
    elif not item.pk:
        ultimo = MotivoCadastro.objects.filter(tipo=tipo).order_by('-ordem').first()
        item.ordem = (ultimo.ordem + 1) if ultimo else 1
    item.ativo = (request.POST.get('ativo') == 'on') if pk else True
    item.save()
    messages.success(request, f'"{item.nome}" salvo.')
    return redirect(destino)


@login_required
@require_POST
def motivo_cadastro_excluir_view(request, pk):
    from kpi.models import MotivoCadastro
    item = get_object_or_404(MotivoCadastro, pk=pk)
    destino = 'kpi:motivos_retorno' if item.tipo == 'retorno' else 'kpi:motivos_perdas'
    nome = item.nome
    item.delete()
    messages.success(request, f'"{nome}" excluído.')
    return redirect(destino)
