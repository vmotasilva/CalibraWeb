# -*- coding: utf-8 -*-
"""
Views e Endpoints JSON / REST para o Módulo de Diagramas e Fluxogramas (DOC.071)
Compatível nativamente com Django 5.0 sem dependência externa obrigatória.
"""

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from django.db import models, transaction
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef, Subquery
from django.shortcuts import get_object_or_404, render, redirect
from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_datetime

from ..models import Procedimento
from ..models_diagram import Diagrama, DiagramaVersao, StatusDiagrama
from ..services.diagram_validation import validar_topologia
from ..services.diagram_diff import comparar_topologias
from ..services.diagram_fotos import decodificar_foto_colaborador
from .diagram_raias_views import pode_gerenciar_raias, raias_catalogo_para_editor
from .diagram_temas_views import pode_salvar_tema, temas_para_editor
from shared.inbox import invalidar_cache_inbox
from ..services.diagram_qms_service import DiagramaQMSService
from ..services.pdf_doc071_generator import gerar_pdf_diagrama_doc071
from ..services.diagram_templates import obter_catalogo_templates, obter_topologia_por_template_id


PERM_SUBMETER = 'core.nav_diagramas_submeter'
PERM_APROVAR = 'core.nav_diagramas_aprovar'
PERM_NOVA_REVISAO = 'core.nav_diagramas_nova_revisao'
PERM_EXPORT_PDF = 'core.nav_diagramas_export_pdf'


# Módulos JS do editor, na ordem de carregamento (scripts clássicos que compartilham o escopo global)
EDITOR_JS_MODULOS = [
    'estado', 'layout_arvore', 'estilo', 'inicializacao', 'canvas', 'inspetor', 'blocos', 'arvore', 'edicao_inline',
    'aparencia', 'outliner_grelha', 'raias_layout', 'persistencia', 'acoes_qms',
]


@lru_cache(maxsize=1)
def _versao_js_editor() -> str:
    """Hash de todos os módulos JS do editor para invalidar o cache do navegador a cada alteração."""
    pasta = Path(__file__).resolve().parent.parent / 'static' / 'procedures' / 'js' / 'diagrama'
    resumo = hashlib.md5()
    for nome in EDITOR_JS_MODULOS:
        try:
            resumo.update((pasta / f'{nome}.js').read_bytes())
        except OSError:
            resumo.update(nome.encode())
    return resumo.hexdigest()[:10]


def _tem_permissao(user, perm: str) -> bool:
    return bool(user.is_superuser or user.has_perm(perm))


def _negar_permissao(acao: str):
    return JsonResponse({"error": f"Você não tem permissão para {acao}."}, status=403)


def serialize_diagrama_versao(versao: DiagramaVersao) -> dict:
    """Serializa uma versão do diagrama para JSON."""
    aprovador_nome = None
    if versao.aprovado_por:
        aprovador_nome = versao.aprovado_por.get_full_name() or versao.aprovado_por.username

    return {
        "id": str(versao.id),
        "diagrama_id": str(versao.diagrama_id),
        "revisao": versao.revisao,
        "status": versao.status,
        "status_display": versao.get_status_display(),
        "dados_topologia": versao.dados_topologia or {"nodes": [], "edges": [], "grid_data": []},
        "motivo_revisao": versao.motivo_revisao,
        "motivo_devolucao": versao.motivo_devolucao,
        "submetido_por_id": versao.submetido_por_id,
        "data_submissao": versao.data_submissao.isoformat() if versao.data_submissao else None,
        "aprovado_por_id": versao.aprovado_por_id,
        "aprovado_por_nome": aprovador_nome,
        "data_aprovacao": versao.data_aprovacao.isoformat() if versao.data_aprovacao else None,
        "criado_em": versao.criado_em.isoformat() if versao.criado_em else None,
        "atualizado_em": versao.atualizado_em.isoformat() if versao.atualizado_em else None,
    }


