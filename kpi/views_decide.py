"""DECIDE (Gestão > Processos): importação da planilha do medidor de lentes e construtor de indicadores."""
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from kpi import decide
from kpi.models import DecideImportacao, DecideIndicador, DecideLente
from shared.permissions import has_view_access


def _params_de(ind):
    c = dict(ind.config)
    c['meta'] = '' if ind.meta is None else str(ind.meta)
    return c


@login_required
def decide_view(request):
    salvo = None
    dados = request.GET
    if request.GET.get('ind', '').isdigit():
        salvo = DecideIndicador.objects.filter(pk=request.GET['ind']).first()
        if salvo:
            dados = _params_de(salvo)
    p = decide.ler_parametros(dados)
    tem_dados = DecideLente.objects.exists()
    resultado = decide.calcular(p['medida'], p['periodo'], p['dimensao'], p['filtros'], p['de'], p['ate']) if tem_dados else None
    nome_medida, unidade, sentido = decide.MEDIDAS[p['medida']]
    grafico = None
    if resultado:
        grafico = {
            'rotulos': resultado['rotulos'], 'series': resultado['series'], 'unidade': unidade, 'sentido': sentido,
            'meta': float(p['meta']) if p['meta'] is not None and sentido else None, 'medida': nome_medida,
        }
    return render(request, 'kpi/decide.html', {
        'p': p, 'nome_medida': nome_medida, 'nome_periodo': decide.PERIODOS[p['periodo']], 'tem_dados': tem_dados, 'resultado': resultado, 'unidade': unidade, 'sentido': sentido,
        'grafico_json': json.dumps(grafico) if grafico else 'null',
        'medidas': {k: v[0] for k, v in decide.MEDIDAS.items()},
        'periodos': decide.PERIODOS,
        'dimensoes': {k: v[0] for k, v in decide.DIMENSOES.items()},
        'opcoes': decide.opcoes_filtros() if tem_dados else {},
        'indicadores': DecideIndicador.objects.all(),
        'salvo': salvo,
        'importacoes': DecideImportacao.objects.all()[:8],
        'total_lentes': DecideLente.objects.filter(ultima=True).count(),
        'pode_importar': has_view_access(request.user, 'kpi:decide_importar'),
        'pode_salvar': has_view_access(request.user, 'kpi:decide_indicador_salvar'),
        'pode_excluir': has_view_access(request.user, 'kpi:decide_indicador_excluir'),
    })


@login_required
@require_POST
def decide_importar_view(request):
    arquivo = request.FILES.get('arquivo')
    if not arquivo:
        messages.error(request, 'Escolha a planilha .xlsx do DECIDE.')
        return redirect('kpi:decide')
    try:
        imp = decide.importar(arquivo, request.user)
    except decide.ErroPlanilha as e:
        messages.error(request, str(e))
        return redirect('kpi:decide')
    extra = f' {imp.substituidas} medição(ões) já existentes foram atualizadas.' if imp.substituidas else ''
    messages.success(request, f'{imp.arquivo}: {imp.linhas} medições de {imp.lentes} lentes importadas '
                              f'({imp.inicio:%d/%m} a {imp.fim:%d/%m}).{extra}')
    return redirect('kpi:decide')


@login_required
@require_POST
def decide_indicador_salvar_view(request):
    p = decide.ler_parametros(request.POST)
    nome = request.POST.get('nome', '').strip()[:150]
    if not nome:
        messages.error(request, 'Dê um nome ao indicador.')
        return redirect('kpi:decide')
    config = {'medida': p['medida'], 'periodo': p['periodo'], 'dimensao': p['dimensao'],
              'de': p['de'].isoformat() if p['de'] else '', 'ate': p['ate'].isoformat() if p['ate'] else '', **p['filtros']}
    pk = request.POST.get('id', '')
    ind = get_object_or_404(DecideIndicador, pk=pk) if pk.isdigit() else DecideIndicador(criado_por=request.user)
    ind.nome, ind.config, ind.meta = nome, config, p['meta']
    ind.descricao = request.POST.get('descricao', '').strip()[:255]
    ind.save()
    messages.success(request, f'Indicador "{ind.nome}" salvo.')
    from django.urls import reverse
    return redirect(f"{reverse('kpi:decide')}?ind={ind.pk}")


@login_required
@require_POST
def decide_indicador_excluir_view(request, pk):
    ind = get_object_or_404(DecideIndicador, pk=pk)
    nome = ind.nome
    ind.delete()
    messages.success(request, f'Indicador "{nome}" excluído.')
    return redirect('kpi:decide')
