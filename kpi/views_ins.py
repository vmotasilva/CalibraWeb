"""Indicadores de insumos: painel (dia/semana/mês), construtor com prévia ao vivo, salvar e excluir.
A lógica de cálculo está em kpi.indicadores_insumo."""
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from kpi import calculo, indicadores_insumo as engine
from kpi.models import HierItem, Indicador, IndicadorInsumo
from shared.permissions import has_view_access

# Modelos prontos com a lógica das abas "Materiais_Semanal/Mensal_Apresentação" da planilha de indicadores.
# `dica`: o que configurar no vínculo dos códigos (Códigos > fator) para a conta fechar.
MODELOS = [
    {'chave': 'pad', 'rotulo': 'Pad', 'nome': 'Pad — lentes por unidade', 'modo': 'rendimento', 'participacao': 70,
     'unidade': 'lentes/und', 'sentido': 'maior', 'meta': 250, 'casas': 0,
     'dica': 'Usa 70% da produção da surfaçagem (os outros 30% são da membrana).'},
    {'chave': 'membrana', 'rotulo': 'Membrana', 'nome': 'Membrana — lentes por unidade', 'modo': 'rendimento', 'participacao': 30,
     'unidade': 'lentes/und', 'sentido': 'maior', 'meta': 150, 'casas': 0,
     'dica': 'Usa 30% da produção da surfaçagem.'},
    {'chave': 'fita', 'rotulo': 'Fita', 'nome': 'Fita — lentes por metro', 'modo': 'rendimento', 'participacao': 100,
     'unidade': 'lentes/metro', 'sentido': 'maior', 'meta': 9, 'casas': 2,
     'dica': 'Informe o fator 35 nos códigos da fita (metros por rolo) para o consumo sair em metros.'},
    {'chave': 'polidor', 'rotulo': 'Polidor', 'nome': 'Polidor — lentes por galão', 'modo': 'rendimento', 'participacao': 100,
     'unidade': 'lentes/galão', 'sentido': 'maior', 'meta': 1000, 'casas': 0, 'dica': ''},
    {'chave': 'diamante', 'rotulo': 'Diamante', 'nome': 'Diamante — lentes por diamante novo', 'modo': 'rendimento', 'participacao': 100,
     'unidade': 'lentes/diamante', 'sentido': 'maior', 'meta': 16000, 'casas': 0, 'dica': ''},
    {'chave': 'quartz', 'rotulo': 'Quartz', 'nome': 'Quartz — lentes por unidade', 'modo': 'rendimento', 'participacao': 100,
     'unidade': 'lentes/und', 'sentido': 'maior', 'meta': 100, 'casas': 0,
     'dica': 'Informe o fator 10 no código do quartz (kit com 10 unidades).'},
    {'chave': 'zirconio', 'rotulo': 'Zircônio', 'nome': 'Zircônio — lentes por unidade', 'modo': 'rendimento', 'participacao': 100,
     'unidade': 'lentes/und', 'sentido': 'maior', 'meta': 50, 'casas': 0,
     'dica': 'Informe o fator de conversão do código (a planilha usa 135).'},
    {'chave': 'aloy', 'rotulo': 'Aloy', 'nome': 'Aloy — gramas por lente boa', 'modo': 'consumo', 'participacao': 100,
     'unidade': 'g/lente', 'sentido': 'menor', 'meta': 0.12, 'casas': 3, 'dica': ''},
    {'chave': 'dsx', 'rotulo': 'DSX', 'nome': 'DSX — gramas por lente boa', 'modo': 'consumo', 'participacao': 100,
     'unidade': 'g/lente', 'sentido': 'menor', 'meta': 0.004, 'casas': 4,
     'dica': 'Informe o fator 30 no código do DSX (gramas por frasco).'},
    {'chave': 'filtro', 'rotulo': 'Filtro 5FF', 'nome': 'Filtro 5FF — uso', 'modo': 'uso', 'participacao': 100,
     'unidade': 'und', 'sentido': 'maior', 'meta': 45, 'meta_semanal': 10, 'casas': 0,
     'dica': 'Só conta o consumo; não usa produção. Meta mensal 45 e semanal 10.'},
]


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _dec(txt, padrao=None):
    t = str(txt if txt is not None else '').strip().replace(',', '.')
    if not t:
        return padrao
    try:
        return Decimal(t)
    except InvalidOperation:
        return padrao