def serialize_diagrama(diagrama: Diagrama, include_versoes: bool = False) -> dict:
    """Serializa o cabeçalho do diagrama para JSON."""
    criador_nome = diagrama.criado_por.get_full_name() or diagrama.criado_por.username if diagrama.criado_por else None

    data = {
        "id": str(diagrama.id),
        "numero": diagrama.numero,
        "identificador": diagrama.identificador,
        "codigo_exibicao": diagrama.codigo_exibicao,
        "codigo": diagrama.codigo,
        "titulo": diagrama.titulo,
        "departamento": diagrama.departamento,
        "procedimento_id": diagrama.procedimento_id,
        "procedimento_codigo": diagrama.procedimento.codigo if diagrama.procedimento else None,
        "procedimento_nome": diagrama.procedimento.nome if diagrama.procedimento else None,
        "matriz_procedimento_id": diagrama.matriz_procedimento_id,
        "descricao": diagrama.descricao,
        "criado_por_id": diagrama.criado_por_id,
        "criado_por_nome": criador_nome,
        "ativo": diagrama.ativo,
        "criado_em": diagrama.criado_em.isoformat() if diagrama.criado_em else None,
        "atualizado_em": diagrama.atualizado_em.isoformat() if diagrama.atualizado_em else None,
    }

    if include_versoes:
        data["versoes"] = [serialize_diagrama_versao(v) for v in diagrama.versoes.all().order_by('-revisao')]
        versao_vig = diagrama.versao_vigente
        data["versao_vigente"] = serialize_diagrama_versao(versao_vig) if versao_vig else None

    return data


# ==============================================================================
# ENDPOINTS REST / JSON
# ==============================================================================

@require_http_methods(["GET", "POST"])
def api_diagramas_list_create(request):
    """Listagem e Criação de Diagramas."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Autenticação necessária."}, status=401)

    if request.method == "GET":
        departamento = request.GET.get('departamento')
        qs = Diagrama.objects.select_related('criado_por', 'procedimento').prefetch_related('versoes').filter(ativo=True)
        if departamento:
            qs = qs.filter(departamento=departamento)

        results = [serialize_diagrama(d, include_versoes=True) for d in qs]
        return JsonResponse({"results": results, "count": len(results)}, status=200)

    elif request.method == "POST":
        try:
            payload = json.loads(request.body)
        except Exception:
            return JsonResponse({"error": "JSON inválido no corpo da requisição."}, status=400)

        titulo = payload.get("titulo", "").strip()
        departamento = payload.get("departamento", "").strip()
        procedimento_id = payload.get("procedimento_id")
        template_id = payload.get("template_id", "fluxograma_padrao")

        if not titulo:
            return JsonResponse({"error": "Título é obrigatório."}, status=400)

        with transaction.atomic():
            diagrama = Diagrama.objects.create(
                titulo=titulo,
                departamento=departamento or "Metrologia",
                descricao=payload.get("descricao", ""),
                criado_por=request.user,
                procedimento_id=procedimento_id,
                matriz_procedimento_id=payload.get("matriz_procedimento_id"),
                codigo=payload.get("codigo", ""),
            )
            topologia_inicial = obter_topologia_por_template_id(template_id, departamento or "Metrologia")
            # Versão R00 inicial com a topologia do template
            DiagramaVersao.objects.create(
                diagrama=diagrama,
                revisao=0,
                status=StatusDiagrama.RASCUNHO,
                dados_topologia=topologia_inicial,
                motivo_revisao="Criação inicial a partir de modelo de estrutura."
            )

        return JsonResponse(serialize_diagrama(diagrama, include_versoes=True), status=201)


@require_http_methods(["GET", "PUT", "PATCH", "DELETE"])
def api_diagrama_detail(request, diagrama_id):
    """Consulta e atualização do cabeçalho do diagrama."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Autenticação necessária."}, status=401)

    diagrama = get_object_or_404(Diagrama, id=diagrama_id)

    if request.method == "GET":
        return JsonResponse(serialize_diagrama(diagrama, include_versoes=True), status=200)

    elif (request.method in ["PUT", "PATCH", "DELETE"]
          and not request.user.is_superuser
          and diagrama.versoes.filter(status=StatusDiagrama.APROVADO).exists()):
        # Documento controlado: cabeçalho de diagrama com revisão aprovada só muda por nova revisão (ou administrador)
        return JsonResponse(
            {"error": "Diagrama com revisão aprovada não pode ter o cabeçalho alterado ou ser desativado. Crie uma nova revisão."},
            status=423
        )

    elif request.method in ["PUT", "PATCH"]:
        try:
            payload = json.loads(request.body)
        except Exception:
            return JsonResponse({"error": "JSON inválido."}, status=400)

        if "titulo" in payload:
            diagrama.titulo = payload["titulo"]
        if "departamento" in payload:
            diagrama.departamento = payload["departamento"]
        if "descricao" in payload:
            diagrama.descricao = payload["descricao"]
        if "procedimento_id" in payload:
            diagrama.procedimento_id = payload["procedimento_id"]
        if "codigo" in payload:
            diagrama.codigo = payload["codigo"]

        diagrama.save()
        return JsonResponse(serialize_diagrama(diagrama, include_versoes=True), status=200)

    elif request.method == "DELETE":
        diagrama.ativo = False
        diagrama.save(update_fields=['ativo', 'atualizado_em'])
        return JsonResponse({"status": "desativado"}, status=200)


