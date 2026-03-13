from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.db import models, transaction
from django.db.models.deletion import ProtectedError
from django.db.models import Count, Max
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from datetime import date as dt_date
from datetime import timedelta
from collections import OrderedDict
from io import BytesIO
import json
import unicodedata
from urllib.parse import urlencode
from shared.permissions import has_view_access

from .forms import ComentarioAuditoriaForm, ModeloAuditoriaForm, PerguntaAuditoriaForm, RegistroAuditoriaForm
from .models import (
    ComentarioAuditoria,
    ComentarioRespostaAuditoria,
    ModeloAuditoria,
    PerguntaAuditoria,
    RelatorioCompartilhadoAuditoria,
    RegistroAuditoria,
    RespostaAuditoria,
)


SPECIAL_VIEW_ALL_COLABORADORES_PERM = 'core.nav_pessoas_ver_todos_colaboradores'
REPORT_SHARE_SALT = "auditoria.registros_por_modelo.share"
REPORT_SHARE_MAX_AGE_SECONDS = 60 * 60 * 24 * 30  # 30 dias


def _build_registro_report_share_token(modelo_id: int, inicio: str = "", fim: str = "", subcategoria: str = "") -> str:
    payload = {
        "m": int(modelo_id),
        "i": (inicio or "").strip(),
        "f": (fim or "").strip(),
        "s": (subcategoria or "").strip(),
    }
    return signing.dumps(payload, salt=REPORT_SHARE_SALT, compress=True)


def _read_registro_report_share_token(token: str) -> dict | None:
    if not token:
        return None
    try:
        payload = signing.loads(token, salt=REPORT_SHARE_SALT, max_age=REPORT_SHARE_MAX_AGE_SECONDS)
    except signing.BadSignature:
        return None
    except signing.SignatureExpired:
        return None

    if not isinstance(payload, dict):
        return None
    try:
        modelo_id = int(payload.get("m"))
    except (TypeError, ValueError):
        return None

    return {
        "modelo_id": modelo_id,
        "inicio": str(payload.get("i") or "").strip(),
        "fim": str(payload.get("f") or "").strip(),
        "subcategoria": str(payload.get("s") or "").strip(),
    }


def _has_special_view_all_colaboradores_perm(user) -> bool:
    return bool(user and user.has_perm(SPECIAL_VIEW_ALL_COLABORADORES_PERM))


def _parse_grid_itens(raw: str) -> list[str]:
    if not raw:
        return []
    itens: list[str] = []
    seen: set[str] = set()
    for line in str(raw).splitlines():
        item = line.strip()
        if not item:
            continue
        if item in seen:
            continue
        seen.add(item)
        itens.append(item)
    return itens


def _get_grid_colunas_modelo(modelo: ModeloAuditoria) -> list[str]:
    return _parse_grid_itens(getattr(modelo, "grid_colunas", ""))


def _get_effective_grid_itens_for_create(modelo: ModeloAuditoria, raw_from_form: str) -> list[str]:
    """Determina as colunas/itens do GRID no momento de criar um registro."""
    cols_modelo = _get_grid_colunas_modelo(modelo)
    if cols_modelo:
        return cols_modelo
    return _parse_grid_itens(raw_from_form)


def _get_effective_grid_itens_for_edit(registro: RegistroAuditoria, raw_from_form: str) -> list[str]:
    """Determina as colunas/itens do GRID no momento de editar um registro.

    Quando o modelo tiver colunas pré-definidas, SEMPRE usa as colunas do modelo.
    Caso contrário, usa as colunas do formulário (se informadas) ou as já salvas no registro.
    """
    cols_modelo = _get_grid_colunas_modelo(registro.modelo)
    if cols_modelo:
        return cols_modelo
    from_form = _parse_grid_itens(raw_from_form)
    if from_form:
        return from_form
    return _parse_grid_itens(getattr(registro, "grid_itens", ""))


def _parse_comentarios_payload(raw_payload: str) -> dict[int, list[str]]:
    if not raw_payload:
        return {}
    try:
        data = json.loads(raw_payload)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}

    parsed: dict[int, list[str]] = {}
    for raw_key, raw_values in data.items():
        try:
            pergunta_id = int(str(raw_key).strip())
        except Exception:
            continue
        if not isinstance(raw_values, list):
            continue
        values: list[str] = []
        for item in raw_values:
            texto = str(item or "").strip()
            if texto:
                values.append(texto)
        if values:
            parsed[pergunta_id] = values
    return parsed


def _replace_comentarios_resposta(
    registro: RegistroAuditoria,
    perguntas,
    raw_payload: str,
    autor,
) -> None:
    payload = _parse_comentarios_payload(raw_payload)
    allowed_ids = {int(p.id) for p in perguntas}

    ComentarioRespostaAuditoria.objects.filter(registro=registro).delete()

    novos = []
    for pergunta_id, textos in payload.items():
        if pergunta_id not in allowed_ids:
            continue
        for texto in textos:
            novos.append(
                ComentarioRespostaAuditoria(
                    registro=registro,
                    pergunta_id=pergunta_id,
                    autor=autor,
                    texto=texto,
                    data_referencia=registro.data_auditoria,
                )
            )
    if novos:
        ComentarioRespostaAuditoria.objects.bulk_create(novos)


def _build_comentarios_por_pergunta(registro: RegistroAuditoria) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    comentarios = (
        ComentarioRespostaAuditoria.objects.filter(registro=registro)
        .only("pergunta_id", "texto")
        .order_by("criado_em", "id")
    )
    for comentario in comentarios:
        key = str(comentario.pergunta_id)
        result.setdefault(key, []).append((comentario.texto or "").strip())
    return result


def _normalize_text_token(value: str) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    normalized = unicodedata.normalize("NFKD", raw)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _fallback_cor_resposta(valor: str) -> str:
    token = _normalize_text_token(valor)
    if not token:
        return ""

    if token in {"na", "n/a", "n.a", "nao aplicavel", "nao se aplica", "não se aplica"}:
        return "#6c757d"
    if any(k in token for k in ["nao conforme", "não conforme", "reprov", "critico", "critico", "nao", "não"]):
        return "#dc3545"
    if any(k in token for k in ["parcial", "atencao", "alerta", "pendente", "em andamento"]):
        return "#fd7e14"
    if any(k in token for k in ["conforme", "aprov", "ok", "sim"]):
        return "#198754"
    return "#0d6efd"


def _resolve_cor_resposta(pergunta: PerguntaAuditoria, valor: str) -> str:
    if not (valor or "").strip():
        return ""

    method = getattr(pergunta, "get_cor_resposta", None)
    if callable(method):
        try:
            color = str(method(valor) or "").strip()
            if color:
                return color
        except Exception:
            pass

    return _fallback_cor_resposta(valor)


def _build_resumo_respostas_registro(registro: RegistroAuditoria) -> dict:
    """Monta estrutura consolidada por pergunta para exibição em blocos e exportação."""
    respostas = list(
        registro.respostas.select_related("pergunta").order_by("pergunta__ordem", "pergunta_id", "id")
    )
    comentarios_por_pergunta = _build_comentarios_por_pergunta(registro)
    dia_labels = dict(ModeloAuditoria.DIA_SEMANA_CHOICES)
    dia_keys = [k for k, _ in ModeloAuditoria.DIA_SEMANA_CHOICES]

    perguntas_consolidadas: "OrderedDict[int, dict]" = OrderedDict()
    for resposta in respostas:
        pergunta = resposta.pergunta
        item = perguntas_consolidadas.get(pergunta.id)
        if not item:
            item = {
                "pergunta_id": pergunta.id,
                "ordem": pergunta.ordem,
                "pergunta": pergunta.pergunta,
                "descricao_detalhada": pergunta.descricao_detalhada,
                "obrigatoria": pergunta.obrigatoria,
                "tipo_resposta_display": pergunta.get_tipo_resposta_display(),
                "subcategoria": (pergunta.subcategoria or "").strip(),
                "resposta_geral": "",
                "resposta_geral_cor": "",
                "respostas_por_dia": {},
                "respostas_por_dia_cores": {},
                "comentarios": comentarios_por_pergunta.get(str(pergunta.id), []),
            }
            perguntas_consolidadas[pergunta.id] = item

        valor = (resposta.valor or "").strip()
        cor_valor = _resolve_cor_resposta(pergunta, valor)
        if resposta.dia_semana:
            item["respostas_por_dia"][resposta.dia_semana] = valor
            item["respostas_por_dia_cores"][resposta.dia_semana] = cor_valor
        else:
            if item["resposta_geral"] and valor and valor != item["resposta_geral"]:
                item["resposta_geral"] = f"{item['resposta_geral']} | {valor}"
                item["resposta_geral_cor"] = ""
            elif valor:
                item["resposta_geral"] = valor
                item["resposta_geral_cor"] = cor_valor

    blocos_map: "OrderedDict[str, dict]" = OrderedDict()
    for item in perguntas_consolidadas.values():
        nome_subcategoria = item["subcategoria"] or "Sem sub-categoria"
        if nome_subcategoria not in blocos_map:
            blocos_map[nome_subcategoria] = {"nome": nome_subcategoria, "linhas": []}

        respostas_por_dia = item["respostas_por_dia"]
        has_resposta_dia = any((respostas_por_dia.get(k) or "").strip() for k in dia_keys)
        usa_colunas_dia = has_resposta_dia

        linha = {
            **item,
            "usa_colunas_dia": usa_colunas_dia,
            "dia_values": [respostas_por_dia.get(k, "") for k in dia_keys],
            "dia_cells": [
                {
                    "value": respostas_por_dia.get(k, ""),
                    "color": item["respostas_por_dia_cores"].get(k, ""),
                }
                for k in dia_keys
            ],
            "comentarios_texto": "\n".join(item["comentarios"]),
            "tem_resposta": bool((item["resposta_geral"] or "").strip() or has_resposta_dia),
        }
        blocos_map[nome_subcategoria]["linhas"].append(linha)

    blocos = list(blocos_map.values())
    total_perguntas = len(perguntas_consolidadas)
    preenchidas = sum(1 for b in blocos for l in b["linhas"] if l["tem_resposta"])
    percentual_preenchimento = round((preenchidas / total_perguntas) * 100, 1) if total_perguntas else 0
    exibir_dias = any(l["usa_colunas_dia"] for b in blocos for l in b["linhas"])

    return {
        "blocos": blocos,
        "total_perguntas": total_perguntas,
        "preenchidas": preenchidas,
        "percentual_preenchimento": percentual_preenchimento,
        "exibir_dias": exibir_dias,
        "dia_keys": dia_keys,
        "dia_labels": dia_labels,
        "comentarios_por_pergunta": comentarios_por_pergunta,
    }


def _parse_date_flexible(raw_value):
    if isinstance(raw_value, dt_date):
        return raw_value
    raw = str(raw_value or "").strip()
    if not raw:
        return None
    return parse_date(raw)


def _resolve_periodo_para_comentarios(data_auditoria_raw, periodo_inicio_raw, periodo_fim_raw):
    data_auditoria = _parse_date_flexible(data_auditoria_raw)
    periodo_inicio = _parse_date_flexible(periodo_inicio_raw)
    periodo_fim = _parse_date_flexible(periodo_fim_raw)

    if not periodo_inicio and data_auditoria:
        periodo_inicio = data_auditoria
    if not periodo_fim and data_auditoria:
        periodo_fim = data_auditoria

    if periodo_inicio and periodo_fim and periodo_inicio > periodo_fim:
        periodo_inicio, periodo_fim = periodo_fim, periodo_inicio
    return periodo_inicio, periodo_fim


def _filter_comentarios_resposta_por_periodo(comentarios_qs, inicio=None, fim=None):
    if inicio:
        comentarios_qs = comentarios_qs.filter(
            models.Q(data_referencia__gte=inicio)
            | (models.Q(data_referencia__isnull=True) & models.Q(registro__data_auditoria__gte=inicio))
        )
    if fim:
        comentarios_qs = comentarios_qs.filter(
            models.Q(data_referencia__lte=fim)
            | (models.Q(data_referencia__isnull=True) & models.Q(registro__data_auditoria__lte=fim))
        )
    return comentarios_qs


def _build_comentarios_por_pergunta_qs(comentarios_qs, include_data=False) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for comentario in comentarios_qs:
        texto = (comentario.texto or "").strip()
        if include_data:
            data_vinculada = comentario.data_referencia or getattr(comentario.registro, "data_auditoria", None)
            if data_vinculada:
                texto = f"[{data_vinculada:%d/%m/%Y}] {texto}"
        key = str(comentario.pergunta_id)
        result.setdefault(key, []).append(texto)
    return result