def _txt(d):
    """Decimal como texto simples, sem notação científica (Decimal(100).normalize() seria '1E+2')."""
    return '' if d is None else format(d.normalize(), 'f')


def _pode(user, nome):
    return has_view_access(user, nome)


def _visao(request, padrao='mes'):
    v = request.GET.get('visao')
    return v if v in dict(engine.VISOES) else padrao


# ───────────────────────────── painel ─────────────────────────────

@login_required
def painel_view(request):
    visao = _visao(request, '')  # vazio = cada indicador na sua periodicidade
    ref = engine.mes_param(request.GET.get('mes'))
    todos = list(IndicadorInsumo.objects.filter(ativo=True)
                 .select_related('item__subcategoria__categoria__setor', 'producao_indicador'))
    setores = {}
    for i in todos:
        s = i.item.subcategoria.categoria.setor
        setores[s.pk] = s
    setor = setores.get(_int(request.GET.get('setor')))
    cards = []
    for ind in todos:
        if setor and ind.item.subcategoria.categoria.setor_id != setor.pk:
            continue
        s = engine.serie(ind, visao or ind.periodicidade, ref)
        cards.append({'ind': ind, 'serie': s, 'grafico': engine.para_grafico(ind, s), 'dom_id': f'dados-ins-{ind.pk}',
                      'meta': s['linhas'][-1]['meta'],
                      'caminho': f'{ind.item.subcategoria.categoria.setor.nome} › {ind.item.subcategoria.categoria.nome} › '
                                 f'{ind.item.subcategoria.nome} › {ind.item.nome}'})
    grupos = []
    if visao:  # visão forçada: um grupo só, sem título
        grupos = [{'titulo': '', 'cards': cards}] if cards else []
    else:  # padrão de cada indicador: agrupa por periodicidade (diário → anual)
        for chave, rotulo in IndicadorInsumo.PERIODICIDADES:
            do_grupo = [c for c in cards if c['ind'].periodicidade == chave]
            if do_grupo:
                grupos.append({'titulo': f'Acompanhamento {rotulo.lower()}', 'cards': do_grupo})
    return render(request, 'kpi/ins_painel.html', {
        'grupos': grupos, 'visao': visao, 'visoes': engine.VISOES[:3], 'mes': ref, 'mes_valor': f'{ref:%Y-%m}',
        'setores': sorted(setores.values(), key=lambda s: (s.ordem, s.nome)), 'setor': setor, 'cards': cards,
        'sem_indicadores': not todos,
        'pode_cadastrar': _pode(request.user, 'kpi:ins_novo'), 'pode_excluir': _pode(request.user, 'kpi:ins_excluir'),
    })


# ───────────────────────────── construtor ─────────────────────────────

def _arvore():
    itens = list(HierItem.objects.filter(ativo=True).select_related('subcategoria__categoria__setor'))
    setores, cats, subs = {}, {}, {}
    for i in itens:
        sub = i.subcategoria
        cat = sub.categoria
        setores[cat.setor_id] = {'id': cat.setor_id, 'nome': cat.setor.nome}
        cats[cat.pk] = {'id': cat.pk, 'nome': cat.nome, 'setor': cat.setor_id, 'ctx': cat.setor.nome}
        subs[sub.pk] = {'id': sub.pk, 'nome': sub.nome, 'categoria': cat.pk, 'setor': cat.setor_id, 'ctx': cat.nome}
    return {
        'setores': list(setores.values()), 'categorias': list(cats.values()), 'subs': list(subs.values()),
        'itens': [{'id': i.pk, 'nome': i.nome, 'sub': i.subcategoria_id, 'categoria': i.subcategoria.categoria_id,
                   'setor': i.subcategoria.categoria.setor_id, 'ctx': i.subcategoria.nome} for i in itens],
    }