@require_http_methods(["GET"])
def api_diagrama_versao_detail(request, versao_id):
    """Obtém detalhes e topologia de uma versão específica."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Autenticação necessária."}, status=401)

    versao = get_object_or_404(DiagramaVersao.objects.select_related('diagrama', 'aprovado_por'), id=versao_id)
    return JsonResponse(serialize_diagrama_versao(versao), status=200)


@require_http_methods(["PATCH", "POST"])
def api_diagrama_versao_autosave(request, versao_id):
    """
    Endpoint de Alta Frequência (Auto-Save).
    Persiste apenas o JSONField com 'update_fields' para otimização do Neon.tech.
    """
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Autenticação necessária."}, status=401)

    versao = get_object_or_404(DiagramaVersao, id=versao_id)

    # Trava de edição QMS: se já estiver aprovado, bloqueia (HTTP 423 Locked)
    if versao.status != StatusDiagrama.RASCUNHO:
        return JsonResponse(
            {"error": f"Edição bloqueada. A versão está com status '{versao.get_status_display()}'."},
            status=423
        )

    try:
        payload = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "JSON inválido."}, status=400)

    topologia = payload.get("dados_topologia")
    if topologia is None or not isinstance(topologia, dict):
        return JsonResponse({"error": "Campo 'dados_topologia' obrigatório e deve ser objeto JSON."}, status=400)

    # Controle otimista de concorrência: o cliente informa a versão (atualizado_em) em que se baseou.
    base_ts = parse_datetime(payload.get("base_atualizado_em") or "")
    if base_ts is not None and base_ts != versao.atualizado_em:
        return JsonResponse(
            {
                "error": "Este diagrama foi alterado em outra sessão/aba. Recarregue a página para não sobrescrever as alterações.",
                "atualizado_em": versao.atualizado_em.isoformat(),
            },
            status=409
        )

    erros = validar_topologia(topologia)
    if erros:
        return JsonResponse({"error": "Topologia inválida: " + "; ".join(erros), "detalhes": erros}, status=400)

    versao.dados_topologia = topologia
    versao.save(update_fields=['dados_topologia', 'atualizado_em'])

    return JsonResponse({
        "status": "saved",
        "atualizado_em": versao.atualizado_em.isoformat()
    }, status=200)


@require_http_methods(["POST"])
def api_diagrama_versao_submeter(request, versao_id):
    """Submete versão em rascunho para aprovação."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Autenticação necessária."}, status=401)

    if not _tem_permissao(request.user, PERM_SUBMETER):
        return _negar_permissao("submeter diagramas para aprovação")

    versao = get_object_or_404(DiagramaVersao, id=versao_id)
    try:
        versao_atualizada = DiagramaQMSService.submeter_para_aprovacao(versao, request.user)
        invalidar_cache_inbox()  # atualiza as pendências do sino (aprovadores/elaboradores)
        return JsonResponse(serialize_diagrama_versao(versao_atualizada), status=200)
    except ValidationError as e:
        msg = e.messages[0] if hasattr(e, 'messages') else str(e)
        return JsonResponse({"error": msg}, status=400)