def _build_comentarios_pre_registro_por_periodo(perguntas, inicio=None, fim=None):
    comentarios_qs = (
        ComentarioRespostaAuditoria.objects.filter(pergunta__in=perguntas)
        .select_related("registro")
        .order_by("criado_em", "id")
    )
    comentarios_qs = _filter_comentarios_resposta_por_periodo(comentarios_qs, inicio=inicio, fim=fim)
    return _build_comentarios_por_pergunta_qs(comentarios_qs, include_data=True)


def _auditoria_is_admin(user) -> bool:
    return bool(
        getattr(user, "is_staff", False)
        or getattr(user, "is_superuser", False)
        or _has_special_view_all_colaboradores_perm(user)
    )


def _has_nav_view_access(user, view_name: str) -> bool:
    try:
        return bool(has_view_access(user, view_name))
    except Exception:
        return True


def _make_unique_modelo_copy_nome(orig_nome: str) -> str:
    orig_nome = (orig_nome or "").strip() or "Modelo"
    base = f"{orig_nome} (Cópia)"
    nome = base
    i = 2
    while ModeloAuditoria.objects.filter(nome=nome).exists():
        nome = f"{orig_nome} (Cópia {i})"
        i += 1
    return nome


def _auditoria_can_update_modelo(user, modelo: ModeloAuditoria) -> bool:
    if _auditoria_is_admin(user):
        return True
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(modelo, "responsavel_id", None) == getattr(user, "pk", None):
        return True
    return modelo.responsaveis.filter(pk=user.pk).exists()


def _filter_modelos_para_usuario(user, qs):
    if _auditoria_is_admin(user):
        return qs
    return qs.filter(models.Q(responsaveis=user) | models.Q(responsavel=user)).distinct()


def _filter_registros_para_usuario(user, qs):
    if _auditoria_is_admin(user):
        return qs
    return qs.filter(models.Q(modelo__responsaveis=user) | models.Q(modelo__responsavel=user)).distinct()


def _get_next_pergunta_ordem(modelo_id: int) -> int:
    """Retorna a próxima ordem (max+1) para perguntas de um modelo."""
    if not modelo_id:
        return 1
    max_ordem = (
        PerguntaAuditoria.objects.filter(modelo_id=modelo_id)
        .aggregate(max_val=Max("ordem"))
        .get("max_val")
    )
    return (max_ordem or 0) + 1


@login_required
def api_next_pergunta_ordem(request):
    """API: devolve a próxima ordem para o modelo selecionado."""
    modelo_id = (request.GET.get("modelo") or "").strip()
    if not (modelo_id and modelo_id.isdigit()):
        return JsonResponse({"next": 1})
    return JsonResponse({"next": _get_next_pergunta_ordem(int(modelo_id))})


@login_required
def api_modelo_subcategorias(request):
    """API: devolve as sub-categorias cadastradas para o modelo selecionado."""
    modelo_id = (request.GET.get("modelo") or "").strip()
    if not (modelo_id and modelo_id.isdigit()):
        return JsonResponse({"subcategorias": []})
    try:
        modelo = ModeloAuditoria.objects.get(pk=int(modelo_id))
    except ModeloAuditoria.DoesNotExist:
        return JsonResponse({"subcategorias": []})
    return JsonResponse({"subcategorias": modelo.subcategorias_list})


@login_required
def modulo_auditoria_view(request):
    modelos_qs = _filter_modelos_para_usuario(request.user, ModeloAuditoria.objects.all())
    total_modelos = modelos_qs.count()
    total_perguntas = PerguntaAuditoria.objects.filter(modelo__in=modelos_qs).count()
    total_registros = RegistroAuditoria.objects.filter(modelo__in=modelos_qs).count()
    registros_recentes = (
        _filter_registros_para_usuario(
            request.user,
            RegistroAuditoria.objects.select_related("modelo"),
        )
        .order_by("-data_auditoria")[:5]
    )

    context = {
        "total_modelos": total_modelos,
        "total_perguntas": total_perguntas,
        "total_registros": total_registros,
        "registros_recentes": registros_recentes,
    }
    return render(request, "auditoria/modulo_auditoria.html", context)


@login_required
def modelos_list(request):
    inicio = request.GET.get("inicio")
    fim = request.GET.get("fim")

    modelos = ModeloAuditoria.objects.annotate(total_perguntas=Count("perguntas"))
    if inicio:
        modelos = modelos.filter(criado_em__date__gte=inicio)
    if fim:
        modelos = modelos.filter(criado_em__date__lte=fim)

    context = {"modelos": modelos.order_by("nome"), "inicio": inicio, "fim": fim}
    return render(request, "auditoria/modelos_list.html", context)


@login_required
def modelo_create(request):
    if not _auditoria_is_admin(request.user):
        messages.error(request, "Apenas usuários Staff/Superuser podem criar modelos de auditoria.")
        return redirect("auditoria:modelos_list")
    if request.method == "POST":
        form = ModeloAuditoriaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Modelo de auditoria criado com sucesso.")
            return redirect("auditoria:modelos_list")
    else:
        form = ModeloAuditoriaForm()
    return render(request, "auditoria/modelo_form.html", {"form": form, "modo": "novo"})


@login_required
def modelo_edit(request, pk):
    modelo = get_object_or_404(ModeloAuditoria, pk=pk)
    if not _auditoria_can_update_modelo(request.user, modelo):
        messages.error(request, "Você não tem permissão para atualizar este modelo de auditoria.")
        return redirect("auditoria:modelos_list")
    if request.method == "POST":
        form = ModeloAuditoriaForm(request.POST, instance=modelo)
        if form.is_valid():
            form.save()
            messages.success(request, "Modelo de auditoria atualizado com sucesso.")
            return redirect("auditoria:modelos_list")
    else:
        form = ModeloAuditoriaForm(instance=modelo)
    return render(request, "auditoria/modelo_form.html", {"form": form, "modo": "edicao", "modelo": modelo})


@login_required
def modelo_delete(request, pk):
    modelo = get_object_or_404(ModeloAuditoria, pk=pk)
    if not _auditoria_can_update_modelo(request.user, modelo):
        messages.error(request, "Você não tem permissão para remover este modelo de auditoria.")
        return redirect("auditoria:modelos_list")
    if request.method == "POST":
        try:
            modelo.delete()
            messages.success(request, "Modelo removido com sucesso.")
        except ProtectedError:
            # RegistroAuditoria usa PROTECT para preservar histórico e impedir exclusões acidentais.
            messages.error(
                request,
                "Não foi possível remover este modelo porque ele possui registros de auditoria vinculados.",
            )
        return redirect("auditoria:modelos_list")
    return render(request, "auditoria/modelo_confirm_delete.html", {"modelo": modelo})


@login_required
def perguntas_list(request):
    modelo_id = request.GET.get("modelo")
    subcategoria = (request.GET.get("subcategoria") or "").strip()
    perguntas = PerguntaAuditoria.objects.select_related("modelo")
    if modelo_id:
        perguntas = perguntas.filter(modelo_id=modelo_id)
    if subcategoria:
        perguntas = perguntas.filter(subcategoria=subcategoria)

    subcategorias = []
    if modelo_id and str(modelo_id).isdigit():
        try:
            modelo = ModeloAuditoria.objects.get(pk=int(modelo_id))
            subcategorias = modelo.subcategorias_list
        except ModeloAuditoria.DoesNotExist:
            subcategorias = []

    context = {
        "perguntas": perguntas.order_by("modelo__nome", "subcategoria", "ordem", "id"),
        "modelos": ModeloAuditoria.objects.filter(ativo=True).order_by("nome"),
        "modelo_id": modelo_id,
        "subcategoria": subcategoria,
        "subcategorias": subcategorias,
    }
    return render(request, "auditoria/perguntas_list.html", context)


@login_required
def perguntas_bulk_set_subcategoria(request):
    if not _auditoria_is_admin(request.user):
        messages.error(request, "Apenas usuários Staff/Superuser podem gerenciar perguntas.")
        return redirect("auditoria:perguntas_list")
    if request.method != "POST":
        return redirect("auditoria:perguntas_list")

    modelo_id = (request.POST.get("modelo") or "").strip()
    subcategoria = (request.POST.get("subcategoria") or "").strip()
    pergunta_ids = request.POST.getlist("pergunta_ids")

    if not (modelo_id and modelo_id.isdigit()):
        messages.error(request, "Selecione um modelo para aplicar sub-categoria em lote.")
        return redirect("auditoria:perguntas_list")
    if not pergunta_ids:
        messages.error(request, "Selecione pelo menos 1 pergunta.")
        url = reverse("auditoria:perguntas_list")
        return redirect(f"{url}?{urlencode({'modelo': modelo_id})}")

    modelo = get_object_or_404(ModeloAuditoria, pk=int(modelo_id))

    # Se o modelo tiver subcategorias cadastradas, validamos a escolha.
    if subcategoria:
        allowed = modelo.subcategorias_list
        if allowed:
            allowed_lower = {a.lower() for a in allowed}
            if subcategoria.lower() not in allowed_lower:
                messages.error(request, "Sub-categoria inválida para este modelo.")
                url = reverse("auditoria:perguntas_list")
                return redirect(f"{url}?{urlencode({'modelo': modelo_id})}")

    # Converte IDs e limita atualização apenas às perguntas do modelo.
    ids_int: list[int] = []
    for raw in pergunta_ids:
        s = str(raw).strip()
        if not s.isdigit():
            continue
        ids_int.append(int(s))

    if not ids_int:
        messages.error(request, "Selecione pelo menos 1 pergunta válida.")
        url = reverse("auditoria:perguntas_list")
        return redirect(f"{url}?{urlencode({'modelo': modelo_id})}")

    updated = (
        PerguntaAuditoria.objects.filter(id__in=ids_int, modelo_id=int(modelo_id))
        .update(subcategoria=subcategoria)
    )

    messages.success(request, f"Sub-categoria aplicada em {updated} pergunta(s).")
    params = {"modelo": modelo_id}
    if subcategoria:
        params["subcategoria"] = subcategoria
    url = reverse("auditoria:perguntas_list")
    return redirect(f"{url}?{urlencode(params)}")


@login_required
def pergunta_create(request):
    if not _auditoria_is_admin(request.user):
        messages.error(request, "Apenas usuários Staff/Superuser podem gerenciar perguntas.")
        return redirect("auditoria:perguntas_list")
    if request.method == "POST":
        form = PerguntaAuditoriaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Pergunta cadastrada com sucesso.")
            modelo_id = getattr(form.instance, "modelo_id", None)
            params = {}
            if modelo_id:
                params["modelo"] = modelo_id
            subcategoria = (getattr(form.instance, "subcategoria", "") or "").strip()
            if subcategoria:
                params["subcategoria"] = subcategoria
            url = reverse("auditoria:perguntas_list")
            if params:
                url = f"{url}?{urlencode(params)}"
            return redirect(url)
    else:
        initial = {}
        modelo_id = request.GET.get("modelo")
        if modelo_id:
            initial["modelo"] = modelo_id
            subcategoria = (request.GET.get("subcategoria") or "").strip()
            if subcategoria:
                initial["subcategoria"] = subcategoria
            if str(modelo_id).isdigit():
                initial["ordem"] = _get_next_pergunta_ordem(int(modelo_id))
        form = PerguntaAuditoriaForm(initial=initial)
    return render(request, "auditoria/pergunta_form.html", {"form": form, "modo": "novo"})


@login_required
def pergunta_duplicate(request, pk):
    if not _auditoria_is_admin(request.user):
        messages.error(request, "Apenas usuários Staff/Superuser podem gerenciar perguntas.")
        return redirect("auditoria:perguntas_list")
    if request.method != "POST":
        return redirect("auditoria:perguntas_list")

    pergunta = get_object_or_404(PerguntaAuditoria, pk=pk)
    with transaction.atomic():
        nova = PerguntaAuditoria(
            modelo_id=pergunta.modelo_id,
            pergunta=pergunta.pergunta,
            descricao_detalhada=pergunta.descricao_detalhada,
            tipo_resposta=pergunta.tipo_resposta,
            preenchimento_semanal=pergunta.preenchimento_semanal,
            opcoes_resposta=pergunta.opcoes_resposta,
            opcoes_resposta_cores=pergunta.opcoes_resposta_cores,
            aplicar_no_grid=pergunta.aplicar_no_grid,
            ordem=_get_next_pergunta_ordem(pergunta.modelo_id),
            subcategoria=pergunta.subcategoria,
            obrigatoria=pergunta.obrigatoria,
            ativo=pergunta.ativo,
        )
        nova.save()

    messages.success(request, "Pergunta duplicada com sucesso.")
    params = {}
    if pergunta.modelo_id:
        params["modelo"] = pergunta.modelo_id
    subcategoria = (pergunta.subcategoria or "").strip()
    if subcategoria:
        params["subcategoria"] = subcategoria
    url = reverse("auditoria:perguntas_list")
    if params:
        url = f"{url}?{urlencode(params)}"
    return redirect(url)