def _fontes():
    """KPIs principais que podem fornecer a produção: variáveis (campos) e setores de cada um."""
    out = []
    for ind in Indicador.objects.filter(ativo=True).prefetch_related('setores'):
        out.append({'id': ind.pk, 'nome': ind.nome, 'area': ind.area, 'campos': calculo.lista_campos(ind),
                    'setores': [{'id': s.pk, 'nome': s.nome} for s in ind.setores.all()]})
    return out


def _valores_de(ind):
    return {
        'pk': ind.pk or '', 'nome': ind.nome, 'periodicidade': ind.periodicidade, 'usar_fator': ind.usar_fator, 'item': ind.item_id or '', 'modo': ind.modo,
        'producao_indicador': ind.producao_indicador_id or '', 'producao_variavel': ind.producao_variavel,
        'producao_setor': ind.producao_setor_id or '', 'participacao': _txt(ind.participacao),
        'multiplicador': _txt(ind.multiplicador), 'unidade': ind.unidade, 'casas': ind.casas,
        'sentido': ind.sentido, 'meta': _txt(ind.meta), 'meta_semanal': _txt(ind.meta_semanal),
        'meta_diaria': _txt(ind.meta_diaria), 'ativo': ind.ativo,
    }


@login_required
def form_view(request, pk=None):
    ind = get_object_or_404(IndicadorInsumo, pk=pk) if pk else IndicadorInsumo(
        periodicidade='mes', modo=IndicadorInsumo.MODO_RENDIMENTO, participacao=Decimal(100), multiplicador=Decimal(1), casas=2)
    return render(request, 'kpi/ins_form.html', {
        'ind': ind, 'novo': not pk, 'valores': _valores_de(ind), 'arvore': _arvore(), 'fontes': _fontes(),
        'modelos': MODELOS, 'modos': IndicadorInsumo.MODOS, 'visoes': engine.VISOES,
        'periodicidades': IndicadorInsumo.PERIODICIDADES,
        'niveis': (('setor', 'Setor'), ('categoria', 'Categoria'), ('sub', 'Subcategoria'), ('item', 'Item')),
        'mes_valor': f'{timezone.localdate():%Y-%m}',
        'pode_excluir': bool(pk) and _pode(request.user, 'kpi:ins_excluir'),
    })


def _ler(dados, ind=None):
    """Monta (sem gravar) um indicador a partir dos campos do formulário. Devolve (indicador, erros)."""
    ind = ind or IndicadorInsumo()
    erros = []
    ind.nome = (dados.get('nome') or '').strip()
    item = HierItem.objects.filter(pk=_int(dados.get('item'))).first()
    if item is None:
        ind.item_id = None  # acessar ind.item sem item levanta exceção: use item_id para checar
        erros.append('Escolha o item (insumo) que será avaliado.')
    else:
        ind.item = item
    ind.periodicidade = dados.get('periodicidade') if dados.get('periodicidade') in dict(IndicadorInsumo.PERIODICIDADES) else 'mes'
    ind.usar_fator = dados.get('usar_fator') == 'on'
    ind.modo = dados.get('modo') if dados.get('modo') in dict(IndicadorInsumo.MODOS) else IndicadorInsumo.MODO_RENDIMENTO
    ind.sentido = dados.get('sentido') if dados.get('sentido') in dict(Indicador.SENTIDOS) else Indicador.SENTIDO_MAIOR
    ind.producao_indicador = Indicador.objects.filter(pk=_int(dados.get('producao_indicador'))).first()
    ind.producao_variavel = (dados.get('producao_variavel') or '').strip()
    ind.producao_setor = None
    if ind.producao_indicador:
        ind.producao_setor = ind.producao_indicador.setores.filter(pk=_int(dados.get('producao_setor'))).first()
        if ind.producao_variavel and ind.producao_variavel.casefold() not in {c.casefold() for c in calculo.lista_campos(ind.producao_indicador)}:
            erros.append(f'O indicador "{ind.producao_indicador}" não tem a variável "{ind.producao_variavel}".')
    elif ind.modo != IndicadorInsumo.MODO_USO:
        erros.append('Escolha o KPI principal de onde vem a produção (ou use o cálculo "Uso").')
    ind.participacao = _dec(dados.get('participacao'), Decimal(100))
    if not Decimal(0) < ind.participacao <= Decimal(100):
        erros.append('A participação na produção deve ser maior que 0 e no máximo 100%.')
        ind.participacao = Decimal(100)
    ind.multiplicador = _dec(dados.get('multiplicador'), Decimal(1))
    if ind.multiplicador <= 0:
        erros.append('O multiplicador deve ser maior que zero.')
        ind.multiplicador = Decimal(1)
    ind.casas = min(max(_int(dados.get('casas')) if _int(dados.get('casas')) is not None else 2, 0), 6)
    ind.unidade = (dados.get('unidade') or '').strip()[:40]
    ind.meta, ind.meta_semanal, ind.meta_diaria = (_dec(dados.get(k)) for k in ('meta', 'meta_semanal', 'meta_diaria'))
    return ind, erros


