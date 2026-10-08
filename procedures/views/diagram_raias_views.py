# -*- coding: utf-8 -*-
"""Tela de cadastro e mapeamento do catálogo de Raias (swimlanes) dos diagramas."""

import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, models, transaction
from django.shortcuts import redirect, render

from ..models_diagram import RaiaCatalogo
from ..services.diagram_raias import renomear_raia_em_rascunhos, uso_das_raias

PERM_RAIAS = 'core.nav_diagramas_raias'
COR_REGEX = re.compile(r'^#[0-9a-fA-F]{6}$')


def pode_gerenciar_raias(user) -> bool:
    return bool(user.is_superuser or user.has_perm(PERM_RAIAS))


def raias_catalogo_para_editor():
    """Catálogo ativo no formato consumido pelo editor (JSON)."""
    return [
        {
            'id': r.id,
            'nome': r.nome,
            'cor': r.cor,
            'ordem': r.ordem,
            'setor_id': r.setor_id,
            'setor_nome': r.setor.nome if r.setor else '',
        }
        for r in RaiaCatalogo.objects.filter(ativo=True).select_related('setor')
    ]


def _salvar(request):
    from organization.models import Setor

    raia_id = request.POST.get('id')
    nome = ' '.join(request.POST.get('nome', '').split())
    cor = request.POST.get('cor', '#334155').strip()
    descricao = request.POST.get('descricao', '').strip()[:255]
    setor_id = request.POST.get('setor') or None
    ativo = request.POST.get('ativo') == 'on'
    aplicar = request.POST.get('aplicar_rascunhos') == 'on'

    try:
        ordem = int(request.POST.get('ordem') or 0)
    except ValueError:
        ordem = 0

    if not nome or len(nome) > 100:
        messages.error(request, "Informe o nome da raia (até 100 caracteres).")
        return
    if not COR_REGEX.match(cor):
        messages.error(request, "Cor inválida. Use o formato #RRGGBB.")
        return
    setor = Setor.objects.filter(pk=setor_id).first() if setor_id else None

    existente = RaiaCatalogo.objects.filter(nome__iexact=nome).exclude(pk=raia_id or 0).first()
    if existente:
        messages.error(request, f"Já existe uma raia chamada \"{existente.nome}\". Use \"Mesclar\" para unificar.")
        return

    try:
        with transaction.atomic():
            if raia_id:
                raia = RaiaCatalogo.objects.get(pk=raia_id)
                nome_antigo = raia.nome
            else:
                raia = RaiaCatalogo()
                nome_antigo = None
                if not request.POST.get('ordem'):
                    ordem = (RaiaCatalogo.objects.aggregate(m=models.Max('ordem'))['m'] or 0) + 10
            raia.nome, raia.cor, raia.ordem, raia.descricao = nome, cor, ordem, descricao
            raia.setor, raia.ativo = setor, (ativo if raia_id else True)
            raia.save()

            renomeadas = 0
            if nome_antigo and nome_antigo != nome and aplicar:
                renomeadas = renomear_raia_em_rascunhos(nome_antigo, nome)
    except RaiaCatalogo.DoesNotExist:
        messages.error(request, "Raia não encontrada.")
        return
    except IntegrityError:
        messages.error(request, "Já existe uma raia com esse nome.")
        return

    texto = f"Raia \"{raia.nome}\" salva."
    if renomeadas:
        texto += f" Renomeada em {renomeadas} rascunho(s)."
    messages.success(request, texto)


def _mesclar(request):
    origem = RaiaCatalogo.objects.filter(pk=request.POST.get('id')).first()
    destino = RaiaCatalogo.objects.filter(pk=request.POST.get('destino_id')).first()
    if not origem or not destino or origem.pk == destino.pk:
        messages.error(request, "Escolha uma raia de destino diferente da origem.")
        return
    with transaction.atomic():
        alteradas = renomear_raia_em_rascunhos(origem.nome, destino.nome)
        origem.ativo = False
        origem.save(update_fields=['ativo', 'atualizado_em'])
    messages.success(
        request,
        f"\"{origem.nome}\" mesclada em \"{destino.nome}\" ({alteradas} rascunho(s) atualizado(s)). "
        "A raia de origem foi desativada; revisões já aprovadas não são alteradas."
    )


@login_required
def raias_catalogo_view(request):
    pode = pode_gerenciar_raias(request.user)

    if request.method == 'POST':
        if not pode:
            messages.error(request, "Você não tem permissão para alterar o catálogo de raias.")
            return redirect('procedures:diagramas_raias')

        acao = request.POST.get('acao')
        if acao == 'salvar':
            _salvar(request)
        elif acao == 'alternar':
            raia = RaiaCatalogo.objects.filter(pk=request.POST.get('id')).first()
            if raia:
                raia.ativo = not raia.ativo
                raia.save(update_fields=['ativo', 'atualizado_em'])
                messages.success(request, f"Raia \"{raia.nome}\" {'ativada' if raia.ativo else 'desativada'}.")
        elif acao == 'excluir':
            raia = RaiaCatalogo.objects.filter(pk=request.POST.get('id')).first()
            if raia:
                raia.delete()
                messages.success(request, f"Raia \"{raia.nome}\" removida do catálogo. Os diagramas que a usam não são alterados.")
        elif acao == 'mesclar':
            _mesclar(request)
        return redirect('procedures:diagramas_raias')

    from organization.models import Setor

    uso = uso_das_raias()
    raias = list(RaiaCatalogo.objects.select_related('setor'))
    for r in raias:
        r.uso = uso.get(r.nome.lower(), [])

    catalogo = {r.nome.lower() for r in raias}
    livres = sorted(
        ({'nome': itens[0]['raia'], 'uso': itens} for nome, itens in uso.items() if nome not in catalogo),
        key=lambda x: x['nome'].lower()
    )

    return render(request, 'procedures/diagrama_raias.html', {
        'raias': raias,
        'raias_livres': livres,
        'setores': Setor.objects.all().order_by('nome'),
        'pode_gerenciar': pode,
    })