@login_required
def modelo_duplicate(request, pk):
    if not _auditoria_is_admin(request.user):
        messages.error(request, "Apenas usuários Staff/Superuser podem criar modelos de auditoria.")
        return redirect("auditoria:modelos_list")
    if request.method != "POST":
        return redirect("auditoria:modelos_list")

    modelo = get_object_or_404(ModeloAuditoria, pk=pk)
    nome_sugerido = f"{modelo.nome} (Cópia)"
    nome_informado = (request.POST.get("novo_nome") or "").strip()

    if nome_informado:
        if ModeloAuditoria.objects.filter(nome=nome_informado).exists():
            messages.error(request, "Já existe um modelo com este nome. Escolha outro nome para a cópia.")
            return redirect("auditoria:modelos_list")
        novo_nome = nome_informado
    else:
        # Mantém comportamento antigo quando nenhum nome é informado no formulário.
        novo_nome = _make_unique_modelo_copy_nome(modelo.nome)

    # Se o usuário manteve o padrão "(Cópia)", garantimos unicidade automática.
    if novo_nome == nome_sugerido and ModeloAuditoria.objects.filter(nome=novo_nome).exists():
        novo_nome = _make_unique_modelo_copy_nome(modelo.nome)

    with transaction.atomic():
        novo_modelo = ModeloAuditoria(
            nome=novo_nome,
            objeto_auditoria=modelo.objeto_auditoria,
            link_sharepoint=modelo.link_sharepoint,
            periodicidade=modelo.periodicidade,
            dia_semana=modelo.dia_semana,
            dias_quinzenal=modelo.dias_quinzenal,
            dia_mes=modelo.dia_mes,
            responsavel_id=modelo.responsavel_id,
            preenchimento_grid=modelo.preenchimento_grid,
            grid_rotulo_item=modelo.grid_rotulo_item,
            grid_colunas=modelo.grid_colunas,
            subcategorias=modelo.subcategorias,
            ativo=modelo.ativo,
        )
        novo_modelo.save()
        novo_modelo.responsaveis.set(modelo.responsaveis.all())

        perguntas = list(modelo.perguntas.all().order_by("ordem", "id"))
        novas_perguntas = [
            PerguntaAuditoria(
                modelo=novo_modelo,
                pergunta=p.pergunta,
                descricao_detalhada=p.descricao_detalhada,
                tipo_resposta=p.tipo_resposta,
                preenchimento_semanal=p.preenchimento_semanal,
                opcoes_resposta=p.opcoes_resposta,
                opcoes_resposta_cores=p.opcoes_resposta_cores,
                aplicar_no_grid=p.aplicar_no_grid,
                ordem=p.ordem,
                subcategoria=p.subcategoria,
                obrigatoria=p.obrigatoria,
                ativo=p.ativo,
            )
            for p in perguntas
        ]
        if novas_perguntas:
            PerguntaAuditoria.objects.bulk_create(novas_perguntas)

    messages.success(request, "Modelo duplicado com sucesso.")
    return redirect("auditoria:modelos_list")


@login_required
def pergunta_edit(request, pk):
    if not _auditoria_is_admin(request.user):
        messages.error(request, "Apenas usuários Staff/Superuser podem gerenciar perguntas.")
        return redirect("auditoria:perguntas_list")
    pergunta = get_object_or_404(PerguntaAuditoria, pk=pk)
    if request.method == "POST":
        form = PerguntaAuditoriaForm(request.POST, instance=pergunta)
        if form.is_valid():
            form.save()
            messages.success(request, "Pergunta atualizada com sucesso.")
            modelo_id = getattr(form.instance, "modelo_id", None)
            params = {}
            if modelo_id:
                params["modelo"] = modelo_id
            subcategoria = (getattr(form.instance, "subcategoria", "") or "").strip()
            if subcategoria:
                params["subcategoria"] = subcategoria
            url = reverse("auditoria:perguntas_list")
            if params:
                url = f"{url}?{urlencode(params)}"
            return redirect(url)
    else:
        form = PerguntaAuditoriaForm(instance=pergunta)
    return render(request, "auditoria/pergunta_form.html", {"form": form, "modo": "edicao", "pergunta": pergunta})


@login_required
def pergunta_delete(request, pk):
    if not _auditoria_is_admin(request.user):
        messages.error(request, "Apenas usuários Staff/Superuser podem gerenciar perguntas.")
        return redirect("auditoria:perguntas_list")
    pergunta = get_object_or_404(PerguntaAuditoria, pk=pk)
    if request.method == "POST":
        pergunta.delete()
        messages.success(request, "Pergunta removida com sucesso.")
        return redirect("auditoria:perguntas_list")
    return render(request, "auditoria/pergunta_confirm_delete.html", {"pergunta": pergunta})


@login_required
def registros_list(request):
    # Tela geral de "Registros" não é mais necessária.
    # Mantemos a URL por compatibilidade e redirecionamos para o Dashboard.
    params = {}
    for k in ("inicio", "fim", "modelo"):
        v = (request.GET.get(k) or "").strip()
        if v:
            params[k] = v

    url = reverse("auditoria:dashboard")
    if params:
        url = f"{url}?{urlencode(params)}"
    return redirect(url)


@login_required
def selecionar_modelo_preenchimento(request):
    """Lista modelos ativos para o usuário escolher qual preencher"""
    q = (request.GET.get("q") or "").strip()
    responsavel_id = (request.GET.get("responsavel") or "").strip()
    periodicidade = (request.GET.get("periodicidade") or "").strip()
    pendentes = (request.GET.get("pendentes") or "").strip().lower()

    if not _auditoria_is_admin(request.user):
        responsavel_id = str(request.user.pk)

    modelos = _filter_modelos_para_usuario(request.user, ModeloAuditoria.objects.filter(ativo=True))
    if q:
        modelos = modelos.filter(models.Q(nome__icontains=q) | models.Q(objeto_auditoria__icontains=q))
    if responsavel_id:
        modelos = modelos.filter(
            models.Q(responsaveis__id=responsavel_id) | models.Q(responsavel_id=responsavel_id)
        ).distinct()
    if periodicidade:
        modelos = modelos.filter(periodicidade=periodicidade)

    if pendentes == "mes":
        from datetime import timedelta
        from django.db.models import Exists, OuterRef, Q
        from django.utils import timezone

        from auditoria.models import RegistroAuditoria

        hoje = timezone.localdate()
        month_start = hoje.replace(day=1)
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)

        registro_mes_qs = RegistroAuditoria.objects.filter(
            modelo_id=OuterRef("pk"),
            data_auditoria__gte=month_start,
            data_auditoria__lt=next_month,
        )
        registro_algum_qs = RegistroAuditoria.objects.filter(modelo_id=OuterRef("pk"))

        modelos = modelos.annotate(
            _tem_registro_mes=Exists(registro_mes_qs),
            _tem_registro_algum=Exists(registro_algum_qs),
        ).filter(
            Q(periodicidade="UNICA", _tem_registro_algum=False)
            | (Q(periodicidade__in=[
                "DIARIA",
                "SEMANAL",
                "QUINZENAL",
                "MENSAL",
                "TRIMESTRAL",
                "SEMESTRAL",
                "ANUAL",
            ])
            & Q(_tem_registro_mes=False))
        )

    modelos = modelos.annotate(
        total_perguntas=Count("perguntas", filter=models.Q(perguntas__ativo=True))
    ).order_by("nome")

    User = get_user_model()
    modelos_com_responsavel = _filter_modelos_para_usuario(
        request.user,
        ModeloAuditoria.objects.filter(
            ativo=True,
        ).filter(
            models.Q(responsaveis__isnull=False) | models.Q(responsavel__isnull=False)
        ),
    )
    ids_m2m = list(modelos_com_responsavel.values_list("responsaveis__id", flat=True))
    ids_fk = list(modelos_com_responsavel.values_list("responsavel_id", flat=True))
    responsaveis_ids = {i for i in ids_m2m + ids_fk if i}
    responsaveis = User.objects.filter(id__in=responsaveis_ids).order_by("username")

    context = {
        "modelos": modelos,
        "q": q,
        "responsavel_id": responsavel_id,
        "periodicidade": periodicidade,
        "pendentes": pendentes,
        "periodicidade_choices": ModeloAuditoria.PERIODICIDADE_CHOICES,
        "responsaveis": responsaveis,
    }
    return render(request, "auditoria/selecionar_modelo.html", context)