@login_required
def preview_view(request):
    """Prévia ao vivo do indicador em construção (não grava). Devolve a série calculada com os campos atuais."""
    ind, erros = _ler(request.GET)
    if ind.item_id is None:
        return JsonResponse({'erro': 'Escolha o item (insumo) para ver a prévia.'})
    visao = _visao(request, ind.periodicidade)
    ref = engine.mes_param(request.GET.get('mes'))
    s = engine.serie(ind, visao, ref)
    linhas = [{'rotulo': l['rotulo'], 'faixa': g, 'producao': engine._f(l['producao']), 'consumo': engine._f(l['consumo']),
               'valor': engine._f(l['valor']), 'meta': engine._f(l['meta']), 'ok': l['ok']}
              for l, g in zip(s['linhas'], engine.para_grafico(ind, s)['faixas'])]
    return JsonResponse({'erro': '; '.join(erros) if erros else '', 'grafico': engine.para_grafico(ind, s), 'linhas': linhas,
                         'janela': s['janela'], 'dentro': s['dentro'], 'fora': s['fora'],
                         'item': ind.item.nome, 'unidade_item': ind.item.unidade})


@login_required
@require_POST
def salvar_view(request):
    alvo = IndicadorInsumo.objects.filter(pk=_int(request.POST.get('pk'))).first()
    ind, erros = _ler(request.POST, alvo)
    if not ind.nome:
        erros.append('Informe o nome do indicador.')
    if erros:
        for e in erros:
            messages.error(request, e)
        return redirect('kpi:ins_editar', pk=alvo.pk) if alvo else redirect('kpi:ins_novo')
    ind.ativo = request.POST.get('ativo') == 'on'  # checkbox desmarcado não vem no POST
    if alvo is None:
        ind.criado_por = request.user
    with transaction.atomic():
        ind.save()
    messages.success(request, f'Indicador "{ind.nome}" salvo.')
    return redirect('kpi:ins_painel')


@login_required
@require_POST
def participacao_view(request, pk):
    """Ajusta, direto no grid do painel, o percentual da produção considerado no cálculo (rendimento e consumo específico)."""
    ind = get_object_or_404(IndicadorInsumo, pk=pk)
    pct = _dec(request.POST.get('participacao'))
    if ind.modo == IndicadorInsumo.MODO_USO:
        messages.error(request, 'Este indicador não usa produção.')
    elif pct is None or not Decimal(0) < pct <= Decimal(100):
        messages.error(request, 'A participação na produção deve ser maior que 0 e no máximo 100%.')
    else:
        ind.participacao = pct
        ind.save(update_fields=['participacao'])
        messages.success(request, f'Participação de "{ind.nome}" ajustada para {pct.normalize():f}%.')
    destino = request.POST.get('next') or ''
    if not url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        destino = 'kpi:ins_painel'
    return redirect(destino)


@login_required
@require_POST
def excluir_view(request, pk):
    ind = get_object_or_404(IndicadorInsumo, pk=pk)
    nome = ind.nome
    ind.delete()
    messages.success(request, f'Indicador "{nome}" excluído.')
    return redirect('kpi:ins_painel')
