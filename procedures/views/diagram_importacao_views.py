# -*- coding: utf-8 -*-
"""Importação de mapas mentais (.xmind, OPML, Markdown/texto) como novo diagrama."""

from django.contrib import messages
from shared.permissions import user_has_nav_perm
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from ..models_diagram import Diagrama, DiagramaVersao, StatusDiagrama
from ..services.importacao_mapas import (
    EXTENSOES, MODOS_IMPORTACAO, ErroImportacao, carregar_colaboradores, ler_arquivo, para_topologia, resumo_das_folhas,
    vincular_colaboradores,
)

PERM_CRIAR = 'core.nav_diagramas_novo'
ROTULOS_LAYOUT = {
    'organograma': 'Organograma (de cima para baixo)',
    'logico': 'Lógico (da esquerda para a direita)',
    'arvore': 'Árvore (lista com recuo)',
}


def _pode_criar(user) -> bool:
    return user_has_nav_perm(user, PERM_CRIAR)


@login_required
@require_http_methods(["POST"])
def api_importar_previa(request):
    """Lê o arquivo enviado e devolve as planilhas encontradas (sem criar nada)."""
    if not _pode_criar(request.user):
        return JsonResponse({"error": "Você não tem permissão para criar diagramas."}, status=403)
    arquivo = request.FILES.get('arquivo')
    if not arquivo:
        return JsonResponse({"error": "Escolha um arquivo."}, status=400)
    try:
        folhas = ler_arquivo(arquivo.name, arquivo.read())
    except ErroImportacao as e:
        return JsonResponse({"error": str(e)}, status=400)
    colaboradores = carregar_colaboradores()
    return JsonResponse({"folhas": resumo_das_folhas(folhas, colaboradores), "colaboradores_no_rh": len(colaboradores)})


@login_required
def diagrama_importar_view(request):
    contexto = {
        'extensoes': ','.join(EXTENSOES),
        'layouts': [(k, ROTULOS_LAYOUT[k]) for k in MODOS_IMPORTACAO],
        'layout': 'organograma',
        'departamento': 'Metrologia',
        'pode_criar': _pode_criar(request.user),
    }
    if not contexto['pode_criar']:
        return render(request, 'procedures/diagrama_importar.html', contexto, status=403)

    if request.method == 'POST':
        arquivo = request.FILES.get('arquivo')
        titulo = request.POST.get('titulo', '').strip()[:200]
        departamento = request.POST.get('departamento', '').strip()[:120] or 'Metrologia'
        layout = request.POST.get('layout', 'organograma')
        com_estilos = request.POST.get('estilos') == 'on'
        vincular = request.POST.get('vincular') == 'on'
        contexto.update(titulo=titulo, departamento=departamento, layout=layout)
        try:
            if not arquivo:
                raise ErroImportacao('Escolha um arquivo para importar.')
            if not titulo:
                raise ErroImportacao('Informe o título do diagrama.')
            folhas = ler_arquivo(arquivo.name, arquivo.read())
            try:
                indice = int(request.POST.get('folha') or 0)
                folha = folhas[indice]
            except (ValueError, IndexError):
                raise ErroImportacao('Planilha inválida.')
            topologia = para_topologia(folha['raiz'], layout, com_estilos)
            vinculos = vincular_colaboradores(topologia) if vincular else None
        except ErroImportacao as e:
            contexto['error'] = str(e)
            return render(request, 'procedures/diagrama_importar.html', contexto)

        with transaction.atomic():
            diagrama = Diagrama.objects.create(titulo=titulo, departamento=departamento, criado_por=request.user)
            versao = DiagramaVersao.objects.create(
                diagrama=diagrama, revisao=0, status=StatusDiagrama.RASCUNHO, dados_topologia=topologia,
                motivo_revisao=f"Importado de '{arquivo.name}' ({folha['titulo']}).",
            )
        avisos = list(folha.get('avisos') or [])
        texto = f'Mapa importado: {len(topologia["nodes"])} blocos.'
        if vinculos is not None:
            texto += f' {vinculos["vinculados"]} ligado(s) a colaboradores do RH.'
            if vinculos['ambiguos']:
                nomes = ', '.join(vinculos['ambiguos'][:5]) + ('...' if len(vinculos['ambiguos']) > 5 else '')
                avisos.append(f'{len(vinculos["ambiguos"])} nome(s) com mais de um colaborador possível ficaram sem ligação ({nomes})')
        if avisos:
            messages.warning(request, texto + ' Ressalvas: ' + '; '.join(avisos) + '.')
        else:
            messages.success(request, texto)
        return redirect('procedures:diagrama_editor', versao_id=versao.id)

    return render(request, 'procedures/diagrama_importar.html', contexto)