@require_http_methods(["POST"])
def api_diagrama_versao_aprovar(request, versao_id):
    """Aprova formalmente o fluxograma."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Autenticação necessária."}, status=401)

    if not _tem_permissao(request.user, PERM_APROVAR):
        return _negar_permissao("aprovar diagramas")

    versao = get_object_or_404(DiagramaVersao, id=versao_id)
    try:
        versao_atualizada = DiagramaQMSService.aprovar_versao(versao, request.user)
        invalidar_cache_inbox()  # atualiza as pendências do sino (aprovadores/elaboradores)
        return JsonResponse(serialize_diagrama_versao(versao_atualizada), status=200)
    except ValidationError as e:
        msg = e.messages[0] if hasattr(e, 'messages') else str(e)
        return JsonResponse({"error": msg}, status=400)


@require_http_methods(["POST"])
def api_diagrama_versao_devolver(request, versao_id):
    """Reprova a revisão em aprovação, devolvendo-a ao elaborador como Rascunho (exige motivo)."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Autenticação necessária."}, status=401)
    if not _tem_permissao(request.user, PERM_APROVAR):
        return _negar_permissao("devolver diagramas para ajustes")

    versao = get_object_or_404(DiagramaVersao, id=versao_id)
    try:
        payload = json.loads(request.body) if request.body else {}
    except Exception:
        payload = {}

    try:
        versao_atualizada = DiagramaQMSService.devolver_para_ajustes(versao, request.user, payload.get("motivo", ""))
        invalidar_cache_inbox()  # atualiza as pendências do sino (aprovadores/elaboradores)
        return JsonResponse(serialize_diagrama_versao(versao_atualizada), status=200)
    except ValidationError as e:
        msg = e.messages[0] if hasattr(e, 'messages') else str(e)
        return JsonResponse({"error": msg}, status=400)


@require_http_methods(["POST"])
def api_diagrama_versao_criar_nova_revisao(request, versao_id):
    """Clona versão vigente para iniciar nova revisão em rascunho."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Autenticação necessária."}, status=401)

    if not _tem_permissao(request.user, PERM_NOVA_REVISAO):
        return _negar_permissao("criar novas revisões")

    versao = get_object_or_404(DiagramaVersao, id=versao_id)
    try:
        payload = json.loads(request.body) if request.body else {}
    except Exception:
        payload = {}

    motivo = payload.get("motivo_revisao", "")
    try:
        nova_versao = DiagramaQMSService.criar_nova_revisao(versao, request.user, motivo)
        return JsonResponse(serialize_diagrama_versao(nova_versao), status=201)
    except ValidationError as e:
        msg = e.messages[0] if hasattr(e, 'messages') else str(e)
        return JsonResponse({"error": msg}, status=400)


@require_http_methods(["POST"])
def api_diagrama_versao_exportar_pdf(request, versao_id):
    """Gera o arquivo PDF DOC.071 injetando a captura do canvas."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Autenticação necessária."}, status=401)

    if not _tem_permissao(request.user, PERM_EXPORT_PDF):
        return _negar_permissao("exportar o PDF DOC.071")

    versao = get_object_or_404(DiagramaVersao.objects.select_related('diagrama', 'aprovado_por'), id=versao_id)
    try:
        payload = json.loads(request.body) if request.body else {}
    except Exception:
        payload = {}

    image_base64 = payload.get("image_base64")
    pdf_bytes = gerar_pdf_diagrama_doc071(versao, image_base64=image_base64)

    nome_doc = re.sub(r'[^A-Za-z0-9#._-]+', '_', versao.diagrama.codigo_exibicao).strip('_')
    filename = f"DOC.071_{nome_doc}_Rev{versao.revisao:02d}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@require_http_methods(["GET"])
def api_diagramas_templates(request):
    """Retorna o catálogo completo de templates disponíveis."""
    templates = obter_catalogo_templates()
    return JsonResponse({"templates": templates}, status=200)


