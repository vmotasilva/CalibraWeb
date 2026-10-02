# -*- coding: utf-8 -*-
"""
Views e Endpoints JSON / REST para o Módulo de Diagramas e Fluxogramas (DOC.071)
Compatível nativamente com Django 5.0 sem dependência externa obrigatória.
"""

import json
from django.db import models, transaction
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.core.exceptions import ValidationError

from ..models_diagram import Diagrama, DiagramaVersao, StatusDiagrama
from ..services.diagram_qms_service import DiagramaQMSService
from ..services.pdf_doc071_generator import gerar_pdf_diagrama_doc071


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
        "codigo": diagrama.codigo,
        "titulo": diagrama.titulo,
        "departamento": diagrama.departamento,
        "matriz_procedimento_id": diagrama.matriz_procedimento_id,
        "procedimento_id": diagrama.procedimento_id,
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
        qs = Diagrama.objects.select_related('criado_por').prefetch_related('versoes').filter(ativo=True)
        if departamento:
            qs = qs.filter(departamento=departamento)
        
        results = [serialize_diagrama(d, include_versoes=True) for d in qs]
        return JsonResponse({"results": results, "count": len(results)}, status=200)

    elif request.method == "POST":
        try:
            payload = json.loads(request.body)
        except Exception:
            return JsonResponse({"error": "JSON inválido no corpo da requisição."}, status=400)

        codigo = payload.get("codigo", "").strip()
        titulo = payload.get("titulo", "").strip()
        departamento = payload.get("departamento", "").strip()

        if not codigo or not titulo:
            return JsonResponse({"error": "Código e Título são obrigatórios."}, status=400)

        if Diagrama.objects.filter(codigo=codigo).exists():
            return JsonResponse({"error": f"Já existe um diagrama cadastrado com o código '{codigo}'."}, status=400)

        with transaction.atomic():
            diagrama = Diagrama.objects.create(
                codigo=codigo,
                titulo=titulo,
                departamento=departamento or "Geral",
                descricao=payload.get("descricao", ""),
                criado_por=request.user,
                matriz_procedimento_id=payload.get("matriz_procedimento_id"),
                procedimento_id=payload.get("procedimento_id"),
            )
            # Versão R00 inicial
            DiagramaVersao.objects.create(
                diagrama=diagrama,
                revisao=0,
                status=StatusDiagrama.RASCUNHO,
                dados_topologia={"nodes": [], "edges": [], "grid_data": []},
                motivo_revisao="Criação inicial do fluxograma."
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
        if "matriz_procedimento_id" in payload:
            diagrama.matriz_procedimento_id = payload["matriz_procedimento_id"]
        if "procedimento_id" in payload:
            diagrama.procedimento_id = payload["procedimento_id"]

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

    versao = get_object_or_404(DiagramaVersao, id=versao_id)
    try:
        versao_atualizada = DiagramaQMSService.submeter_para_aprovacao(versao, request.user)
        return JsonResponse(serialize_diagrama_versao(versao_atualizada), status=200)
    except ValidationError as e:
        msg = e.messages[0] if hasattr(e, 'messages') else str(e)
        return JsonResponse({"error": msg}, status=400)


@require_http_methods(["POST"])
def api_diagrama_versao_aprovar(request, versao_id):
    """Aprova formalmente o fluxograma."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Autenticação necessária."}, status=401)

    versao = get_object_or_404(DiagramaVersao, id=versao_id)
    try:
        versao_atualizada = DiagramaQMSService.aprovar_versao(versao, request.user)
        return JsonResponse(serialize_diagrama_versao(versao_atualizada), status=200)
    except ValidationError as e:
        msg = e.messages[0] if hasattr(e, 'messages') else str(e)
        return JsonResponse({"error": msg}, status=400)


@require_http_methods(["POST"])
def api_diagrama_versao_criar_nova_revisao(request, versao_id):
    """Clona versão vigente para iniciar nova revisão em rascunho."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Autenticação necessária."}, status=401)

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

    versao = get_object_or_404(DiagramaVersao.objects.select_related('diagrama', 'aprovado_por'), id=versao_id)
    try:
        payload = json.loads(request.body) if request.body else {}
    except Exception:
        payload = {}

    image_base64 = payload.get("image_base64")
    pdf_bytes = gerar_pdf_diagrama_doc071(versao, image_base64=image_base64)

    filename = f"DOC.071_{versao.diagrama.codigo}_Rev{versao.revisao:02d}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ==============================================================================
# HTML TEMPLATE VIEWS (INTERFACE DO USUÁRIO)
# ==============================================================================