@login_required
def registro_create(request, modelo_id=None):
    """Cria novo registro de auditoria para um modelo específico"""
    modelos_qs = _filter_modelos_para_usuario(
        request.user,
        ModeloAuditoria.objects.filter(ativo=True),
    )

    if modelo_id:
        modelo = get_object_or_404(modelos_qs, pk=modelo_id)
    else:
        modelo_id = request.GET.get("modelo")
        if modelo_id:
            modelo = get_object_or_404(modelos_qs, pk=modelo_id)
        else:
            return redirect("auditoria:selecionar_modelo_preenchimento")
    
    perguntas = PerguntaAuditoria.objects.filter(modelo=modelo, ativo=True).order_by("subcategoria", "ordem", "id")
    
    dias_semana_choices = list(ModeloAuditoria.DIA_SEMANA_CHOICES)
    is_semanal = modelo.periodicidade == "SEMANAL"
    is_diaria_ou_unica = modelo.periodicidade in ("DIARIA", "UNICA")
    grid_enabled = bool(getattr(modelo, "preenchimento_grid", False) or _get_grid_colunas_modelo(modelo))

    perguntas_por_dia = [
        p for p in perguntas if is_semanal and getattr(p, "preenchimento_semanal", "UNICO") == "POR_DIA"
    ]
    # Em modo GRID com colunas/itens definidos, repetimos o conjunto de perguntas por coluna.
    # (Neste modo, não filtramos por "aplicar_no_grid".)
    grid_perguntas = [p for p in perguntas if p not in perguntas_por_dia]
    comentarios_atuais = {}

    if request.method == "POST":
        post_data = request.POST
        if is_diaria_ou_unica:
            # Forçar período = data da auditoria (mesmo se vier em branco)
            post_data = request.POST.copy()
            data_auditoria = (post_data.get("data_auditoria") or "").strip()
            if data_auditoria:
                post_data["periodo_inicio"] = data_auditoria
                post_data["periodo_fim"] = data_auditoria

        form = RegistroAuditoriaForm(post_data)
        if form.is_valid():
            registro = form.save(commit=False)
            registro.modelo = modelo
            registro.avaliador = request.user

            grid_itens = []
            if grid_enabled:
                grid_itens = _get_effective_grid_itens_for_create(modelo, form.cleaned_data.get("grid_itens") or "")
                registro.grid_itens = "\n".join(grid_itens)

            registro.save()

            # Salvar respostas
            erros = []

            # Perguntas padrão (não-POR_DIA)
            if grid_enabled and grid_itens:
                for pergunta in grid_perguntas:
                    for idx, item in enumerate(grid_itens):
                        field_name = f"grid_{pergunta.id}_{idx}"
                        valor = request.POST.get(field_name, "").strip()
                        if not valor and pergunta.obrigatoria:
                            erros.append(f"A pergunta '{pergunta.pergunta}' é obrigatória para {item}.")
                        RespostaAuditoria.objects.create(
                            registro=registro,
                            pergunta=pergunta,
                            dia_semana=None,
                            grid_item=item,
                            valor=valor,
                        )
            else:
                for pergunta in grid_perguntas:
                    valor = request.POST.get(f"resposta_{pergunta.id}", "").strip()
                    if not valor and pergunta.obrigatoria:
                        erros.append(f"A pergunta '{pergunta.pergunta}' é obrigatória.")
                    RespostaAuditoria.objects.create(
                        registro=registro,
                        pergunta=pergunta,
                        dia_semana=None,
                        grid_item="",
                        valor=valor,
                    )

            # Perguntas POR_DIA: no GRID, também repetimos por item/coluna.
            for pergunta in perguntas_por_dia:
                if grid_enabled and grid_itens:
                    for idx, item in enumerate(grid_itens):
                        for dia_key, _dia_label in dias_semana_choices:
                            field_name = f"griddia_{pergunta.id}_{idx}_{dia_key}"
                            valor = request.POST.get(field_name, "").strip()
                            if not valor and pergunta.obrigatoria:
                                erros.append(
                                    f"A pergunta '{pergunta.pergunta}' é obrigatória para {item} em {dict(dias_semana_choices).get(dia_key, dia_key)}."
                                )
                            RespostaAuditoria.objects.create(
                                registro=registro,
                                pergunta=pergunta,
                                dia_semana=dia_key,
                                grid_item=item,
                                valor=valor,
                            )
                else:
                    for dia_key, _dia_label in dias_semana_choices:
                        field_name = f"resposta_{pergunta.id}_{dia_key}"
                        valor = request.POST.get(field_name, "").strip()
                        if not valor and pergunta.obrigatoria:
                            erros.append(
                                f"A pergunta '{pergunta.pergunta}' é obrigatória para {dict(dias_semana_choices).get(dia_key, dia_key)}."
                            )
                        RespostaAuditoria.objects.create(
                            registro=registro,
                            pergunta=pergunta,
                            dia_semana=dia_key,
                            grid_item="",
                            valor=valor,
                        )
            
            if erros:
                for erro in erros:
                    messages.warning(request, erro)

            _replace_comentarios_resposta(
                registro=registro,
                perguntas=perguntas,
                raw_payload=request.POST.get("comentarios_payload", ""),
                autor=request.user,
            )
            
            messages.success(request, "Formulário de auditoria preenchido com sucesso!")
            return redirect("auditoria:registro_detail", pk=registro.pk)
        comentarios_atuais = {
            str(k): v for (k, v) in _parse_comentarios_payload(request.POST.get("comentarios_payload", "")).items()
        }
        if not comentarios_atuais:
            periodo_inicio_lookup, periodo_fim_lookup = _resolve_periodo_para_comentarios(
                post_data.get("data_auditoria"),
                post_data.get("periodo_inicio"),
                post_data.get("periodo_fim"),
            )
            comentarios_atuais = _build_comentarios_pre_registro_por_periodo(
                perguntas=perguntas,
                inicio=periodo_inicio_lookup,
                fim=periodo_fim_lookup,
            )
    else:
        initial = {"data_auditoria": dt_date.today()}
        if is_diaria_ou_unica:
            initial["periodo_inicio"] = initial["data_auditoria"]
            initial["periodo_fim"] = initial["data_auditoria"]
        form = RegistroAuditoriaForm(initial=initial)
        periodo_inicio_lookup, periodo_fim_lookup = _resolve_periodo_para_comentarios(
            initial.get("data_auditoria"),
            initial.get("periodo_inicio"),
            initial.get("periodo_fim"),
        )
        comentarios_atuais = _build_comentarios_pre_registro_por_periodo(
            perguntas=perguntas,
            inicio=periodo_inicio_lookup,
            fim=periodo_fim_lookup,
        )

    grid_itens = []
    if grid_enabled:
        raw_grid_itens = (getattr(form, "data", {}) or {}).get("grid_itens") or ""
        grid_itens = _get_effective_grid_itens_for_create(modelo, raw_grid_itens)
    grid_colunas_predefinidas = bool(_get_grid_colunas_modelo(modelo))

    context = {
        "form": form,
        "modelo": modelo,
        "perguntas": perguntas,
        "grid_enabled": grid_enabled,
        "grid_itens": grid_itens,
        "grid_colunas_predefinidas": grid_colunas_predefinidas,
        "grid_perguntas": grid_perguntas,
        "perguntas_por_dia": perguntas_por_dia,
        "dias_semana_choices": dias_semana_choices,
        "comentarios_atuais": comentarios_atuais,
    }
    return render(request, "auditoria/registro_form.html", context)


@login_required
def registro_edit(request, pk):
    """Edita um registro de auditoria existente"""
    registro = get_object_or_404(
        _filter_registros_para_usuario(
            request.user,
            RegistroAuditoria.objects.select_related("modelo"),
        ),
        pk=pk,
    )
    perguntas = PerguntaAuditoria.objects.filter(modelo=registro.modelo, ativo=True).order_by("subcategoria", "ordem", "id")
    
    dias_semana_choices = list(ModeloAuditoria.DIA_SEMANA_CHOICES)
    is_semanal = registro.modelo.periodicidade == "SEMANAL"
    is_diaria_ou_unica = registro.modelo.periodicidade in ("DIARIA", "UNICA")
    grid_enabled = bool(getattr(registro.modelo, "preenchimento_grid", False) or _get_grid_colunas_modelo(registro.modelo))

    perguntas_por_dia = [
        p for p in perguntas if is_semanal and getattr(p, "preenchimento_semanal", "UNICO") == "POR_DIA"
    ]
    grid_perguntas = [p for p in perguntas if p not in perguntas_por_dia]
    respostas_atuais = {}
    comentarios_atuais = {}

    if request.method == "POST":
        post_data = request.POST
        if is_diaria_ou_unica:
            post_data = request.POST.copy()
            data_auditoria = (post_data.get("data_auditoria") or "").strip()
            if data_auditoria:
                post_data["periodo_inicio"] = data_auditoria
                post_data["periodo_fim"] = data_auditoria

        form = RegistroAuditoriaForm(post_data, instance=registro)
        if form.is_valid():
            registro = form.save(commit=False)

            grid_itens = []
            if grid_enabled:
                grid_itens = _get_effective_grid_itens_for_edit(registro, form.cleaned_data.get("grid_itens") or "")
                registro.grid_itens = "\n".join(grid_itens)

            registro.save()
            grid_item_to_index = {item: idx for idx, item in enumerate(grid_itens)}

            # Atualizar respostas existentes
            for pergunta in perguntas:
                is_por_dia = is_semanal and getattr(pergunta, "preenchimento_semanal", "UNICO") == "POR_DIA"

                if is_por_dia:
                    # Se antes era resposta única, remover para evitar duplicidade
                    RespostaAuditoria.objects.filter(
                        registro=registro,
                        pergunta=pergunta,
                        dia_semana__isnull=True,
                    ).delete()

                    if grid_enabled and grid_itens:
                        # Recriar POR_DIA por item/coluna
                        RespostaAuditoria.objects.filter(
                            registro=registro,
                            pergunta=pergunta,
                            dia_semana__isnull=False,
                        ).delete()

                        for idx, item in enumerate(grid_itens):
                            for dia_key, _dia_label in dias_semana_choices:
                                field_name = f"griddia_{pergunta.id}_{idx}_{dia_key}"
                                valor = request.POST.get(field_name, "").strip()
                                RespostaAuditoria.objects.update_or_create(
                                    registro=registro,
                                    pergunta=pergunta,
                                    dia_semana=dia_key,
                                    grid_item=item,
                                    defaults={"valor": valor},
                                )
                    else:
                        # POR_DIA sem GRID
                        RespostaAuditoria.objects.filter(
                            registro=registro,
                            pergunta=pergunta,
                            dia_semana__isnull=False,
                        ).exclude(grid_item="").delete()

                        for dia_key, _dia_label in dias_semana_choices:
                            field_name = f"resposta_{pergunta.id}_{dia_key}"
                            valor = request.POST.get(field_name, "").strip()
                            RespostaAuditoria.objects.update_or_create(
                                registro=registro,
                                pergunta=pergunta,
                                dia_semana=dia_key,
                                grid_item="",
                                defaults={"valor": valor},
                            )
                else:
                    # Se antes era por dia, remover linhas por dia
                    RespostaAuditoria.objects.filter(
                        registro=registro,
                        pergunta=pergunta,
                        dia_semana__isnull=False,
                    ).delete()

                    # GRID
                    if grid_enabled and grid_itens and pergunta in grid_perguntas:
                        # Remover itens que não existem mais
                        RespostaAuditoria.objects.filter(
                            registro=registro,
                            pergunta=pergunta,
                            dia_semana__isnull=True,
                        ).exclude(grid_item__in=grid_itens).delete()

                        for idx, item in enumerate(grid_itens):
                            field_name = f"grid_{pergunta.id}_{idx}"
                            valor = request.POST.get(field_name, "").strip()
                            RespostaAuditoria.objects.update_or_create(
                                registro=registro,
                                pergunta=pergunta,
                                dia_semana=None,
                                grid_item=item,
                                defaults={"valor": valor},
                            )
                    else:
                        # Remover possíveis respostas GRID antigas para esta pergunta
                        RespostaAuditoria.objects.filter(
                            registro=registro,
                            pergunta=pergunta,
                            dia_semana__isnull=True,
                        ).exclude(grid_item="").delete()

                        valor = request.POST.get(f"resposta_{pergunta.id}", "").strip()
                        RespostaAuditoria.objects.update_or_create(
                            registro=registro,
                            pergunta=pergunta,
                            dia_semana=None,
                            grid_item="",
                            defaults={"valor": valor},
                        )

            _replace_comentarios_resposta(
                registro=registro,
                perguntas=perguntas,
                raw_payload=request.POST.get("comentarios_payload", ""),
                autor=request.user,
            )
            
            messages.success(request, "Registro de auditoria atualizado com sucesso!")
            return redirect("auditoria:registro_detail", pk=registro.pk)
        else:
            comentarios_atuais = {
                str(k): v for (k, v) in _parse_comentarios_payload(request.POST.get("comentarios_payload", "")).items()
            }
    else:
        form = RegistroAuditoriaForm(instance=registro)
        # Preencher valores atuais das respostas

        grid_itens = _get_effective_grid_itens_for_edit(registro, getattr(registro, "grid_itens", "")) if grid_enabled else []
        grid_item_to_index = {item: idx for idx, item in enumerate(grid_itens)}

        for resposta in registro.respostas.all():
            if resposta.dia_semana:
                if grid_enabled and grid_itens and getattr(resposta, "grid_item", ""):
                    idx = grid_item_to_index.get(resposta.grid_item)
                    if idx is not None:
                        respostas_atuais[f"griddia_{resposta.pergunta_id}_{idx}_{resposta.dia_semana}"] = resposta.valor
                else:
                    respostas_atuais[f"resposta_{resposta.pergunta_id}_{resposta.dia_semana}"] = resposta.valor
            elif getattr(resposta, "grid_item", ""):
                idx = grid_item_to_index.get(resposta.grid_item)
                if idx is not None:
                    respostas_atuais[f"grid_{resposta.pergunta_id}_{idx}"] = resposta.valor
            else:
                respostas_atuais[f"resposta_{resposta.pergunta_id}"] = resposta.valor
        comentarios_atuais = _build_comentarios_por_pergunta(registro)

    context = {
        "form": form,
        "modelo": registro.modelo,
        "perguntas": perguntas,
        "grid_enabled": grid_enabled,
        "grid_itens": grid_itens,
        "grid_colunas_predefinidas": bool(_get_grid_colunas_modelo(registro.modelo)),
        "grid_perguntas": grid_perguntas,
        "perguntas_por_dia": perguntas_por_dia,
        "registro": registro,
        "respostas_atuais": respostas_atuais,
        "comentarios_atuais": comentarios_atuais,
        "edicao": True,
        "dias_semana_choices": dias_semana_choices,
    }
    return render(request, "auditoria/registro_form.html", context)