@require_http_methods(["POST"])
def api_diagrama_versao_aplicar_template(request, versao_id):
    """Aplica a topologia de um template à versão em rascunho."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Autenticação necessária."}, status=401)

    versao = get_object_or_404(DiagramaVersao.objects.select_related('diagrama'), id=versao_id)
    if versao.status != StatusDiagrama.RASCUNHO:
        return JsonResponse({"error": "Apenas versões em rascunho podem receber novos templates."}, status=423)

    try:
        payload = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "JSON inválido."}, status=400)

    template_id = payload.get("template_id", "fluxograma_padrao")
    nova_topologia = obter_topologia_por_template_id(template_id, versao.diagrama.departamento)
    versao.dados_topologia = nova_topologia
    versao.save(update_fields=['dados_topologia', 'atualizado_em'])

    return JsonResponse(serialize_diagrama_versao(versao), status=200)


@require_http_methods(["GET"])
def api_diagramas_colaboradores(request):
    """Busca de colaboradores para os blocos de colaborador (nome, função, setor e se há foto)."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Autenticação necessária."}, status=401)

    from rh.models import Colaborador

    termo = request.GET.get('q', '').strip()
    if len(termo) < 2:
        return JsonResponse({"results": []})

    colaboradores = (
        Colaborador.objects.select_related('setor')
        .filter(models.Q(nome_completo__icontains=termo) | models.Q(matricula__icontains=termo))
        .order_by('nome_completo')[:10]
    )
    return JsonResponse({"results": [
        {
            "id": c.id,
            "nome": c.nome_completo,
            "cargo": c.cargo or '',
            "setor": c.setor.nome if c.setor else '',
            "setor_id": c.setor_id,
            "tem_foto": bool(c.foto),
        }
        for c in colaboradores
    ]})