@login_required
def diagramas_lista_view(request):
    """Tela de listagem de diagramas e fluxogramas cadastrados."""
    departamento = request.GET.get('departamento', '')
    busca = request.GET.get('busca', '').strip()

    diagramas = Diagrama.objects.filter(ativo=True).select_related('criado_por', 'matriz_procedimento').prefetch_related('versoes').order_by('codigo')

    if departamento:
        diagramas = diagramas.filter(departamento=departamento)
    if busca:
        diagramas = diagramas.filter(models.Q(codigo__icontains=busca) | models.Q(titulo__icontains=busca) | models.Q(descricao__icontains=busca))

    departamentos = Diagrama.objects.filter(ativo=True).values_list('departamento', flat=True).distinct()

    context = {
        'diagramas': diagramas,
        'departamentos': departamentos,
        'departamento_selecionado': departamento,
        'busca': busca,
    }
    return render(request, 'procedures/diagramas_lista.html', context)


@login_required
def diagrama_novo_view(request):
    """Tela/Formulário para criar um novo fluxograma."""
    if request.method == 'POST':
        codigo = request.POST.get('codigo', '').strip().upper()
        titulo = request.POST.get('titulo', '').strip()
        departamento = request.POST.get('departamento', '').strip()
        descricao = request.POST.get('descricao', '').strip()

        if not codigo or not titulo:
            return render(request, 'procedures/diagrama_form.html', {
                'error': 'Código e Título são campos obrigatórios.',
                'codigo': codigo, 'titulo': titulo, 'departamento': departamento, 'descricao': descricao
            })

        if Diagrama.objects.filter(codigo=codigo).exists():
            return render(request, 'procedures/diagrama_form.html', {
                'error': f'Já existe um diagrama com o código {codigo}.',
                'codigo': codigo, 'titulo': titulo, 'departamento': departamento, 'descricao': descricao
            })

        with transaction.atomic():
            diagrama = Diagrama.objects.create(
                codigo=codigo,
                titulo=titulo,
                departamento=departamento or "Qualidade",
                descricao=descricao,
                criado_por=request.user
            )
            versao = DiagramaVersao.objects.create(
                diagrama=diagrama,
                revisao=0,
                status=StatusDiagrama.RASCUNHO,
                dados_topologia={
                    "nodes": [
                        {"id": "1", "type": "start", "position": {"x": 80, "y": 80}, "data": {"label": "Início do Processo", "stepId": "1", "lane": departamento or "Qualidade"}},
                        {"id": "2", "type": "process", "position": {"x": 340, "y": 80}, "data": {"label": "Executar Atividade", "stepId": "2", "lane": departamento or "Qualidade"}},
                        {"id": "3", "type": "decision", "position": {"x": 600, "y": 60}, "data": {"label": "Conforme?", "stepId": "3", "lane": departamento or "Qualidade"}},
                        {"id": "4", "type": "end", "position": {"x": 860, "y": 80}, "data": {"label": "Fim do Processo", "stepId": "4", "lane": departamento or "Qualidade"}}
                    ],
                    "edges": [
                        {"id": "e-1-2", "source": "1", "target": "2", "sourceHandle": "bottom", "targetHandle": "top"},
                        {"id": "e-2-3", "source": "2", "target": "3", "sourceHandle": "bottom", "targetHandle": "top"},
                        {"id": "e-3-4", "source": "3", "target": "4", "sourceHandle": "bottom", "targetHandle": "top", "label": "Sim"}
                    ],
                    "grid_data": [
                        {"stepId": "1", "lane": departamento or "Qualidade", "type": "start", "label": "Início do Processo", "next": [{"targetId": "2"}]},
                        {"stepId": "2", "lane": departamento or "Qualidade", "type": "process", "label": "Executar Atividade", "next": [{"targetId": "3"}]},
                        {"stepId": "3", "lane": departamento or "Qualidade", "type": "decision", "label": "Conforme?", "next": [{"targetId": "4", "condition": "Sim"}]},
                        {"stepId": "4", "lane": departamento or "Qualidade", "type": "end", "label": "Fim do Processo", "next": []}
                    ]
                },
                motivo_revisao="Criação inicial do fluxograma."
            )

        return redirect('procedures:diagrama_editor', versao_id=versao.id)

    return render(request, 'procedures/diagrama_form.html')


@login_required
def diagrama_editor_view(request, versao_id):
    """Editor Interativo Híbrido: Modo Grelha + Modo Canvas xyflow."""
    versao = get_object_or_404(DiagramaVersao.objects.select_related('diagrama', 'aprovado_por'), id=versao_id)
    diagrama = versao.diagrama
    todas_versoes = diagrama.versoes.all().order_by('-revisao')

    context = {
        'versao': versao,
        'diagrama': diagrama,
        'todas_versoes': todas_versoes,
        'topologia_json': json.dumps(versao.dados_topologia or {"nodes": [], "edges": [], "grid_data": []}),
        'is_approved': versao.status == StatusDiagrama.APROVADO,
        'is_locked': versao.status != StatusDiagrama.RASCUNHO,
    }
    return render(request, 'procedures/diagrama_editor.html', context)