@login_required
def registro_detail(request, pk):
    registro = get_object_or_404(
        _filter_registros_para_usuario(
            request.user,
            RegistroAuditoria.objects.select_related("modelo", "avaliador"),
        ),
        pk=pk,
    )
    if request.method == "POST" and (request.POST.get("action") or "").strip() == "add_question_comment":
        pergunta_id_raw = (request.POST.get("pergunta_id") or "").strip()
        texto = (request.POST.get("comentario") or "").strip()
        if not pergunta_id_raw.isdigit():
            messages.error(request, "Pergunta inválida para comentário.")
            return redirect("auditoria:registro_detail", pk=registro.pk)

        pergunta = PerguntaAuditoria.objects.filter(
            id=int(pergunta_id_raw),
            modelo_id=registro.modelo_id,
            ativo=True,
        ).first()
        if not pergunta:
            messages.error(request, "Pergunta não encontrada para este registro.")
            return redirect("auditoria:registro_detail", pk=registro.pk)

        if not texto:
            messages.error(request, "Informe um comentário.")
            return redirect("auditoria:registro_detail", pk=registro.pk)
        if len(texto) > 8000:
            messages.error(request, "Comentário muito longo (máx. 8000 caracteres).")
            return redirect("auditoria:registro_detail", pk=registro.pk)

        ComentarioRespostaAuditoria.objects.create(
            registro=registro,
            pergunta=pergunta,
            autor=request.user,
            texto=texto,
            data_referencia=registro.data_auditoria,
        )
        messages.success(request, "Comentário adicionado com sucesso.")
        return redirect("auditoria:registro_detail", pk=registro.pk)

    resumo = _build_resumo_respostas_registro(registro)
    dias_semana_abrev = {
        "SEGUNDA": "Seg",
        "TERCA": "Ter",
        "QUARTA": "Qua",
        "QUINTA": "Qui",
        "SEXTA": "Sex",
        "SABADO": "Sáb",
        "DOMINGO": "Dom",
    }
    dias_semana_colunas = []
    for dia_key in resumo["dia_keys"]:
        label = resumo["dia_labels"].get(dia_key, dia_key)
        dias_semana_colunas.append(
            {
                "key": dia_key,
                "label": label,
                "short_label": dias_semana_abrev.get(dia_key, label[:3]),
            }
        )

    context = {
        "registro": registro,
        "blocos_respostas": resumo["blocos"],
        "exibir_dia_semana": resumo["exibir_dias"],
        "dias_semana_colunas": dias_semana_colunas,
        "total_respostas": resumo["total_perguntas"],
        "preenchidas": resumo["preenchidas"],
        "percentual_preenchimento": resumo["percentual_preenchimento"],
        "comentarios_por_pergunta": resumo["comentarios_por_pergunta"],
        "can_delete_registro": _has_nav_view_access(request.user, "auditoria:registro_delete"),
    }
    return render(request, "auditoria/registro_detail.html", context)


@login_required
def registro_exportar_pdf(request, pk):
    """Exporta o detalhe do registro em PDF no formato consolidado por sub-categoria."""
    from xml.sax.saxutils import escape
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    registro = get_object_or_404(
        _filter_registros_para_usuario(
            request.user,
            RegistroAuditoria.objects.select_related("modelo", "avaliador"),
        ),
        pk=pk,
    )

    resumo = _build_resumo_respostas_registro(registro)
    dia_keys = resumo["dia_keys"]
    dia_labels = resumo["dia_labels"]
    exibir_dias = resumo["exibir_dias"]

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=1.2 * cm,
        rightMargin=1.2 * cm,
        topMargin=1.0 * cm,
        bottomMargin=1.0 * cm,
        title=f"Relatório de Auditoria - Registro #{registro.id}",
    )

    styles = getSampleStyleSheet()
    style_title = ParagraphStyle(
        "AuditoriaTitle",
        parent=styles["Heading2"],
        fontSize=14,
        leading=17,
        spaceAfter=10,
    )
    style_section = ParagraphStyle(
        "AuditoriaSection",
        parent=styles["Heading4"],
        fontSize=10,
        leading=12,
        textColor=colors.HexColor("#0f5132"),
        spaceBefore=8,
        spaceAfter=4,
    )
    style_cell = ParagraphStyle(
        "AuditoriaCell",
        parent=styles["BodyText"],
        fontSize=8,
        leading=10,
    )
    style_cell_center = ParagraphStyle(
        "AuditoriaCellCenter",
        parent=style_cell,
        alignment=1,
    )
    style_cell_bold = ParagraphStyle(
        "AuditoriaCellBold",
        parent=style_cell,
        fontName="Helvetica-Bold",
    )

    elements = []

    avaliador = ""
    if registro.avaliador_id:
        avaliador = registro.avaliador.get_full_name() or registro.avaliador.username
    periodo = ""
    if registro.periodo_inicio and registro.periodo_fim:
        periodo = f"{registro.periodo_inicio:%d/%m/%Y} até {registro.periodo_fim:%d/%m/%Y}"
    elif registro.periodo_inicio:
        periodo = f"A partir de {registro.periodo_inicio:%d/%m/%Y}"
    elif registro.periodo_fim:
        periodo = f"Até {registro.periodo_fim:%d/%m/%Y}"

    info_rows = [
        [Paragraph("<b>Modelo</b>", style_cell_bold), Paragraph(escape(registro.modelo.nome or ""), style_cell)],
        [Paragraph("<b>Objeto da Auditoria</b>", style_cell_bold), Paragraph(escape(registro.modelo.objeto_auditoria or ""), style_cell)],
        [Paragraph("<b>Data da Auditoria</b>", style_cell_bold), Paragraph(escape(registro.data_auditoria.strftime("%d/%m/%Y") if registro.data_auditoria else ""), style_cell)],
        [Paragraph("<b>Período</b>", style_cell_bold), Paragraph(escape(periodo), style_cell)],
        [Paragraph("<b>Avaliador</b>", style_cell_bold), Paragraph(escape(avaliador), style_cell)],
        [Paragraph("<b>ITEM/O.S.</b>", style_cell_bold), Paragraph(escape(registro.item_os or ""), style_cell)],
        [Paragraph("<b>Observações</b>", style_cell_bold), Paragraph(escape(registro.observacoes or ""), style_cell)],
    ]
    info_table = Table(info_rows, colWidths=[4.2 * cm, 22.0 * cm], repeatRows=0)
    info_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d0d7de")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8f9fa")),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    dias_semana_abrev = {
        "SEGUNDA": "Seg",
        "TERCA": "Ter",
        "QUARTA": "Qua",
        "QUINTA": "Qui",
        "SEXTA": "Sex",
        "SABADO": "Sáb",
        "DOMINGO": "Dom",
    }

    for idx_bloco, bloco in enumerate(resumo["blocos"]):
        elements.append(Paragraph(f"Relatório de Auditoria - Registro #{registro.id}", style_title))

        info_rows = [
            [Paragraph("<b>Modelo</b>", style_cell_bold), Paragraph(escape(registro.modelo.nome or ""), style_cell)],
            [Paragraph("<b>Objeto da Auditoria</b>", style_cell_bold), Paragraph(escape(registro.modelo.objeto_auditoria or ""), style_cell)],
            [Paragraph("<b>Data da Auditoria</b>", style_cell_bold), Paragraph(escape(registro.data_auditoria.strftime("%d/%m/%Y") if registro.data_auditoria else ""), style_cell)],
            [Paragraph("<b>Período</b>", style_cell_bold), Paragraph(escape(periodo), style_cell)],
            [Paragraph("<b>Avaliador</b>", style_cell_bold), Paragraph(escape(avaliador), style_cell)],
            [Paragraph("<b>ITEM/O.S.</b>", style_cell_bold), Paragraph(escape(registro.item_os or ""), style_cell)],
            [Paragraph("<b>Observações</b>", style_cell_bold), Paragraph(escape(registro.observacoes or ""), style_cell)],
        ]
        info_table = Table(info_rows, colWidths=[4.2 * cm, 22.0 * cm], repeatRows=0)
        info_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d0d7de")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8f9fa")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.append(info_table)
        elements.append(Spacer(1, 8))

        elements.append(Paragraph(f"Sub-categoria: {escape(bloco['nome'])}", style_section))

        headers = ["Ordem", "Pergunta"]
        if exibir_dias:
            headers.extend([dias_semana_abrev.get(k, dia_labels.get(k, k)[:3]) for k in dia_keys])
        headers.append("Comentários")

        if exibir_dias:
            col_widths = [1.2 * cm, 7.2 * cm] + [1.4 * cm for _ in dia_keys] + [8.6 * cm]
        else:
            col_widths = [1.5 * cm, 11.0 * cm, 14.5 * cm]

        table_data = [[Paragraph(f"<b>{escape(h)}</b>", style_cell_center) for h in headers]]
        for linha in bloco["linhas"]:
            comentarios_texto = "<br/>".join(escape(c) for c in linha["comentarios"]) or "-"
            row = [
                Paragraph(escape(str(linha["ordem"])), style_cell_center),
                Paragraph(escape(linha["pergunta"]), style_cell),
            ]
            if exibir_dias:
                for k in dia_keys:
                    valor = (linha["respostas_por_dia"].get(k, "") or "").strip()
                    cor = (linha.get("respostas_por_dia_cores", {}).get(k, "") or "#6c757d").strip()
                    if valor:
                        row.append(Paragraph(f"<font color=\"{escape(cor)}\">&#9679;</font>", style_cell_center))
                    else:
                        row.append(Paragraph("-", style_cell_center))
            row.append(Paragraph(comentarios_texto, style_cell))
            table_data.append(row)

        bloco_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        bloco_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cfd6dd")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (0, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        elements.append(bloco_table)

        if idx_bloco < len(resumo["blocos"]) - 1:
            elements.append(PageBreak())

    doc.build(elements)
    buffer.seek(0)

    nome_modelo = "".join(c for c in (registro.modelo.nome or "modelo") if c.isalnum() or c in {" ", "-", "_"}).strip()
    if not nome_modelo:
        nome_modelo = f"modelo_{registro.modelo_id}"
    filename = f"relatorio_registro_{registro.id}_{nome_modelo}.pdf"

    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/pdf",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def registro_delete(request, pk):
    if request.method != "POST":
        return redirect("auditoria:registro_detail", pk=pk)

    if not _has_nav_view_access(request.user, "auditoria:registro_delete"):
        messages.error(request, "Acesso negado. Você não tem permissão para excluir registros de auditoria.")
        return redirect("auditoria:registro_detail", pk=pk)

    registro = get_object_or_404(
        _filter_registros_para_usuario(
            request.user,
            RegistroAuditoria.objects.select_related("modelo"),
        ),
        pk=pk,
    )

    if not _auditoria_can_update_modelo(request.user, registro.modelo):
        messages.error(request, "Acesso negado. Você não pode excluir este registro.")
        return redirect("auditoria:registro_detail", pk=pk)

    modelo_id = registro.modelo_id
    registro.delete()
    messages.success(request, "Registro de auditoria excluído com sucesso.")
    return redirect("auditoria:registros_por_modelo", modelo_id=modelo_id)


@login_required
def dashboard_auditoria(request):
    inicio = request.GET.get("inicio")
    fim = request.GET.get("fim")
    modelo_id = request.GET.get("modelo")
    responsavel_id = request.GET.get("responsavel")

    registros = _filter_registros_para_usuario(
        request.user,
        RegistroAuditoria.objects.select_related("modelo"),
    )

    if modelo_id:
        registros = registros.filter(modelo_id=modelo_id)
    if responsavel_id:
        registros = registros.filter(
            models.Q(modelo__responsaveis__id=responsavel_id) | models.Q(modelo__responsavel_id=responsavel_id)
        ).distinct()
    if inicio:
        registros = registros.filter(data_auditoria__gte=inicio)
    if fim:
        registros = registros.filter(data_auditoria__lte=fim)

    total_modelos = registros.values("modelo_id").distinct().count()
    total_registros = registros.count()

    por_modelo = list(
        registros.values("modelo__nome", "modelo__id")
        .annotate(total=Count("id"))
        .order_by("-total", "modelo__nome")
    )

    por_periodicidade_raw = list(
        registros.values("modelo__periodicidade")
        .annotate(total=Count("id"))
        .order_by("modelo__periodicidade")
    )

    periodicidade_map = dict(ModeloAuditoria.PERIODICIDADE_CHOICES)
    por_periodicidade = [
        {
            "periodicidade": item["modelo__periodicidade"],
            "periodicidade_label": periodicidade_map.get(item["modelo__periodicidade"], item["modelo__periodicidade"]),
            "total": item["total"],
        }
        for item in por_periodicidade_raw
    ]

    chart_modelo_labels = [item["modelo__nome"] for item in por_modelo]
    chart_modelo_values = [item["total"] for item in por_modelo]
    chart_periodicidade_labels = [item["periodicidade_label"] for item in por_periodicidade]
    chart_periodicidade_values = [item["total"] for item in por_periodicidade]
    
    # Lista de todos os modelos para o filtro
    todos_modelos = _filter_modelos_para_usuario(
        request.user,
        ModeloAuditoria.objects.filter(ativo=True),
    ).order_by("nome")
    modelo_selecionado = None
    if modelo_id:
        modelo_selecionado = ModeloAuditoria.objects.filter(pk=modelo_id).first()

    # Lista de responsáveis (usuários vinculados aos modelos)
    User = get_user_model()
    modelos_com_responsavel = _filter_modelos_para_usuario(
        request.user,
        ModeloAuditoria.objects.filter(
            models.Q(responsaveis__isnull=False) | models.Q(responsavel__isnull=False)
        ),
    )
    ids_m2m = list(modelos_com_responsavel.values_list("responsaveis__id", flat=True))
    ids_fk = list(modelos_com_responsavel.values_list("responsavel_id", flat=True))
    responsavel_ids = {i for i in ids_m2m + ids_fk if i}
    responsaveis = User.objects.filter(pk__in=responsavel_ids).order_by("username")
    responsavel_selecionado = None
    if responsavel_id:
        responsavel_selecionado = User.objects.filter(pk=responsavel_id).first()

    context = {
        "total_modelos": total_modelos,
        "total_registros": total_registros,
        "por_modelo": por_modelo,
        "por_periodicidade": por_periodicidade,
        "chart_modelo_labels": chart_modelo_labels,
        "chart_modelo_values": chart_modelo_values,
        "chart_periodicidade_labels": chart_periodicidade_labels,
        "chart_periodicidade_values": chart_periodicidade_values,
        "inicio": inicio,
        "fim": fim,
        "modelo_id": modelo_id,
        "responsavel_id": responsavel_id,
        "todos_modelos": todos_modelos,
        "modelo_selecionado": modelo_selecionado,
        "responsaveis": responsaveis,
        "responsavel_selecionado": responsavel_selecionado,
    }
    return render(request, "auditoria/dashboard_auditoria.html", context)


