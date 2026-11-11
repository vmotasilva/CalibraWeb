"""Editor visual das apresentações: slides automáticos e manuais (grade), com prévia dos cards ao vivo.

A página (`telao_editor.html`) guarda tudo em memória e só grava ao clicar em Salvar (`editor_salvar`).
As demais rotas são auxiliares e só leem: prévia do conteúdo, instâncias de um card e "Personalizar".
"""
import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from shared.models import ModeloApresentacao

from . import cards, layout, providers

MAX_JSON = 400_000  # bytes aceitos em uma gravação


def _campos_json(user) -> dict:
    """Campos de filtro de cada módulo (para montar os formulários do editor)."""
    def um(k, c):
        cards_cfg = providers.CAMPOS_CONFIG.get(k, {}).get(c["nome"])
        return {"nome": c["nome"], "rotulo": c["rotulo"], "tipo": c["tipo"], "ajuda": c.get("ajuda", ""),
                "opcoes": [[str(v), r] for v, r in c["opcoes"]], "config": cards_cfg is not None, "cards": cards_cfg or []}

    return {k: [um(k, c) for c in providers.campos_filtro(k, user)] for k in providers.ROTULOS_PROVEDORES}


def _modelo_json(m: ModeloApresentacao) -> dict:
    return {"id": m.pk, "nome": m.nome, "descricao": m.descricao, "icone": m.icone or "bi-display",
            "duracao_padrao": m.duracao_padrao, "resumo": m.resumo, "tema": m.tema or "escuro", "compartilhada": m.compartilhada, "ativo": m.ativo}


@login_required
@never_cache
def editor(request, pk=None):
    if pk:
        modelo = get_object_or_404(ModeloApresentacao, pk=pk)
        if not modelo.editavel_por(request.user):
            return HttpResponseForbidden("Apenas quem criou a apresentação (ou um administrador) pode editá-la.")
        slides = layout.slides_do_modelo(modelo)
    else:
        modelo = ModeloApresentacao(criado_por=request.user, nome="", icone="bi-display")
        slides = layout.slides_da_geral()
        base = (request.GET.get("base") or "").strip()  # copia a Apresentação Geral ou outro modelo
        if base == providers.PLAYLIST_PADRAO:
            modelo.nome, modelo.icone = f"{providers.PLAYLISTS[base][0]} (cópia)", providers.PLAYLISTS[base][1]
        elif base[:1] == "m" and base[1:].isdigit():
            origem = providers.modelos_visiveis(request.user).filter(pk=int(base[1:])).first()
            if origem:
                modelo.nome, modelo.icone, modelo.descricao = f"{origem.nome} (cópia)", origem.icone, origem.descricao
                modelo.duracao_padrao, modelo.resumo, modelo.tema = origem.duracao_padrao, origem.resumo, origem.tema
                slides = layout.slides_do_modelo(origem)
    dados = {
        "modelo": _modelo_json(modelo), "slides": slides, "catalogo": cards.catalogo(), "campos": _campos_json(request.user),
        "layouts": layout.OPCOES_LAYOUT, "grade": {"colunas": cards.COLUNAS, "linhas": cards.LINHAS},
        "rotulos": {k: list(v) for k, v in providers.ROTULOS_PROVEDORES.items()},
        "urls": {"previa": reverse("telao_editor_previa"), "instancias": reverse("telao_editor_instancias"),
                 "personalizar": reverse("telao_editor_personalizar"), "salvar": reverse("telao_editor_salvar"),
                 "lista": reverse("telao_modelos"), "player": reverse("telao")},
    }
    return render(request, "shared/telao_editor.html", {"dados": dados, "modelo": modelo, "novo": not modelo.pk})


def _json_body(request):
    if len(request.body) > MAX_JSON:
        return None
    try:
        corpo = json.loads(request.body or b"{}")
    except ValueError:
        return None
    return corpo if isinstance(corpo, dict) else None


@login_required
@require_POST
def editor_salvar(request):
    dados = _json_body(request)
    if dados is None:
        return JsonResponse({"ok": False, "erros": ["Dados inválidos."]}, status=400)
    pk = dados.get("id")
    if pk:
        modelo = get_object_or_404(ModeloApresentacao, pk=pk)
        if not modelo.editavel_por(request.user):
            return JsonResponse({"ok": False, "erros": ["Apenas quem criou a apresentação (ou um administrador) pode editá-la."]}, status=403)
    else:
        modelo = ModeloApresentacao(criado_por=request.user)
    modelo.nome = str(dados.get("nome") or "").strip()[:100]
    modelo.descricao = str(dados.get("descricao") or "").strip()[:200]
    icone = str(dados.get("icone") or "").strip()
    modelo.icone = icone if icone.startswith("bi-") and len(icone) <= 40 else "bi-display"
    try:
        modelo.duracao_padrao = min(max(int(dados.get("duracao_padrao")), 5), 120)
    except (TypeError, ValueError):
        modelo.duracao_padrao = 15
    modelo.resumo = bool(dados.get("resumo"))
    modelo.tema = "claro" if dados.get("tema") == "claro" else "escuro"
    modelo.compartilhada = bool(dados.get("compartilhada"))
    modelo.ativo = dados.get("ativo", True) is not False
    modelo.slides = layout.limpar_slides(dados.get("slides"), request.user)
    erros = []
    if not modelo.nome:
        erros.append("Informe o nome da apresentação.")
    if not modelo.slides:
        erros.append("Adicione ao menos um slide.")
    if erros:
        return JsonResponse({"ok": False, "erros": erros}, status=400)
    modelo.itens = []  # a configuração antiga deixa de valer: `slides` é a fonte
    modelo.save()
    return JsonResponse({"ok": True, "id": modelo.pk, "slides": modelo.slides, "url": reverse("telao_editor", args=[modelo.pk])})


@login_required
@require_POST
def editor_previa(request):
    dados = _json_body(request)
    if dados is None:
        return JsonResponse({"erro": "Dados inválidos."}, status=400)
    token = providers._SEM_CACHE.set(True)  # no editor, o que se vê é o dado de agora
    try:
        return JsonResponse(layout.previa(request.user, dados.get("slide"), resumo=bool(dados.get("resumo"))))
    finally:
        providers._SEM_CACHE.reset(token)


@login_required
@require_GET
def editor_instancias(request):
    return JsonResponse({"instancias": layout.instancias(request.user, request.GET.get("card_id") or "")})


@login_required
@require_POST
def editor_personalizar(request):
    dados = _json_body(request)
    cfg = layout.limpar_slide(dados.get("slide") if dados else None, request.user)
    if cfg is None:
        return JsonResponse({"erro": "Slide inválido."}, status=400)
    novos = layout.limpar_slides(layout.materializar(request.user, cfg, resumo=bool((dados or {}).get("resumo"))), request.user)
    if not novos:
        return JsonResponse({"erro": "Este slide não tem dados para personalizar agora."}, status=409)
    return JsonResponse({"slides": novos})