@require_http_methods(["GET"])
def api_diagramas_colaborador_foto(request, colaborador_id):
    """Entrega a foto do colaborador como imagem (evita gravar Base64 dentro do JSON do diagrama)."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Autenticação necessária."}, status=401)

    from rh.models import Colaborador

    foto = Colaborador.objects.filter(pk=colaborador_id).values_list('foto', flat=True).first()
    decodificada = decodificar_foto_colaborador(foto)
    if not decodificada:
        return HttpResponse(status=404)
    conteudo, content_type = decodificada
    resposta = HttpResponse(conteudo, content_type=content_type)
    resposta['Cache-Control'] = 'private, max-age=300'
    return resposta


# ==============================================================================
# HTML TEMPLATE VIEWS (INTERFACE DO USUÁRIO)
# ==============================================================================

ORDENACOES_LISTA = {
    'numero': ('numero', 'Número'),
    'recente': ('-atualizado_em', 'Atualizados recentemente'),
    'titulo': ('titulo', 'Título (A-Z)'),
}
STATUS_FILTRO = [
    (StatusDiagrama.RASCUNHO, 'Rascunho'),
    (StatusDiagrama.EM_APROVACAO, 'Em Aprovação'),
    (StatusDiagrama.APROVADO, 'Aprovado'),
    (StatusDiagrama.OBSOLETO, 'Obsoleto'),
]


@login_required
def diagramas_lista_view(request):
    """Tela de listagem de diagramas e fluxogramas cadastrados (filtros, ordenação e paginação)."""
    departamento = request.GET.get('departamento', '')
    busca = request.GET.get('busca', '').strip()
    status = request.GET.get('status', '')
    arquivados = request.GET.get('arquivados') == '1'
    ordem = request.GET.get('ordem', 'numero')
    if ordem not in ORDENACOES_LISTA:
        ordem = 'numero'

    ultima_versao = DiagramaVersao.objects.filter(diagrama=OuterRef('pk')).order_by('-revisao')
    diagramas = (
        Diagrama.objects.filter(ativo=not arquivados)
        .select_related('criado_por', 'procedimento', 'matriz_procedimento')
        .prefetch_related('versoes')
        .annotate(status_ultima=Subquery(ultima_versao.values('status')[:1]))
        .order_by(ORDENACOES_LISTA[ordem][0], 'numero')
    )

    if departamento:
        diagramas = diagramas.filter(departamento=departamento)
    if status in dict(STATUS_FILTRO):
        diagramas = diagramas.filter(status_ultima=status)
    if busca:
        filtro = (
            models.Q(titulo__icontains=busca) |
            models.Q(codigo__icontains=busca) |
            models.Q(descricao__icontains=busca) |
            models.Q(procedimento__codigo__icontains=busca) |
            models.Q(procedimento__nome__icontains=busca)
        )
        if busca.lstrip('#').isdigit():
            filtro |= models.Q(numero=int(busca.lstrip('#')))
        diagramas = diagramas.filter(filtro)

    departamentos = Diagrama.objects.values_list('departamento', flat=True).distinct().order_by('departamento')

    pagina = Paginator(diagramas, 25).get_page(request.GET.get('page'))
    for d in pagina.object_list:
        versoes = sorted(d.versoes.all(), key=lambda v: -v.revisao)
        d.ultima = versoes[0] if versoes else None
        d.vigente = next((v for v in versoes if v.status == StatusDiagrama.APROVADO), None)
        d.em_andamento = d.ultima is not None and d.ultima.status in (StatusDiagrama.RASCUNHO, StatusDiagrama.EM_APROVACAO)

    params = request.GET.copy()
    params.pop('page', None)

    context = {
        'diagramas': pagina.object_list,
        'pagina': pagina,
        'departamentos': departamentos,
        'departamento_selecionado': departamento,
        'busca': busca,
        'status_selecionado': status,
        'status_opcoes': STATUS_FILTRO,
        'arquivados': arquivados,
        'ordem': ordem,
        'ordem_opcoes': [(k, v[1]) for k, v in ORDENACOES_LISTA.items()],
        'querystring': params.urlencode(),
        'pode_criar': _tem_permissao(request.user, 'core.nav_diagramas_novo'),
    }
    return render(request, 'procedures/diagramas_lista.html', context)


@login_required
@require_POST
def diagrama_duplicar_view(request, diagrama_id):
    """Cria um novo diagrama (R00 em rascunho) copiando a última revisão do diagrama de origem."""
    if not _tem_permissao(request.user, 'core.nav_diagramas_novo'):
        messages.error(request, "Você não tem permissão para criar novos fluxogramas.")
        return redirect('procedures:diagramas_lista')

    origem = get_object_or_404(Diagrama, id=diagrama_id)
    ultima = origem.versoes.order_by('-revisao').first()
    with transaction.atomic():
        copia = Diagrama.objects.create(
            titulo=f"{origem.titulo} (cópia)"[:255],
            departamento=origem.departamento,
            procedimento=origem.procedimento,
            matriz_procedimento=origem.matriz_procedimento,
            descricao=origem.descricao,
            criado_por=request.user,
        )
        topologia = json.loads(json.dumps(ultima.dados_topologia)) if ultima else {"nodes": [], "edges": [], "grid_data": []}
        nova = DiagramaVersao.objects.create(
            diagrama=copia,
            revisao=0,
            status=StatusDiagrama.RASCUNHO,
            dados_topologia=topologia,
            motivo_revisao=f"Cópia de {origem.identificador}" + (f" (Rev. {ultima.revisao:02d})" if ultima else ""),
        )
    messages.success(request, f"Cópia criada a partir de {origem.identificador}.")
    return redirect('procedures:diagrama_editor', versao_id=nova.id)


@login_required
@require_POST
def diagrama_arquivar_view(request, diagrama_id):
    """Arquiva ou restaura um diagrama. Diagramas com revisão aprovada só podem ser arquivados por superusuário."""
    diagrama = get_object_or_404(Diagrama, id=diagrama_id)
    restaurar = request.POST.get('acao') == 'restaurar'
    tem_aprovada = diagrama.versoes.filter(status=StatusDiagrama.APROVADO).exists()

    if not request.user.is_superuser and (tem_aprovada or not _tem_permissao(request.user, 'core.nav_diagramas_editor')):
        messages.error(request, "Sem permissão: diagramas com revisão aprovada só podem ser arquivados por um administrador.")
    else:
        diagrama.ativo = restaurar
        diagrama.save(update_fields=['ativo', 'atualizado_em'])
        messages.success(request, f"{diagrama.identificador} {'restaurado' if restaurar else 'arquivado'}.")
    return redirect('procedures:diagramas_lista')


@login_required
def diagrama_historico_view(request, diagrama_id):
    """Histórico de revisões do diagrama e comparação entre duas revisões."""
    diagrama = get_object_or_404(Diagrama.objects.select_related('criado_por', 'procedimento'), id=diagrama_id)
    versoes = list(diagrama.versoes.select_related('aprovado_por', 'submetido_por').order_by('-revisao'))
    por_id = {str(v.id): v for v in versoes}

    para = por_id.get(request.GET.get('para', ''), versoes[0] if versoes else None)
    de = por_id.get(request.GET.get('de', ''))
    if de is None and para is not None:
        anteriores = [v for v in versoes if v.revisao < para.revisao]
        de = anteriores[0] if anteriores else None

    diff = comparar_topologias(de.dados_topologia, para.dados_topologia) if de and para and de.pk != para.pk else None

    return render(request, 'procedures/diagrama_historico.html', {
        'diagrama': diagrama,
        'versoes': versoes,
        'de': de,
        'para': para,
        'diff': diff,
    })


@login_required
def diagrama_novo_view(request):
    """Tela/Formulário para criar um novo fluxograma com catálogo de modelos visuais e vínculo opcional."""
    procedimentos = Procedimento.objects.filter(codigo__isnull=False).order_by('codigo')
    templates = obter_catalogo_templates()

    if request.method == 'POST':
        titulo = request.POST.get('titulo', '').strip()
        departamento = request.POST.get('departamento', '').strip()
        procedimento_id = request.POST.get('procedimento_id') or None
        descricao = request.POST.get('descricao', '').strip()
        template_id = request.POST.get('template_id', 'fluxograma_padrao')

        if not titulo:
            return render(request, 'procedures/diagrama_form.html', {
                'error': 'O Título do Processo / Diagrama é obrigatório.',
                'titulo': titulo,
                'departamento': departamento,
                'descricao': descricao,
                'procedimento_id': procedimento_id,
                'template_id_selecionado': template_id,
                'procedimentos': procedimentos,
                'templates': templates,
            })

        with transaction.atomic():
            diagrama = Diagrama.objects.create(
                titulo=titulo,
                departamento=departamento or "Metrologia",
                procedimento_id=procedimento_id,
                descricao=descricao,
                criado_por=request.user
            )
            topologia_inicial = obter_topologia_por_template_id(template_id, departamento or "Metrologia")
            versao = DiagramaVersao.objects.create(
                diagrama=diagrama,
                revisao=0,
                status=StatusDiagrama.RASCUNHO,
                dados_topologia=topologia_inicial,
                motivo_revisao=f"Criação inicial baseada no modelo '{template_id}'."
            )

        return redirect('procedures:diagrama_editor', versao_id=versao.id)

    return render(request, 'procedures/diagrama_form.html', {
        'procedimentos': procedimentos,
        'templates': templates,
        'template_id_selecionado': 'fluxograma_padrao',
    })


@login_required
def diagrama_editor_view(request, versao_id):
    """Editor Interativo Híbrido: Modo Grelha + Modo Canvas xyflow."""
    versao = get_object_or_404(DiagramaVersao.objects.select_related('diagrama', 'diagrama__procedimento', 'aprovado_por'), id=versao_id)
    diagrama = versao.diagrama
    todas_versoes = diagrama.versoes.all().order_by('-revisao')
    templates = obter_catalogo_templates()

    context = {
        'versao': versao,
        'diagrama': diagrama,
        'todas_versoes': todas_versoes,
        'templates': templates,
        'topologia_json': json.dumps(versao.dados_topologia or {"nodes": [], "edges": [], "grid_data": []}),
        'is_approved': versao.status == StatusDiagrama.APROVADO,
        'is_locked': versao.status != StatusDiagrama.RASCUNHO,
        'editor_js_version': _versao_js_editor(),
        'editor_js_modulos': EDITOR_JS_MODULOS,
        'raias_catalogo': raias_catalogo_para_editor(),
        'temas_salvos': temas_para_editor(request.user),
        'pode_salvar_tema': pode_salvar_tema(request.user),
        'pode_gerenciar_raias': pode_gerenciar_raias(request.user),
        'is_rascunho': versao.status == StatusDiagrama.RASCUNHO,
        'is_em_aprovacao': versao.status == StatusDiagrama.EM_APROVACAO,
        'revisao_em_andamento': any(
            v.status in (StatusDiagrama.RASCUNHO, StatusDiagrama.EM_APROVACAO) for v in todas_versoes
        ),
        'pode_submeter': _tem_permissao(request.user, PERM_SUBMETER),
        'pode_aprovar': _tem_permissao(request.user, PERM_APROVAR),
        'pode_nova_revisao': _tem_permissao(request.user, PERM_NOVA_REVISAO),
        'pode_exportar_pdf': _tem_permissao(request.user, PERM_EXPORT_PDF),
    }
    return render(request, 'procedures/diagrama_editor.html', context)