@login_required
def registros_por_modelo(request, modelo_id):
    """Lista todos os registros preenchidos de um modelo específico"""
    share_token_raw = (request.GET.get("share_token") or "").strip()
    targeted_share = None
    share_data = None
    is_read_only = False

    if share_token_raw:
        targeted_share = (
            RelatorioCompartilhadoAuditoria.objects.select_related("destinatario")
            .filter(token=share_token_raw, ativo=True)
            .first()
        )
        if targeted_share:
            if targeted_share.modelo_id != int(modelo_id):
                return HttpResponseForbidden("Link de compartilhamento inválido para este relatório.")
            if targeted_share.destinatario_id != request.user.id:
                return HttpResponseForbidden("Este compartilhamento é direcionado a outro usuário.")
            if targeted_share.is_expired:
                return HttpResponseForbidden("Este compartilhamento expirou.")

            is_read_only = True
            share_data = {
                "modelo_id": targeted_share.modelo_id,
                "inicio": targeted_share.inicio.isoformat() if targeted_share.inicio else "",
                "fim": targeted_share.fim.isoformat() if targeted_share.fim else "",
                "subcategoria": (targeted_share.subcategoria or "").strip(),
            }
        else:
            share_data = _read_registro_report_share_token(share_token_raw)
            is_read_only = bool(share_data and int(share_data.get("modelo_id", 0)) == int(modelo_id))
            if share_token_raw and not is_read_only:
                return HttpResponseForbidden("Link de compartilhamento inválido ou expirado.")

    if is_read_only:
        modelo = get_object_or_404(ModeloAuditoria.objects.all(), pk=modelo_id)
    else:
        modelo = get_object_or_404(
            _filter_modelos_para_usuario(request.user, ModeloAuditoria.objects.all()),
            pk=modelo_id,
        )

    if request.method == "POST" and is_read_only:
        return HttpResponseForbidden("Este link é somente leitura.")

    if request.method == "POST" and (request.POST.get("action") or "").strip() == "share_report_targeted":
        destinatario_raw = (request.POST.get("destinatario_id") or "").strip()
        if not destinatario_raw.isdigit():
            messages.error(request, "Selecione um destinatário válido.")
        else:
            User = get_user_model()
            destinatario = User.objects.filter(pk=int(destinatario_raw), is_active=True).first()
            if not destinatario:
                messages.error(request, "Destinatário não encontrado.")
            elif destinatario.id == request.user.id:
                messages.error(request, "Não é possível compartilhar para o próprio usuário.")
            else:
                inicio_tmp = parse_date((request.GET.get("inicio") or "").strip() or "")
                fim_tmp = parse_date((request.GET.get("fim") or "").strip() or "")
                subcat_tmp = (request.GET.get("subcategoria") or "").strip()
                if subcat_tmp and subcat_tmp not in modelo.subcategorias_list:
                    subcat_tmp = ""

                share_obj = RelatorioCompartilhadoAuditoria.objects.create(
                    modelo=modelo,
                    remetente=request.user,
                    destinatario=destinatario,
                    inicio=inicio_tmp,
                    fim=fim_tmp,
                    subcategoria=subcat_tmp,
                    expira_em=timezone.now() + timedelta(days=30),
                )
                redirect_url = reverse("auditoria:registros_por_modelo", args=[modelo.id])
                preserved = {}
                for k in ("inicio", "fim", "subcategoria", "page", "per_page"):
                    v = (request.GET.get(k) or "").strip()
                    if v:
                        preserved[k] = v
                preserved["share_created"] = str(share_obj.id)
                if preserved:
                    redirect_url = f"{redirect_url}?{urlencode(preserved)}"
                messages.success(request, "Relatório compartilhado com sucesso.")
                return redirect(redirect_url)

        redirect_url = reverse("auditoria:registros_por_modelo", args=[modelo.id])
        preserved = {}
        for k in ("inicio", "fim", "subcategoria", "page", "per_page"):
            v = (request.GET.get(k) or "").strip()
            if v:
                preserved[k] = v
        if preserved:
            redirect_url = f"{redirect_url}?{urlencode(preserved)}"
        return redirect(redirect_url)

    if targeted_share and is_read_only and not targeted_share.recebido_em:
        now = timezone.now()
        targeted_share.primeiro_acesso_em = targeted_share.primeiro_acesso_em or now
        targeted_share.recebido_em = now
        targeted_share.recebido_ip = (request.META.get("HTTP_X_FORWARDED_FOR") or request.META.get("REMOTE_ADDR") or "")[:45]
        targeted_share.recebido_user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:255]
        targeted_share.save(update_fields=["primeiro_acesso_em", "recebido_em", "recebido_ip", "recebido_user_agent"])

    if request.method == "POST" and (request.POST.get("action") or "").strip() == "add_comment":
        texto = (request.POST.get("comentario") or "").strip()
        if not texto:
            messages.error(request, "Informe um comentário.")
        elif len(texto) > 8000:
            messages.error(request, "Comentário muito longo (máx. 8000 caracteres).")
        else:
            ComentarioAuditoria.objects.create(modelo=modelo, autor=request.user, texto=texto)
            messages.success(request, "Comentário adicionado com sucesso.")

        redirect_url = reverse("auditoria:registros_por_modelo", args=[modelo.id])
        preserved = {}
        for k in ("inicio", "fim", "subcategoria", "page", "per_page"):
            v = (request.GET.get(k) or "").strip()
            if v:
                preserved[k] = v
        if preserved:
            redirect_url = f"{redirect_url}?{urlencode(preserved)}"
        return redirect(redirect_url)

    if request.method == "POST" and (request.POST.get("action") or "").strip() == "add_question_comment":
        pergunta_id_raw = (request.POST.get("pergunta_id") or "").strip()
        texto = (request.POST.get("comentario") or "").strip()
        comentario_data_raw = (request.POST.get("comentario_data") or "").strip()

        redirect_url = reverse("auditoria:registros_por_modelo", args=[modelo.id])
        preserved = {}
        for k in ("inicio", "fim", "subcategoria", "page", "per_page"):
            v = (request.GET.get(k) or "").strip()
            if v:
                preserved[k] = v
        if preserved:
            redirect_url = f"{redirect_url}?{urlencode(preserved)}"

        if not pergunta_id_raw.isdigit():
            messages.error(request, "Pergunta inválida para comentário.")
            return redirect(redirect_url)
        if not texto:
            messages.error(request, "Informe um comentário.")
            return redirect(redirect_url)
        if len(texto) > 8000:
            messages.error(request, "Comentário muito longo (máx. 8000 caracteres).")
            return redirect(redirect_url)
        if not comentario_data_raw:
            messages.error(request, "Informe a data do comentário para vincular ao período.")
            return redirect(redirect_url)

        comentario_data = parse_date(comentario_data_raw)
        if not comentario_data:
            messages.error(request, "Data do comentário inválida. Use o formato ANO-MÊS-DIA.")
            return redirect(redirect_url)

        pergunta = PerguntaAuditoria.objects.filter(
            id=int(pergunta_id_raw),
            modelo_id=modelo.id,
            ativo=True,
        ).first()
        if not pergunta:
            messages.error(request, "Pergunta não encontrada para este modelo.")
            return redirect(redirect_url)

        inicio_raw = (request.GET.get("inicio") or "").strip()
        fim_raw = (request.GET.get("fim") or "").strip()
        inicio = parse_date(inicio_raw) if inicio_raw else None
        fim = parse_date(fim_raw) if fim_raw else None

        registros_para_comentario = RegistroAuditoria.objects.filter(modelo=modelo)
        if inicio:
            registros_para_comentario = registros_para_comentario.filter(data_auditoria__gte=inicio)
        if fim:
            registros_para_comentario = registros_para_comentario.filter(data_auditoria__lte=fim)

        if inicio and comentario_data < inicio:
            messages.error(request, "A data do comentário está fora do período inicial filtrado.")
            return redirect(redirect_url)
        if fim and comentario_data > fim:
            messages.error(request, "A data do comentário está fora do período final filtrado.")
            return redirect(redirect_url)

        registro_alvo = registros_para_comentario.filter(data_auditoria=comentario_data).order_by("-id").first()

        ComentarioRespostaAuditoria.objects.create(
            registro=registro_alvo,
            pergunta=pergunta,
            autor=request.user,
            texto=texto,
            data_referencia=comentario_data,
        )
        if registro_alvo:
            messages.success(request, "Comentário da pergunta adicionado com sucesso.")
        else:
            messages.success(
                request,
                "Comentário da pergunta salvo para a data informada. Ele aparecerá ao criar um registro que inclua esse período.",
            )
        return redirect(redirect_url)

    if request.method == "POST" and (request.POST.get("action") or "").strip() == "delete_question_comment":
        comentario_id_raw = (request.POST.get("comentario_id") or "").strip()

        if not comentario_id_raw.isdigit():
            return JsonResponse({"success": False, "message": "Comentário inválido."}, status=400)

        comentario = ComentarioRespostaAuditoria.objects.filter(
            id=int(comentario_id_raw),
            pergunta__modelo_id=modelo.id,
        ).select_related("autor", "pergunta").first()

        if not comentario:
            return JsonResponse({"success": False, "message": "Comentário não encontrado."}, status=404)

        can_manage = _auditoria_is_admin(request.user) or (comentario.autor_id == request.user.id)
        if not can_manage:
            return JsonResponse(
                {"success": False, "message": "Você não tem permissão para remover este comentário."},
                status=403,
            )

        pergunta_id = comentario.pergunta_id
        comentario.delete()
        return JsonResponse({"success": True, "comentario_id": int(comentario_id_raw), "pergunta_id": pergunta_id})

    if is_read_only:
        inicio_raw = (share_data.get("inicio") or "").strip()
        fim_raw = (share_data.get("fim") or "").strip()
    else:
        inicio_raw = (request.GET.get("inicio") or "").strip()
        fim_raw = (request.GET.get("fim") or "").strip()
    subcategorias = list(modelo.subcategorias_list)
    if is_read_only:
        subcategoria_raw = (share_data.get("subcategoria") or "").strip()
    else:
        subcategoria_raw = (request.GET.get("subcategoria") or "").strip()
    subcategoria = subcategoria_raw if (subcategoria_raw and subcategoria_raw in subcategorias) else ""
    inicio = parse_date(inicio_raw) if inicio_raw else None
    fim = parse_date(fim_raw) if fim_raw else None

    per_page_raw = (request.GET.get("per_page") or "").strip()
    allowed_per_page = {10, 25, 50, 100}
    try:
        per_page = int(per_page_raw) if per_page_raw else 25
    except (TypeError, ValueError):
        per_page = 25
    if per_page not in allowed_per_page:
        per_page = 25

    registros_qs = RegistroAuditoria.objects.filter(modelo=modelo)
    if inicio:
        registros_qs = registros_qs.filter(data_auditoria__gte=inicio)
    if fim:
        registros_qs = registros_qs.filter(data_auditoria__lte=fim)

    registros_qs = registros_qs.select_related("avaliador").order_by("-criado_em", "-id")

    paginator = Paginator(registros_qs, per_page)
    page_obj = paginator.get_page((request.GET.get("page") or "").strip() or 1)

    base_params = {}
    if inicio_raw:
        base_params["inicio"] = inicio_raw
    if fim_raw:
        base_params["fim"] = fim_raw
    if subcategoria:
        base_params["subcategoria"] = subcategoria
    if is_read_only and share_token_raw:
        base_params["share_token"] = share_token_raw
    base_params["per_page"] = str(per_page)
    querystring_base = urlencode(base_params)
    querystring_with_page = querystring_base
    if querystring_with_page:
        querystring_with_page = f"{querystring_with_page}&page={page_obj.number}"
    else:
        querystring_with_page = f"page={page_obj.number}"

    comentarios_qs = ComentarioAuditoria.objects.filter(modelo=modelo).select_related("autor")
    if inicio:
        comentarios_qs = comentarios_qs.filter(criado_em__date__gte=inicio)
    if fim:
        comentarios_qs = comentarios_qs.filter(criado_em__date__lte=fim)
    comentarios = list(comentarios_qs.order_by("-criado_em", "-id"))

    perguntas_qs = PerguntaAuditoria.objects.filter(modelo=modelo, ativo=True)
    if subcategoria:
        perguntas_qs = perguntas_qs.filter(subcategoria=subcategoria)
    perguntas = list(perguntas_qs.order_by("ordem", "id"))
    pergunta_map = {p.id: p for p in perguntas}

    respostas_qs = (
        RespostaAuditoria.objects.filter(pergunta__in=perguntas, registro__in=registros_qs)
        .select_related("registro", "pergunta")
        .order_by("registro__data_auditoria", "id")
    )

    respostas_por_pergunta: dict[int, list[RespostaAuditoria]] = {}
    for r in respostas_qs:
        respostas_por_pergunta.setdefault(r.pergunta_id, []).append(r)

    comentarios_resposta_qs = (
        ComentarioRespostaAuditoria.objects.filter(pergunta__in=perguntas)
        .select_related("registro", "autor")
        .order_by("criado_em", "id")
    )
    comentarios_resposta_qs = _filter_comentarios_resposta_por_periodo(comentarios_resposta_qs, inicio=inicio, fim=fim)
    comentarios_resposta_por_pergunta: dict[str, list[dict[str, object]]] = {}
    can_admin = False if is_read_only else _auditoria_is_admin(request.user)
    for comentario in comentarios_resposta_qs:
        texto = (comentario.texto or "").strip()
        data_vinculada = comentario.data_referencia or getattr(comentario.registro, "data_auditoria", None)
        if data_vinculada:
            texto = f"[{data_vinculada:%d/%m/%Y}] {texto}"

        key = str(comentario.pergunta_id)
        comentarios_resposta_por_pergunta.setdefault(key, []).append(
            {
                "id": comentario.id,
                "texto": texto,
                "can_delete": bool(can_admin or comentario.autor_id == request.user.id),
            }
        )

    # Gráfico agregado: situações por subcategoria
    subcat_chart: dict | None = None
    if subcategorias:
        subcats_to_show = [subcategoria] if subcategoria else subcategorias

        def _normalize_situacao(value: str) -> str:
            if value is None:
                return ""
            raw = str(value).strip()
            if not raw:
                return ""
            low = raw.lower()
            if low in {"conforme", "conf."}:
                return "Conforme"
            if low in {"não conforme", "nao conforme", "n/conforme", "nconforme", "nc"}:
                return "Não conforme"
            if low in {"n/a", "na", "n.a", "não aplicável", "nao aplicavel"}:
                return "N/A"
            if low in {"sim", "true", "1"}:
                return "Sim"
            if low in {"não", "nao", "false", "0"}:
                return "Não"
            return raw

        situations_order = ["Conforme", "Não conforme", "N/A", "Sim", "Não", "Outros"]
        counts_by_subcat: dict[str, dict[str, int]] = {sc: {s: 0 for s in situations_order} for sc in subcats_to_show}

        for r in respostas_qs:
            p = pergunta_map.get(r.pergunta_id)
            if not p:
                continue
            sc = (p.subcategoria or "").strip()
            if not sc:
                continue
            if sc not in counts_by_subcat:
                continue
            val = _normalize_situacao(r.valor)
            if not val:
                continue
            if val not in situations_order:
                val = "Outros"
            counts_by_subcat[sc][val] += 1

        labels_sc = subcats_to_show
        datasets_sc = []
        for sit in situations_order:
            datasets_sc.append({
                "label": sit,
                "data": [counts_by_subcat.get(sc, {}).get(sit, 0) for sc in labels_sc],
            })

        subcat_chart = {"labels": labels_sc, "datasets": datasets_sc}

    def _normalize_sim_nao(value: str) -> str:
        if value is None:
            return ""
        raw = str(value).strip()
        if raw in {"True", "true", "Sim", "sim", "1", "SIM"}:
            return "Sim"
        if raw in {"False", "false", "Não", "não", "Nao", "nao", "0", "NAO", "NÃO"}:
            return "Não"
        return raw

    def _short(text: str, limit: int = 42) -> str:
        raw = (text or "").strip()
        if len(raw) <= limit:
            return raw
        return raw[: max(0, limit - 3)].rstrip() + "..."

    # Estatísticas (tabela) e dados dos gráficos por tipo/pergunta
    estatisticas_perguntas: list[dict] = []
    chart_cards: list[dict] = []
    chart_data: dict[str, dict] = {}

    tipo_cards_def = [
        {"tipo": "SIM_NAO", "key": "sim_nao", "label": "Sim/Não"},
        {"tipo": "LISTA", "key": "lista", "label": "Lista (opções)"},
        {"tipo": "NUMERO", "key": "numero", "label": "Número inteiro"},
        {"tipo": "DECIMAL", "key": "decimal", "label": "Número decimal"},
    ]

    perguntas_por_tipo: dict[str, list[PerguntaAuditoria]] = {d["tipo"]: [] for d in tipo_cards_def}
    for p in perguntas:
        if p.tipo_resposta in perguntas_por_tipo:
            perguntas_por_tipo[p.tipo_resposta].append(p)

    for d in tipo_cards_def:
        tipo = d["tipo"]
        key = d["key"]
        label = d["label"]
        perguntas_tipo = perguntas_por_tipo.get(tipo) or []
        if not perguntas_tipo:
            continue

        chart_cards.append({
            "key": key,
            "label": label,
            "tipo": tipo,
            "perguntas": ([{"id": "__all__", "texto": "Todas"}] + [{"id": p.id, "texto": p.pergunta} for p in perguntas_tipo]),
        })
        chart_data[key] = {"tipo": tipo, "perguntas": {}}

        # Agregado (todas as perguntas do tipo)
        all_respostas: list[RespostaAuditoria] = []
        for p in perguntas_tipo:
            all_respostas.extend(respostas_por_pergunta.get(p.id, []))

        if tipo == "SIM_NAO":
            # Geral por pergunta (barras empilhadas)
            labels_q = [_short(p.pergunta) for p in perguntas_tipo]
            sim_by_q: list[int] = []
            nao_by_q: list[int] = []
            for p in perguntas_tipo:
                respostas_p = respostas_por_pergunta.get(p.id, [])
                sim_count = 0
                nao_count = 0
                for r in respostas_p:
                    val = _normalize_sim_nao(r.valor)
                    if val == "Sim":
                        sim_count += 1
                    elif val == "Não":
                        nao_count += 1
                sim_by_q.append(sim_count)
                nao_by_q.append(nao_count)

            sim_total = 0
            nao_total = 0
            por_data: dict[str, dict[str, int]] = {}
            for r in all_respostas:
                val = _normalize_sim_nao(r.valor)
                if val not in {"Sim", "Não"}:
                    continue
                date_key = r.registro.data_auditoria.strftime("%Y-%m-%d") if r.registro.data_auditoria else ""
                if not date_key:
                    continue
                por_data.setdefault(date_key, {"Sim": 0, "Não": 0})
                por_data[date_key][val] += 1
                if val == "Sim":
                    sim_total += 1
                else:
                    nao_total += 1

            labels_date = sorted(por_data.keys())
            chart_data[key]["perguntas"]["__all__"] = {
                "current": {
                    "labels": labels_q,
                    "datasets": [
                        {"label": "Sim", "data": sim_by_q},
                        {"label": "Não", "data": nao_by_q},
                    ],
                },
                "by_date": {
                    "labels": labels_date,
                    "datasets": [
                        {"label": "Sim", "data": [por_data[d]["Sim"] for d in labels_date]},
                        {"label": "Não", "data": [por_data[d]["Não"] for d in labels_date]},
                    ],
                },
            }

        elif tipo == "LISTA":
            # Agregado (todas): uma barra por OPÇÃO (somando todas as perguntas do tipo)
            counts: dict[str, int] = {}
            por_data_opt: dict[str, dict[str, int]] = {}
            for r in all_respostas:
                opt = (str(r.valor).strip() if r.valor is not None else "")
                if not opt:
                    continue
                counts[opt] = counts.get(opt, 0) + 1
                date_key = r.registro.data_auditoria.strftime("%Y-%m-%d") if r.registro.data_auditoria else ""
                if not date_key:
                    continue
                por_data_opt.setdefault(date_key, {})
                por_data_opt[date_key][opt] = por_data_opt[date_key].get(opt, 0) + 1

            options_sorted = sorted(counts.items(), key=lambda x: (-x[1], x[0].lower()))
            opt_labels = [k for (k, _v) in options_sorted]
            opt_values = [v for (_k, v) in options_sorted]
            labels_date = sorted(por_data_opt.keys())

            datasets = []
            for opt in opt_labels:
                datasets.append({
                    "label": opt,
                    "data": [por_data_opt.get(d, {}).get(opt, 0) for d in labels_date],
                })

            chart_data[key]["perguntas"]["__all__"] = {
                "current": {
                    "labels": opt_labels,
                    "datasets": [
                        {"label": "Respostas", "data": opt_values},
                    ],
                },
                "by_date": {"labels": labels_date, "datasets": datasets},
            }

        elif tipo in {"NUMERO", "DECIMAL"}:
            # Geral por pergunta (apenas Valor por pergunta)
            labels_q = [_short(p.pergunta) for p in perguntas_tipo]
            avgs_q: list[float | None] = []
            for p in perguntas_tipo:
                vals: list[float] = []
                for r in respostas_por_pergunta.get(p.id, []):
                    raw = (r.valor or "").strip() if isinstance(r.valor, str) else ("" if r.valor is None else str(r.valor))
                    if not raw:
                        continue
                    try:
                        vals.append(float(raw.replace(",", ".")))
                    except (ValueError, TypeError):
                        continue
                if vals:
                    avgs_q.append(sum(vals) / len(vals))
                else:
                    avgs_q.append(None)

            # Por data (todas): uma série por pergunta (média por dia, se houver múltiplos registros)
            values_by_q_by_date: dict[int, dict[str, list[float]]] = {}
            all_dates: set[str] = set()
            for p in perguntas_tipo:
                for r in respostas_por_pergunta.get(p.id, []):
                    raw = (r.valor or "").strip() if isinstance(r.valor, str) else ("" if r.valor is None else str(r.valor))
                    if not raw:
                        continue
                    try:
                        num = float(raw.replace(",", "."))
                    except (ValueError, TypeError):
                        continue
                    date_key = r.registro.data_auditoria.strftime("%Y-%m-%d") if r.registro.data_auditoria else ""
                    if not date_key:
                        continue
                    all_dates.add(date_key)
                    values_by_q_by_date.setdefault(p.id, {}).setdefault(date_key, []).append(num)

            labels_date = sorted(all_dates)
            datasets_by_date: list[dict] = []
            for p in perguntas_tipo:
                per_date = values_by_q_by_date.get(p.id, {})
                data_points: list[float | None] = []
                for dte in labels_date:
                    arr = per_date.get(dte) or []
                    data_points.append((sum(arr) / len(arr)) if arr else None)
                datasets_by_date.append({"label": _short(p.pergunta), "data": data_points})

            chart_data[key]["perguntas"]["__all__"] = {
                "current": {
                    "labels": labels_q,
                    "datasets": [
                        {"label": "Valor", "data": avgs_q},
                    ],
                },
                "by_date": {"labels": labels_date, "datasets": datasets_by_date},
            }

        for pergunta in perguntas_tipo:
            respostas = respostas_por_pergunta.get(pergunta.id, [])
            total_respostas = len(respostas)
            estatistica = {
                "pergunta_id": pergunta.id,
                "pergunta": pergunta.pergunta,
                "descricao_detalhada": (pergunta.descricao_detalhada or "").strip(),
                "tipo": pergunta.get_tipo_resposta_display(),
                "total_respostas": total_respostas,
            }

            if pergunta.tipo_resposta == "SIM_NAO":
                sim_total = 0
                nao_total = 0
                por_data: dict[str, dict[str, int]] = {}
                for r in respostas:
                    val = _normalize_sim_nao(r.valor)
                    if val not in {"Sim", "Não"}:
                        continue
                    date_key = r.registro.data_auditoria.strftime("%Y-%m-%d") if r.registro.data_auditoria else ""
                    if not date_key:
                        continue
                    por_data.setdefault(date_key, {"Sim": 0, "Não": 0})
                    por_data[date_key][val] += 1
                    if val == "Sim":
                        sim_total += 1
                    else:
                        nao_total += 1

                estatistica["sim"] = sim_total
                estatistica["nao"] = nao_total

                labels_date = sorted(por_data.keys())
                chart_data[key]["perguntas"][str(pergunta.id)] = {
                    "current": {"labels": ["Sim", "Não"], "values": [sim_total, nao_total]},
                    "by_date": {
                        "labels": labels_date,
                        "datasets": [
                            {"label": "Sim", "data": [por_data[d]["Sim"] for d in labels_date]},
                            {"label": "Não", "data": [por_data[d]["Não"] for d in labels_date]},
                        ],
                    },
                }

            elif pergunta.tipo_resposta == "LISTA":
                counts: dict[str, int] = {}
                por_data_opt: dict[str, dict[str, int]] = {}
                for r in respostas:
                    opt = (str(r.valor).strip() if r.valor is not None else "")
                    if not opt:
                        continue
                    counts[opt] = counts.get(opt, 0) + 1
                    date_key = r.registro.data_auditoria.strftime("%Y-%m-%d") if r.registro.data_auditoria else ""
                    if not date_key:
                        continue
                    por_data_opt.setdefault(date_key, {})
                    por_data_opt[date_key][opt] = por_data_opt[date_key].get(opt, 0) + 1

                options_sorted = sorted(counts.items(), key=lambda x: (-x[1], x[0].lower()))
                opt_labels = [k for (k, _v) in options_sorted]
                opt_values = [v for (_k, v) in options_sorted]
                labels_date = sorted(por_data_opt.keys())

                datasets = []
                for opt in opt_labels:
                    datasets.append({
                        "label": opt,
                        "data": [por_data_opt.get(d, {}).get(opt, 0) for d in labels_date],
                    })

                chart_data[key]["perguntas"][str(pergunta.id)] = {
                    "current": {"labels": opt_labels, "values": opt_values},
                    "by_date": {"labels": labels_date, "datasets": datasets},
                }

            elif pergunta.tipo_resposta in {"NUMERO", "DECIMAL"}:
                values: list[float] = []
                por_data_vals: dict[str, list[float]] = {}
                for r in respostas:
                    raw = (r.valor or "").strip() if isinstance(r.valor, str) else ("" if r.valor is None else str(r.valor))
                    if not raw:
                        continue
                    try:
                        num = float(raw.replace(",", "."))
                    except (ValueError, TypeError):
                        continue
                    values.append(num)
                    date_key = r.registro.data_auditoria.strftime("%Y-%m-%d") if r.registro.data_auditoria else ""
                    if not date_key:
                        continue
                    por_data_vals.setdefault(date_key, []).append(num)

                if values:
                    avg_v = sum(values) / len(values)
                    estatistica["media"] = round(avg_v, 2)
                else:
                    avg_v = None

                labels_date = sorted(por_data_vals.keys())
                avg_by_date = []
                for dte in labels_date:
                    arr = por_data_vals.get(dte) or []
                    avg_by_date.append((sum(arr) / len(arr)) if arr else None)

                chart_data[key]["perguntas"][str(pergunta.id)] = {
                    "current": {
                        "labels": ["Valor"],
                        "values": [avg_v],
                    },
                    "by_date": {
                        "labels": labels_date,
                        "datasets": [
                            {"label": pergunta.pergunta, "data": avg_by_date},
                        ],
                    },
                }

            estatisticas_perguntas.append(estatistica)
    
    share_link = ""
    share_created_id_raw = (request.GET.get("share_created") or "").strip()
    share_created_id = int(share_created_id_raw) if share_created_id_raw.isdigit() else None
    share_created = None
    share_recipients = []
    share_history = []

    if not is_read_only:
        User = get_user_model()
        share_recipients = list(User.objects.filter(is_active=True).exclude(pk=request.user.id).order_by("first_name", "username"))

        share_history_qs = (
            RelatorioCompartilhadoAuditoria.objects.filter(modelo=modelo, remetente=request.user)
            .select_related("destinatario")
            .order_by("-criado_em", "-id")
        )
        share_history = list(share_history_qs[:30])

        if share_created_id:
            share_created = share_history_qs.filter(pk=share_created_id).first()
            if share_created:
                share_link = request.build_absolute_uri(
                    f"{reverse('auditoria:registros_por_modelo_compartilhado', args=[modelo.id])}?{urlencode({'share_token': share_created.token})}"
                )

    context = {
        "modelo": modelo,
        "page_obj": page_obj,
        "paginator": paginator,
        "querystring_base": querystring_base,
        "per_page": per_page,
        "per_page_options": sorted(allowed_per_page),
        "registros_count": paginator.count,
        "comentarios": comentarios,
        "is_auditoria_admin": _auditoria_is_admin(request.user),
        "querystring_with_page": querystring_with_page,
        "perguntas": perguntas,
        "comentarios_resposta_por_pergunta": comentarios_resposta_por_pergunta,
        "estatisticas_perguntas": estatisticas_perguntas,
        "chart_cards": chart_cards,
        "chart_data": chart_data,
        "subcategorias": subcategorias,
        "subcategoria": subcategoria,
        "subcat_chart": subcat_chart,
        "inicio": inicio_raw,
        "fim": fim_raw,
        "comentario_data_default": fim_raw or inicio_raw,
        "is_read_only": is_read_only,
        "share_token": share_token_raw,
        "share_link": share_link,
        "share_created": share_created,
        "share_recipients": share_recipients,
        "share_history": share_history,
        "targeted_share": targeted_share,
    }
    return render(request, "auditoria/registros_por_modelo.html", context)


