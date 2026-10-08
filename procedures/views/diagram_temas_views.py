# -*- coding: utf-8 -*-
"""API do catálogo de temas de diagramas (cores e estilos reutilizáveis)."""

import json

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from ..models_diagram import TemaDiagrama
from ..services.diagram_validation import validar_tema

PERM_EDITAR = 'core.nav_diagramas_editor'


def pode_salvar_tema(user) -> bool:
    return bool(user.is_superuser or user.has_perm(PERM_EDITAR))


def serializar_tema(tema: TemaDiagrama, user) -> dict:
    return {
        "id": tema.id,
        "nome": tema.nome,
        "definicao": tema.definicao,
        "criado_por_nome": (tema.criado_por.get_full_name() or tema.criado_por.username) if tema.criado_por else None,
        "pode_excluir": bool(user.is_superuser or (tema.criado_por_id and tema.criado_por_id == user.id)),
    }


def temas_para_editor(user) -> list:
    return [serializar_tema(t, user) for t in TemaDiagrama.objects.select_related('criado_por')]


@require_http_methods(["GET", "POST"])
def api_temas(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Autenticação necessária."}, status=401)

    if request.method == "GET":
        return JsonResponse({"results": temas_para_editor(request.user)})

    if not pode_salvar_tema(request.user):
        return JsonResponse({"error": "Você não tem permissão para salvar temas."}, status=403)
    try:
        payload = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "JSON inválido."}, status=400)

    nome = " ".join(str(payload.get("nome", "")).split())
    definicao = payload.get("definicao")
    if not nome or len(nome) > 100:
        return JsonResponse({"error": "Informe o nome do tema (até 100 caracteres)."}, status=400)
    erros = validar_tema(definicao)
    if erros:
        return JsonResponse({"error": "Tema inválido: " + "; ".join(erros)}, status=400)

    definicao = {**definicao, "nome": nome}
    existente = TemaDiagrama.objects.filter(nome__iexact=nome).first()
    if existente:
        if not (request.user.is_superuser or existente.criado_por_id == request.user.id):
            return JsonResponse({"error": "Já existe um tema com esse nome criado por outra pessoa."}, status=409)
        existente.nome, existente.definicao = nome, definicao
        existente.save(update_fields=["nome", "definicao", "atualizado_em"])
        tema, status = existente, 200
    else:
        tema, status = TemaDiagrama.objects.create(nome=nome, definicao=definicao, criado_por=request.user), 201
    return JsonResponse({"tema": serializar_tema(tema, request.user), "results": temas_para_editor(request.user)}, status=status)


@require_http_methods(["DELETE"])
def api_tema_detalhe(request, tema_id):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Autenticação necessária."}, status=401)
    tema = TemaDiagrama.objects.filter(pk=tema_id).first()
    if tema is None:
        return JsonResponse({"error": "Tema não encontrado."}, status=404)
    if not (request.user.is_superuser or (tema.criado_por_id and tema.criado_por_id == request.user.id)):
        return JsonResponse({"error": "Só quem criou o tema (ou um administrador) pode excluí-lo."}, status=403)
    tema.delete()
    return JsonResponse({"results": temas_para_editor(request.user)})