@login_required
def comentario_edit(request, modelo_id, pk):
    modelo = get_object_or_404(
        _filter_modelos_para_usuario(request.user, ModeloAuditoria.objects.all()),
        pk=modelo_id,
    )
    comentario = get_object_or_404(ComentarioAuditoria, pk=pk, modelo=modelo)
    can_manage = _auditoria_is_admin(request.user) or (comentario.autor_id == request.user.id)

    preserved = {}
    for k in ("inicio", "fim", "subcategoria", "page", "per_page"):
        v = (request.GET.get(k) or "").strip()
        if v:
            preserved[k] = v
    back_url = reverse("auditoria:registros_por_modelo", args=[modelo.id])
    if preserved:
        back_url = f"{back_url}?{urlencode(preserved)}"

    if not can_manage:
        messages.error(request, "Você não tem permissão para editar este comentário.")
        return redirect(back_url)

    if request.method == "POST":
        form = ComentarioAuditoriaForm(request.POST, instance=comentario)
        if form.is_valid():
            form.save()
            messages.success(request, "Comentário atualizado com sucesso.")
            return redirect(back_url)
    else:
        form = ComentarioAuditoriaForm(instance=comentario)

    return render(
        request,
        "auditoria/comentario_form.html",
        {
            "modelo": modelo,
            "comentario": comentario,
            "form": form,
            "back_url": back_url,
        },
    )


@login_required
def comentario_delete(request, modelo_id, pk):
    modelo = get_object_or_404(
        _filter_modelos_para_usuario(request.user, ModeloAuditoria.objects.all()),
        pk=modelo_id,
    )
    comentario = get_object_or_404(ComentarioAuditoria, pk=pk, modelo=modelo)
    can_manage = _auditoria_is_admin(request.user) or (comentario.autor_id == request.user.id)

    preserved = {}
    for k in ("inicio", "fim", "subcategoria", "page", "per_page"):
        v = (request.GET.get(k) or "").strip()
        if v:
            preserved[k] = v
    back_url = reverse("auditoria:registros_por_modelo", args=[modelo.id])
    if preserved:
        back_url = f"{back_url}?{urlencode(preserved)}"

    if not can_manage:
        messages.error(request, "Você não tem permissão para remover este comentário.")
        return redirect(back_url)

    if request.method == "POST":
        comentario.delete()
        messages.success(request, "Comentário removido com sucesso.")
        return redirect(back_url)

    return render(
        request,
        "auditoria/comentario_confirm_delete.html",
        {
            "modelo": modelo,
            "comentario": comentario,
            "back_url": back_url,
        },
    )


@login_required
def exportar_respostas_excel(request, modelo_id):
    """Exporta em Excel (.xlsx) as respostas registradas de um modelo específico."""
    from openpyxl import Workbook

    modelo = get_object_or_404(
        _filter_modelos_para_usuario(request.user, ModeloAuditoria.objects.all()),
        pk=modelo_id,
    )

    perguntas = list(
        PerguntaAuditoria.objects.filter(modelo=modelo, ativo=True).order_by("ordem", "id")
    )
    registros = (
        RegistroAuditoria.objects.filter(modelo=modelo)
        .select_related("avaliador")
        .prefetch_related("respostas__pergunta")
        .order_by("-data_auditoria", "-id")
    )

    def _normalize_sim_nao(value: str) -> str:
        if value is None:
            return ""
        raw = str(value).strip()
        if raw in {"True", "true", "Sim", "sim", "1", "SIM"}:
            return "Sim"
        if raw in {"False", "false", "Não", "não", "Nao", "nao", "0", "NAO", "NÃO"}:
            return "Não"
        return raw

    dias_semana_choices = list(ModeloAuditoria.DIA_SEMANA_CHOICES)
    is_semanal = modelo.periodicidade == "SEMANAL"

    # Mapear respostas por registro/pergunta/(dia)
    respostas_por_registro: dict[int, dict[tuple[int, str | None], str]] = {}
    for registro in registros:
        respostas_por_registro[registro.id] = {}
        for resposta in getattr(registro, "respostas").all():
            key = (resposta.pergunta_id, resposta.dia_semana)
            respostas_por_registro[registro.id][key] = resposta.valor

    wb = Workbook()
    ws = wb.active
    ws.title = "Respostas"

    headers = [
        "ID",
        "Data Auditoria",
        "Período Início",
        "Período Fim",
        "Avaliador",
        "Observações",
    ]
    for p in perguntas:
        if is_semanal and getattr(p, "preenchimento_semanal", "UNICO") == "POR_DIA":
            for dia_key, dia_label in dias_semana_choices:
                headers.append(f"{p.pergunta} ({dia_label})")
        else:
            headers.append(p.pergunta)
    ws.append(headers)

    for registro in registros:
        avaliador = ""
        if registro.avaliador_id:
            avaliador = registro.avaliador.get_full_name() or registro.avaliador.username

        row = [
            registro.id,
            registro.data_auditoria.strftime("%d/%m/%Y") if registro.data_auditoria else "",
            registro.periodo_inicio.strftime("%d/%m/%Y") if registro.periodo_inicio else "",
            registro.periodo_fim.strftime("%d/%m/%Y") if registro.periodo_fim else "",
            avaliador,
            registro.observacoes or "",
        ]

        respostas_dict = respostas_por_registro.get(registro.id, {})
        for pergunta in perguntas:
            if is_semanal and getattr(pergunta, "preenchimento_semanal", "UNICO") == "POR_DIA":
                for dia_key, _dia_label in dias_semana_choices:
                    valor = respostas_dict.get((pergunta.id, dia_key), "")
                    if pergunta.tipo_resposta in ["SIM_NAO", "BOOLEANO"]:
                        row.append(_normalize_sim_nao(valor))
                    else:
                        row.append(valor or "")
            else:
                valor = respostas_dict.get((pergunta.id, None), "")
                if pergunta.tipo_resposta in ["SIM_NAO", "BOOLEANO"]:
                    row.append(_normalize_sim_nao(valor))
                else:
                    row.append(valor or "")

        ws.append(row)

    # Gerar arquivo em memória
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)

    safe_name = "".join(c for c in (modelo.nome or "modelo") if c.isalnum() or c in {" ", "-", "_"}).strip()
    if not safe_name:
        safe_name = f"modelo_{modelo.id}"
    filename = f"respostas_{safe_name}.xlsx"

    response = HttpResponse(
        stream.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
