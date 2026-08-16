from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
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

from .forms import (
    ComentarioAuditoriaForm, 
    ModeloAuditoriaForm, 
    PerguntaAuditoriaForm, 
    RegistroAuditoriaForm,
    NormaIsoForm,
    ItemNormaIsoForm,
    BancoPerguntaIsoForm,
)
from .models import (
    ComentarioAuditoria,
    ComentarioRespostaAuditoria,
    ModeloAuditoria,
    PerguntaAuditoria,
    RelatorioCompartilhadoAuditoria,
    RegistroAuditoria,
    RespostaAuditoria,
    get_pergunta_resposta_preset,
    list_pergunta_resposta_presets,
    Norma,
    ItemNorma,
    BancoPergunta,
    AuditoriaIso,
)


SPECIAL_VIEW_ALL_COLABORADORES_PERM = 'core.nav_pessoas_ver_todos_colaboradores'
REPORT_SHARE_SALT = "auditoria.registros_por_modelo.share"
REPORT_SHARE_MAX_AGE_SECONDS = 60 * 60 * 24 * 30  # 30 dias


def _build_registro_report_share_token(modelo_id: int, inicio: str = "", fim: str = "", topico: str = "") -> str:
    payload = {
        "m": int(modelo_id),
        "i": (inicio or "").strip(),
        "f": (fim or "").strip(),
        "s": (topico or "").strip(),
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
        "topico": str(payload.get("s") or "").strip(),
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
                "tipo_resposta": pergunta.tipo_resposta,
                "tipo_resposta_display": pergunta.get_tipo_resposta_display(),
                "opcoes_resposta_com_cores": list(getattr(pergunta, "opcoes_resposta_com_cores", []) or []),
                "topico": pergunta.topico.get_full_name() if pergunta.topico else "",
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
        nome_topico = item["topico"] or "Sem tópico"
        if nome_topico not in blocos_map:
            blocos_map[nome_topico] = {"nome": nome_topico, "caminho": nome_topico.split(" > "), "linhas": []}

        blocos_map[nome_topico]["linhas"].append(item)

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
        blocos_map[nome_topico]["linhas"].append(linha)

    for bloco in blocos_map.values():
        opcoes_meta: "OrderedDict[str, dict]" = OrderedDict()
        opcoes_counts: dict[str, int] = {}
        total_respostas_lista = 0

        for linha in bloco["linhas"]:
            if linha.get("tipo_resposta") != "LISTA":
                continue

            for opcao in linha.get("opcoes_resposta_com_cores", []):
                label = str((opcao or {}).get("label") or "").strip()
                if not label:
                    continue
                key = _normalize_text_token(label)
                if not key:
                    continue
                if key not in opcoes_meta:
                    color = str((opcao or {}).get("color") or "").strip() or _fallback_cor_resposta(label)
                    opcoes_meta[key] = {"label": label, "color": color}
                    opcoes_counts[key] = 0

            valores_resposta: list[str] = []
            respostas_por_dia = linha.get("respostas_por_dia") or {}
            tem_por_dia = any((respostas_por_dia.get(k) or "").strip() for k in dia_keys)
            if tem_por_dia:
                for dia_key in dia_keys:
                    valor = (respostas_por_dia.get(dia_key) or "").strip()
                    if valor:
                        valores_resposta.append(valor)
            else:
                valor_geral = (linha.get("resposta_geral") or "").strip()
                if valor_geral:
                    if "|" in valor_geral:
                        valores_resposta.extend([p.strip() for p in valor_geral.split("|") if p.strip()])
                    else:
                        valores_resposta.append(valor_geral)

            for valor in valores_resposta:
                key = _normalize_text_token(valor)
                if key in opcoes_counts:
                    opcoes_counts[key] += 1
                    total_respostas_lista += 1

        lista_resumo = []
        for key, meta in opcoes_meta.items():
            count = int(opcoes_counts.get(key, 0))
            percentual = round((count / total_respostas_lista) * 100, 1) if total_respostas_lista else 0
            lista_resumo.append(
                {
                    "label": meta.get("label") or "",
                    "color": meta.get("color") or "#6c757d",
                    "count": count,
                    "percentual": percentual,
                }
            )

        bloco["lista_resumo"] = lista_resumo
        bloco["lista_total_respostas"] = total_respostas_lista
        bloco["tem_lista_resumo"] = bool(lista_resumo)

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


def _build_topico_chart_from_resumo(blocos: list[dict]) -> dict:
    """Agrega respostas por sub-categoria para gráfico de situações."""
    situations_order = ["Conforme", "Não conforme", "N/A", "Sim", "Não", "Outros"]

    def _normalize_situacao(value: str) -> str:
        raw = str(value or "").strip()
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
        return "Outros"

    labels: list[str] = []
    counts_by_subcat: dict[str, dict[str, int]] = {}
    for bloco in blocos or []:
        nome = str(bloco.get("nome") or "Sem sub-categoria").strip() or "Sem sub-categoria"
        labels.append(nome)
        counts_by_subcat[nome] = {s: 0 for s in situations_order}

        for linha in bloco.get("linhas") or []:
            values: list[str] = []
            if linha.get("usa_colunas_dia"):
                values.extend(str(v or "").strip() for v in (linha.get("dia_values") or []))
            else:
                raw = str(linha.get("resposta_geral") or "").strip()
                if raw:
                    values.extend([v.strip() for v in raw.split("|")])

            for value in values:
                if not value:
                    continue
                situacao = _normalize_situacao(value)
                if not situacao:
                    continue
                if situacao not in situations_order:
                    situacao = "Outros"
                counts_by_subcat[nome][situacao] += 1

    datasets = [
        {
            "label": sit,
            "data": [counts_by_subcat.get(sc, {}).get(sit, 0) for sc in labels],
        }
        for sit in situations_order
    ]
    return {"labels": labels, "datasets": datasets}


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
def api_modelo_topicos(request):
    """API: devolve os tópicos cadastrados para o modelo selecionado."""
    modelo_id = (request.GET.get("modelo") or "").strip()
    if not (modelo_id and modelo_id.isdigit()):
        return JsonResponse({"topicos": []})
    try:
        modelo = ModeloAuditoria.objects.get(pk=int(modelo_id))
    except ModeloAuditoria.DoesNotExist:
        return JsonResponse({"topicos": []})
        
    from .models import TopicoAuditoria
    tps = TopicoAuditoria.objects.filter(modelo=modelo).order_by("parent__ordem", "ordem", "nome")
    
    result = []
    for t in tps:
        result.append({
            "id": t.id,
            "nome": t.get_full_name()
        })
    return JsonResponse({"topicos": result})


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
    mostrar_arquivados = request.GET.get("arquivados") == "1"

    modelos = ModeloAuditoria.objects.annotate(total_perguntas=Count("perguntas"))
    
    if mostrar_arquivados:
        modelos = modelos.filter(arquivado=True)
    else:
        modelos = modelos.filter(arquivado=False)
        
    if inicio:
        modelos = modelos.filter(criado_em__date__gte=inicio)
    if fim:
        modelos = modelos.filter(criado_em__date__lte=fim)

    context = {
        "modelos": modelos.order_by("nome"), 
        "inicio": inicio, 
        "fim": fim,
        "mostrar_arquivados": mostrar_arquivados
    }
    return render(request, "auditoria/modelos_list.html", context)

@login_required
@require_POST
def modelo_encerrar(request, pk):
    modelo = get_object_or_404(ModeloAuditoria, pk=pk)
    if not _auditoria_can_update_modelo(request.user, modelo):
        messages.error(request, "Você não tem permissão para encerrar este modelo.")
        return redirect("auditoria:modelos_list")
        
    modelo.ativo = False
    modelo.arquivado = False
    modelo.save()
    messages.success(request, f"O modelo '{modelo.nome}' foi encerrado com sucesso.")
    return redirect("auditoria:modelos_list")

@login_required
@require_POST
def modelo_arquivar(request, pk):
    modelo = get_object_or_404(ModeloAuditoria, pk=pk)
    if not _auditoria_can_update_modelo(request.user, modelo):
        messages.error(request, "Você não tem permissão para arquivar este modelo.")
        return redirect("auditoria:modelos_list")
        
    modelo.ativo = False
    modelo.arquivado = True
    modelo.save()
    messages.success(request, f"O modelo '{modelo.nome}' foi arquivado.")
    return redirect("auditoria:modelos_list")


@login_required
@require_POST
def justificar_nao_execucao(request, pk):
    from auditoria.models import JustificativaAuditoria
    from django.utils import timezone
    
    modelo = get_object_or_404(ModeloAuditoria, pk=pk)
    
    # Valida se o usuário tem permissão para preencher/justificar este modelo
    modelos_do_usuario = _filter_modelos_para_usuario(request.user, ModeloAuditoria.objects.filter(pk=pk))
    if not modelos_do_usuario.exists():
        messages.error(request, "Acesso negado. Você não tem permissão para justificar este modelo.")
        return redirect("auditoria:selecionar_modelo_preenchimento")
        
    justificativa_texto = (request.POST.get("justificativa") or "").strip()
    if not justificativa_texto:
        messages.error(request, "A justificativa é obrigatória.")
        return redirect("auditoria:selecionar_modelo_preenchimento")
        
    periodo_str = (request.POST.get("periodo") or "").strip()
    if not periodo_str or "|" not in periodo_str:
        messages.error(request, "Período inválido.")
        return redirect("auditoria:selecionar_modelo_preenchimento")
        
    try:
        p_inicio_str, p_fim_str = periodo_str.split("|")
        from datetime import datetime
        p_inicio = datetime.strptime(p_inicio_str, "%Y-%m-%d").date()
        p_fim = datetime.strptime(p_fim_str, "%Y-%m-%d").date()
    except ValueError:
        messages.error(request, "Formato de data inválido.")
        return redirect("auditoria:selecionar_modelo_preenchimento")
    
    JustificativaAuditoria.objects.create(
        modelo=modelo,
        periodo_inicio=p_inicio,
        periodo_fim=p_fim,
        justificativa=justificativa_texto,
        criado_por=request.user
    )
    
    messages.success(request, f"Justificativa para '{modelo.nome}' registrada com sucesso.")
    return redirect("auditoria:selecionar_modelo_preenchimento")


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
    topico_val = (request.GET.get("topico") or "").strip()
    perguntas = PerguntaAuditoria.objects.select_related("modelo")
    if modelo_id:
        perguntas = perguntas.filter(modelo_id=modelo_id)
    if topico_val:
        if topico_val.isdigit():
            perguntas = perguntas.filter(topico_id=int(topico_val))
        else:
            perguntas = perguntas.filter(topico__nome=topico_val)

    topicos = []
    if modelo_id and str(modelo_id).isdigit():
        try:
            from .models import TopicoAuditoria
            tps = TopicoAuditoria.objects.filter(modelo_id=int(modelo_id)).order_by("parent__ordem", "ordem", "nome")
            for t in tps:
                topicos.append({"id": str(t.id), "nome": t.get_full_name()})
        except Exception:
            topicos = []

    context = {
        "perguntas": perguntas.order_by("modelo__nome", "topico_id", "ordem", "id"),
        "modelos": ModeloAuditoria.objects.filter(ativo=True).order_by("nome"),
        "modelo_id": modelo_id,
        "selected_topico": topico_val,
        "topicos": topicos,
        "resposta_presets": list_pergunta_resposta_presets(),
    }
    return render(request, "auditoria/perguntas_list.html", context)


@login_required
def perguntas_bulk_apply_resposta(request):
    if not _auditoria_is_admin(request.user):
        messages.error(request, "Apenas usuários Staff/Superuser podem gerenciar perguntas.")
        return redirect("auditoria:perguntas_list")
    if request.method != "POST":
        return redirect("auditoria:perguntas_list")

    modelo_id = (request.POST.get("modelo") or "").strip()
    topico_val = (request.POST.get("filtro_topico") or "").strip()
    conjunto_resposta_padrao = (request.POST.get("conjunto_resposta_padrao") or "").strip()
    pergunta_ids = request.POST.getlist("pergunta_ids")

    if not (modelo_id and modelo_id.isdigit()):
        messages.error(request, "Selecione um modelo para aplicar o tipo de resposta em lote.")
        return redirect("auditoria:perguntas_list")

    if not pergunta_ids:
        messages.error(request, "Selecione pelo menos 1 pergunta.")
        params = {"modelo": modelo_id}
        if topico:
            params["topico"] = topico
        url = reverse("auditoria:perguntas_list")
        return redirect(f"{url}?{urlencode(params)}")

    preset = get_pergunta_resposta_preset(conjunto_resposta_padrao)
    if not preset:
        messages.error(request, "Selecione um conjunto de respostas válido.")
        params = {"modelo": modelo_id}
        if topico:
            params["topico"] = topico
        url = reverse("auditoria:perguntas_list")
        return redirect(f"{url}?{urlencode(params)}")

    ids_int: list[int] = []
    for raw in pergunta_ids:
        s = str(raw).strip()
        if not s.isdigit():
            continue
        ids_int.append(int(s))

    if not ids_int:
        messages.error(request, "Selecione pelo menos 1 pergunta válida.")
        params = {"modelo": modelo_id}
        if topico:
            params["topico"] = topico
        url = reverse("auditoria:perguntas_list")
        return redirect(f"{url}?{urlencode(params)}")

    updated = (
        PerguntaAuditoria.objects.filter(id__in=ids_int, modelo_id=int(modelo_id))
        .update(
            tipo_resposta=preset["tipo_resposta"],
            opcoes_resposta=preset["opcoes_resposta_texto"],
            opcoes_resposta_cores=preset["opcoes_resposta_cores"],
            exibir_grafico=preset["exibir_grafico"],
            aplicar_no_grid=preset["aplicar_no_grid"],
        )
    )

    messages.success(request, f"Conjunto de respostas '{preset['label']}' aplicado em {updated} pergunta(s).")
    params = {"modelo": modelo_id}
    if topico_val:
        params["topico"] = topico_val
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
            topico = (getattr(form.instance, "topico", "") or "").strip()
            if topico:
                params["topico"] = topico
            url = reverse("auditoria:perguntas_list")
            if params:
                url = f"{url}?{urlencode(params)}"
            return redirect(url)
    else:
        initial = {}
        modelo_id = request.GET.get("modelo")
        if modelo_id:
            initial["modelo"] = modelo_id
            topico = (request.GET.get("topico") or "").strip()
            if topico:
                initial["topico"] = topico
            if str(modelo_id).isdigit():
                initial["ordem"] = _get_next_pergunta_ordem(int(modelo_id))
        form = PerguntaAuditoriaForm(initial=initial)
    return render(
        request,
        "auditoria/pergunta_form.html",
        {
            "form": form,
            "modo": "novo",
            "resposta_presets": list_pergunta_resposta_presets(),
        },
    )


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
            exibir_grafico=pergunta.exibir_grafico,
            aplicar_no_grid=pergunta.aplicar_no_grid,
            ordem=_get_next_pergunta_ordem(pergunta.modelo_id),
            topico=pergunta.topico,
            obrigatoria=pergunta.obrigatoria,
            ativo=pergunta.ativo,
        )
        nova.save()

    messages.success(request, "Pergunta duplicada com sucesso.")
    params = {}
    if pergunta.modelo_id:
        params["modelo"] = pergunta.modelo_id
    topico = str(pergunta.topico.id) if pergunta.topico else ""
    if topico:
        params["topico"] = topico
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
                exibir_grafico=p.exibir_grafico,
                aplicar_no_grid=p.aplicar_no_grid,
                ordem=p.ordem,
                topico=p.topico,
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
            topico = (getattr(form.instance, "topico", "") or "").strip()
            if topico:
                params["topico"] = topico
            url = reverse("auditoria:perguntas_list")
            if params:
                url = f"{url}?{urlencode(params)}"
            return redirect(url)
    else:
        form = PerguntaAuditoriaForm(instance=pergunta)
    return render(
        request,
        "auditoria/pergunta_form.html",
        {
            "form": form,
            "modo": "edicao",
            "pergunta": pergunta,
            "resposta_presets": list_pergunta_resposta_presets(),
        },
    )


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

    from auditoria.utils_periodos import calcular_periodos_pendentes

    modelos_com_pendencias = []
    
    # We will fetch and annotate all models first
    modelos = modelos.annotate(
        total_perguntas=Count("perguntas", filter=models.Q(perguntas__ativo=True))
    ).order_by("nome")

    for modelo in modelos:
        pendencias = calcular_periodos_pendentes(modelo, limit=24)
        modelo.is_pendente = len(pendencias) > 0
        modelo.periodos_pendentes = pendencias
        if not pendencias and pendentes == "mes":
            continue
        modelos_com_pendencias.append(modelo)
        
    modelos = modelos_com_pendencias

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
    perguntas_qs = PerguntaAuditoria.objects.filter(modelo=modelo, ativo=True).select_related('topico').order_by("ordem", "id")
    # Sort recursively by topic path in python to group correctly
    perguntas = sorted(list(perguntas_qs), key=lambda p: (p.topico.get_full_name() if p.topico else "", p.ordem, p.id))
    
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
            
            action = request.POST.get("action", "save_draft")
            is_draft = action == "save_draft"
            if not is_draft:
                registro.status = "CONCLUIDO"
            else:
                registro.status = "RASCUNHO"

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
                        if not valor and pergunta.obrigatoria and not is_draft:
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
                    if not valor and pergunta.obrigatoria and not is_draft:
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
            
            if erros and not is_draft:
                registro.delete()
                for erro in erros:
                    messages.error(request, erro)
            else:
                registro.atualizar_progresso()
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
    
    if registro.status == "CONCLUIDO":
        from django.contrib import messages
        messages.warning(request, "Este ciclo já foi concluído e encontra-se bloqueado para edição.")
        return redirect("auditoria:registro_detail", pk=registro.pk)
    perguntas_qs = PerguntaAuditoria.objects.filter(modelo=registro.modelo, ativo=True).select_related('topico').order_by("ordem", "id")
    perguntas = sorted(list(perguntas_qs), key=lambda p: (p.topico.get_full_name() if p.topico else "", p.ordem, p.id))
    
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
            action = request.POST.get("action", "save_draft")
            is_draft = action == "save_draft"
            if not is_draft:
                registro.status = "CONCLUIDO"
            else:
                registro.status = "RASCUNHO"

            grid_itens = []
            if grid_enabled:
                grid_itens = _get_effective_grid_itens_for_edit(registro, form.cleaned_data.get("grid_itens") or "")
                registro.grid_itens = "\n".join(grid_itens)

            registro.save()

            erros = []
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
                                if not valor and pergunta.obrigatoria and not is_draft:
                                    erros.append(f"A pergunta '{pergunta.pergunta}' é obrigatória para {item} no dia {_dia_label}.")
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
                            if not valor and pergunta.obrigatoria and not is_draft:
                                erros.append(f"A pergunta '{pergunta.pergunta}' é obrigatória para o dia {_dia_label}.")
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
                            if not valor and pergunta.obrigatoria and not is_draft:
                                erros.append(f"A pergunta '{pergunta.pergunta}' é obrigatória para {item}.")
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
                        if not valor and pergunta.obrigatoria and not is_draft:
                            erros.append(f"A pergunta '{pergunta.pergunta}' é obrigatória.")
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
            
            if erros and not is_draft:
                for erro in erros:
                    messages.error(request, erro)
                # se teve erro no submit, volta para RASCUNHO para não travar
                registro.status = "RASCUNHO"
                registro.save(update_fields=['status'])
            else:
                registro.atualizar_progresso()
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    from django.http import JsonResponse
                    return JsonResponse({"status": "ok", "progresso": registro.progresso})
                
                msg = "Rascunho do Ciclo salvo com sucesso!" if is_draft else "Ciclo de auditoria concluído com sucesso!"
                messages.success(request, msg)
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


    # Gráfico único de distribuição de situações por topico (dashboard style)
    subcat_chart = _build_topico_chart_from_resumo(resumo["blocos"])

    context = {
        "registro": registro,
        "blocos_respostas": resumo["blocos"],
        "subcat_chart": subcat_chart,
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
    """Exporta o detalhe do registro em PDF (A4 paisagem) com gráfico e blocos por sub-categoria."""
    from xml.sax.saxutils import escape
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.charts.legends import Legend
    from reportlab.graphics.shapes import Drawing
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    registro = get_object_or_404(
        _filter_registros_para_usuario(
            request.user,
            RegistroAuditoria.objects.select_related("modelo", "avaliador"),
        ),
        pk=pk,
    )

    resumo = _build_resumo_respostas_registro(registro)
    subcat_chart = _build_topico_chart_from_resumo(resumo["blocos"])
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

    # Pagina 1: Informacoes gerais
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
    info_table = Table(info_rows, colWidths=[4.2 * cm, doc.width - 4.2 * cm], repeatRows=0)
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

    # Pagina 2: Grafico por sub-categoria (pagina inteira)
    elements.append(PageBreak())
    elements.append(Paragraph("Distribuição de Situações por Tópico", style_title))

    labels = subcat_chart.get("labels") or []
    datasets = subcat_chart.get("datasets") or []
    has_chart_data = bool(labels and any((sum((ds.get("data") or [])) > 0) for ds in datasets))

    if has_chart_data:
        drawing = Drawing(doc.width, doc.height - 2.0 * cm)
        chart = VerticalBarChart()
        chart.x = 1.1 * cm
        chart.y = 2.2 * cm
        chart.width = doc.width - 2.6 * cm
        chart.height = doc.height - 5.8 * cm
        chart.data = [list(ds.get("data") or []) for ds in datasets]
        chart.categoryAxis.categoryNames = labels
        chart.categoryAxis.labels.angle = 25
        chart.categoryAxis.labels.boxAnchor = "ne"
        chart.categoryAxis.labels.fontSize = 8
        chart.valueAxis.valueMin = 0
        chart.valueAxis.forceZero = 1
        chart.valueAxis.labels.fontSize = 8
        chart.barSpacing = 1
        chart.groupSpacing = 8
        chart.bars[0].strokeWidth = 0
        chart.bars.strokeWidth = 0

        series_color_map = {
            "Conforme": "#198754",
            "Não conforme": "#dc3545",
            "N/A": "#6c757d",
            "Sim": "#20c997",
            "Não": "#fd7e14",
            "Outros": "#0d6efd",
        }
        for idx, ds in enumerate(datasets):
            label = str(ds.get("label") or "")
            chart.bars[idx].fillColor = HexColor(series_color_map.get(label, "#0d6efd"))

        chart.categoryAxis.style = "stacked"
        chart.bars[0].strokeColor = None
        drawing.add(chart)

        legend = Legend()
        legend.x = 1.1 * cm
        legend.y = doc.height - 3.0 * cm
        legend.fontSize = 8
        legend.columnMaximum = 6
        legend.colorNamePairs = [
            (HexColor(series_color_map.get(str(ds.get("label") or ""), "#0d6efd")), str(ds.get("label") or ""))
            for ds in datasets
        ]
        drawing.add(legend)
        elements.append(drawing)
    else:
        elements.append(Paragraph("Sem dados suficientes para gerar o gráfico desta auditoria.", style_cell))

    # Paginas seguintes: sub-categorias com farol (várias por página, sem quebrar bloco)
    elements.append(PageBreak())
    dias_semana_abrev = {
        "SEGUNDA": "Seg",
        "TERCA": "Ter",
        "QUARTA": "Qua",
        "QUINTA": "Qui",
        "SEXTA": "Sex",
        "SABADO": "Sáb",
        "DOMINGO": "Dom",
    }

    elements.append(Paragraph("Respostas por Tópico", style_title))
    remaining_height = doc.height - 1.0 * cm

    for idx_bloco, bloco in enumerate(resumo["blocos"]):
        heading = Paragraph(f"Tópico: {escape(bloco['nome'])}", style_section)

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

        bloco_table = Table(table_data, colWidths=col_widths, repeatRows=1, splitByRow=0)
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
        h_heading = heading.wrap(doc.width, doc.height)[1]
        h_table = bloco_table.wrap(doc.width, doc.height)[1]
        h_total = h_heading + h_table + 0.5 * cm

        if h_total > remaining_height and remaining_height < doc.height:
            elements.append(PageBreak())
            remaining_height = doc.height

        elements.append(heading)
        elements.append(bloco_table)
        elements.append(Spacer(1, 0.3 * cm))
        remaining_height -= h_total

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
        ModeloAuditoria.objects.filter(arquivado=False),
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
                "topico": (targeted_share.topico or "").strip(),
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
                subcat_tmp = (request.GET.get("topico") or "").strip()
                if subcat_tmp:
                    # Allow filtering if it's an integer ID
                    if subcat_tmp.isdigit():
                        base_params["topico_id"] = int(subcat_tmp)
                    else:
                        base_params["topico__nome"] = subcat_tmp

                share_obj = RelatorioCompartilhadoAuditoria.objects.create(
                    modelo=modelo,
                    remetente=request.user,
                    destinatario=destinatario,
                    inicio=inicio_tmp,
                    fim=fim_tmp,
                    topico=subcat_tmp,
                    expira_em=timezone.now() + timedelta(days=30),
                )
                redirect_url = reverse("auditoria:registros_por_modelo", args=[modelo.id])
                preserved = {}
                for k in ("inicio", "fim", "topico", "page", "per_page"):
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
        for k in ("inicio", "fim", "topico", "page", "per_page"):
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
        for k in ("inicio", "fim", "topico", "page", "per_page"):
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
        for k in ("inicio", "fim", "topico", "page", "per_page"):
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

    from .models import TopicoAuditoria
    tps = TopicoAuditoria.objects.filter(modelo=modelo).order_by("parent__ordem", "ordem", "nome")
    topicos = [{"id": str(t.id), "nome": t.get_full_name()} for t in tps]

    topico = ""
    if is_read_only:
        topico_raw = (share_data.get("topico") or "").strip()
    else:
        topico_raw = (request.GET.get("topico") or "").strip()
    
    topico = ""
    if topico_raw:
        if any(sc["id"] == topico_raw for sc in topicos) or any(sc["nome"] == topico_raw for sc in topicos):
            topico = topico_raw
    else:
        subcat_get = (request.GET.get("topico") or "").strip()
        if any(sc["id"] == subcat_get for sc in topicos) or any(sc["nome"] == subcat_get for sc in topicos):
            topico = subcat_get

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
    if topico:
        base_params["topico"] = topico
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
    if topico:
        if topico.isdigit():
            perguntas_qs = perguntas_qs.filter(topico_id=int(topico))
        else:
            perguntas_qs = perguntas_qs.filter(topico__nome=topico)
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

    # Gráfico agregado: situações por topico
    subcat_chart: dict | None = None
    if topicos:
        subcats_to_show = [sc["nome"] for sc in topicos if sc["id"] == topico or sc["nome"] == topico] if topico else [sc["nome"] for sc in topicos]

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
            sc = p.topico.get_full_name() if p.topico else ""
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
                
    # Buscar justificativas
    from auditoria.models import JustificativaAuditoria
    justificativas = JustificativaAuditoria.objects.filter(modelo=modelo).order_by("-criado_em")

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
        "topicos": topicos,
        "selected_topico": topico,
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
        "justificativas": justificativas,
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
    for k in ("inicio", "fim", "topico", "page", "per_page"):
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
    for k in ("inicio", "fim", "topico", "page", "per_page"):
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


@login_required
def perguntas_bulk_set_topico(request):
    modelo_id = request.POST.get("modelo")
    topico_id = (request.POST.get("topico") or "").strip()
    pergunta_ids = request.POST.getlist("pergunta_ids")

    if not (modelo_id and pergunta_ids):
        messages.error(request, "Selecione o modelo e pelo menos uma pergunta.")
        return redirect("auditoria:perguntas_list")

    # Verifica permissão do modelo
    modelo = get_object_or_404(ModeloAuditoria, pk=modelo_id)
    if not _auditoria_can_update_modelo(request.user, modelo):
        messages.error(request, "Você não tem permissão para alterar as perguntas deste modelo.")
        return redirect(f"{reverse('auditoria:perguntas_list')}?modelo={modelo_id}")

    topico_obj = None
    if topico_id and topico_id.isdigit():
        from .models import TopicoAuditoria
        topico_obj = TopicoAuditoria.objects.filter(id=int(topico_id), modelo=modelo).first()
        if not topico_obj:
            messages.error(request, "Tópico inválido para este modelo.")
            return redirect(f"{reverse('auditoria:perguntas_list')}?modelo={modelo_id}")

    count = 0
    with transaction.atomic():
        perguntas = PerguntaAuditoria.objects.filter(id__in=pergunta_ids, modelo_id=modelo_id)
        for pergunta in perguntas:
            pergunta.topico = topico_obj
            pergunta.save(update_fields=["topico"])
            count += 1
    messages.success(request, f"{count} perguntas atualizadas.")
    return redirect(f"{reverse('auditoria:perguntas_list')}?modelo={modelo_id}")


@login_required
def modelo_categorias(request, modelo_id):
    modelo = get_object_or_404(ModeloAuditoria, pk=modelo_id)
    if not _auditoria_can_update_modelo(request.user, modelo):
        messages.error(request, "Você não tem permissão para editar as categorias deste modelo.")
        return redirect("auditoria:modelos_list")

    if request.method == "POST":
        action = request.POST.get("action")
        is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest" or request.headers.get("Accept", "").startswith("application/json")
        
        if action == "add_topico":
            nome = request.POST.get("nome")
            parent_id = request.POST.get("parent_id")
            if nome:
                from .models import TopicoAuditoria
                parent = None
                if parent_id and parent_id.isdigit():
                    parent = get_object_or_404(TopicoAuditoria, pk=parent_id, modelo=modelo)
                topico = TopicoAuditoria.objects.create(modelo=modelo, parent=parent, nome=nome)
                
                if is_ajax:
                    from django.template.loader import render_to_string
                    from django.http import JsonResponse
                    html = render_to_string("auditoria/_topico_node.html", {"topico": topico}, request=request)
                    return JsonResponse({"status": "success", "html": html, "parent_id": parent_id or ""})
                    
                messages.success(request, "Tópico adicionado.")
        elif action == "edit_topico":
            topico_id = request.POST.get("topico_id")
            nome = request.POST.get("nome")
            if topico_id and nome:
                from .models import TopicoAuditoria
                topico = get_object_or_404(TopicoAuditoria, pk=topico_id, modelo=modelo)
                topico.nome = nome
                topico.save()
                
                if is_ajax:
                    from django.http import JsonResponse
                    return JsonResponse({"status": "success", "nome": nome, "topico_id": topico_id})
                    
                messages.success(request, "Tópico atualizado.")
        
        if is_ajax:
            from django.http import JsonResponse
            return JsonResponse({"status": "error", "message": "Ação inválida ou dados incompletos"}, status=400)
            
        return redirect("auditoria:modelo_categorias", modelo_id=modelo.id)

    from .models import TopicoAuditoria
    topicos_raiz = TopicoAuditoria.objects.filter(modelo=modelo, parent__isnull=True).prefetch_related('subtopicos')
    
    # Busca recursiva para montar a arvore no template (usaremos include do template)
    # A view so precisa mandar os topicos raiz e os topicos irao renderizar seus filhos.
    
    context = {
        "modelo": modelo,
        "topicos_raiz": topicos_raiz,
    }
    return render(request, "auditoria/modelo_categorias.html", context)


@login_required
@require_POST
def topico_delete(request, pk):
    from .models import TopicoAuditoria
    from django.http import JsonResponse
    
    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest" or request.headers.get("Accept", "").startswith("application/json")
    
    topico = get_object_or_404(TopicoAuditoria, pk=pk)
    if not _auditoria_can_update_modelo(request.user, topico.modelo):
        if is_ajax:
            return JsonResponse({"status": "error", "message": "Acesso negado."}, status=403)
        return HttpResponseForbidden()
    
    modelo_id = topico.modelo_id
    try:
        topico.delete()
        if is_ajax:
            return JsonResponse({"status": "success", "topico_id": pk})
        messages.success(request, "Tópico removido.")
    except ProtectedError:
        msg = "Não é possível remover o tópico pois ele está vinculado a perguntas ou sub-tópicos vinculados a perguntas."
        if is_ajax:
            return JsonResponse({"status": "error", "message": msg}, status=400)
        messages.error(request, msg)
        
    if is_ajax:
        return JsonResponse({"status": "error", "message": "Erro desconhecido."}, status=400)
    return redirect("auditoria:modelo_categorias", modelo_id=modelo_id)

@login_required
@require_POST
def reorder_topicos(request):
    import json
    from django.http import JsonResponse
    from .models import TopicoAuditoria
    
    try:
        data = json.loads(request.body)
        topicos_ids = data.get("topicos", [])
        
        if not topicos_ids:
            return JsonResponse({"status": "success"})
            
        primeiro_topico = TopicoAuditoria.objects.filter(id=topicos_ids[0]).first()
        if not primeiro_topico or not _auditoria_can_update_modelo(request.user, primeiro_topico.modelo):
            return JsonResponse({"status": "error", "message": "Sem permissão"}, status=403)
            
        for index, topico_id in enumerate(topicos_ids, start=1):
            TopicoAuditoria.objects.filter(id=topico_id).update(ordem=index)
            
        return JsonResponse({"status": "success"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)
# ==========================================
# VIEWS PARA AUDITORIA MODO ENTREVISTA (ISO)
# ==========================================

from .models import AuditoriaIso, RespostaEntrevistaIso, BancoPergunta

@login_required
def iso_auditoria_list(request):
    auditorias = AuditoriaIso.objects.all().order_by("-data_inicio")
    return render(request, "auditoria/iso_auditoria_list.html", {"auditorias": auditorias})

@login_required
def iso_entrevista_view(request, auditoria_id):
    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    
    agenda_id = request.GET.get('agenda_id')
    if agenda_id:
        from .models import AgendaAuditoriaIso
        agenda = get_object_or_404(AgendaAuditoriaIso, pk=agenda_id, auditoria=auditoria)
        perguntas = agenda.perguntas.filter(ativa=True).distinct().prefetch_related('itens_norma')
    else:
        # Obter perguntas vinculadas ao escopo da auditoria
        perguntas = BancoPergunta.objects.filter(ativa=True, itens_norma__in=auditoria.escopo_itens.all()).distinct().prefetch_related('itens_norma')
        if not perguntas.exists():
            perguntas = BancoPergunta.objects.filter(ativa=True).prefetch_related('itens_norma')
            
    # Ordenar perguntas rigorosamente pela ordem e referência do item da norma
    def get_pergunta_sort_key(p):
        items = list(p.itens_norma.all())
        if items:
            min_ordem = min((it.ordem or 0) for it in items)
            min_ref = min((it.referencia or '') for it in items)
            return (min_ordem, min_ref, p.id)
        return (999999, '', p.id)

    perguntas_lista = sorted(list(perguntas), key=get_pergunta_sort_key)
    
    # Garante a existência e atualização da pergunta padrão de Identificação dos Auditados (Nome e Função)
    pergunta_auditados, _ = BancoPergunta.objects.get_or_create(
        texto_pergunta="Quais são os nomes e funções das pessoas auditadas / entrevistadas neste bloco?",
        defaults={
            "dica_auditor": "Registre o nome completo e a função / cargo de cada participante entrevistado nesta etapa da auditoria.",
            "ativa": True
        }
    )
    if "funções" not in pergunta_auditados.texto_pergunta.lower():
        pergunta_auditados.texto_pergunta = "Quais são os nomes e funções das pessoas auditadas / entrevistadas neste bloco?"
        pergunta_auditados.dica_auditor = "Registre o nome completo e a função / cargo de cada participante entrevistado nesta etapa da auditoria."
        pergunta_auditados.save()

    # Prepend a pergunta de auditados na PRIMEIRA POSIÇÃO da entrevista
    perguntas_lista = [p for p in perguntas_lista if p.id != pergunta_auditados.id]
    perguntas_lista.insert(0, pergunta_auditados)
    
    # Obter respostas já existentes
    respostas = RespostaEntrevistaIso.objects.filter(auditoria=auditoria).prefetch_related('solicitacoes')
    respostas_dict = {}
    for r in respostas:
        sols = [
            {
                "id": s.id,
                "solicitacao": s.solicitacao,
                "evidencia": s.evidencia,
                "conclusao": s.conclusao
            }
            for s in r.solicitacoes.all()
        ]
        respostas_dict[r.pergunta_id] = {
            "classificacao": r.classificacao,
            "texto_resposta": r.texto_resposta,
            "solicitacoes": sols
        }
        
    agendas_outras_todas = list(auditoria.agendas.all().prefetch_related('itens_norma', 'perguntas'))

    perguntas_data = []
    for p in perguntas_lista:
        r = respostas_dict.get(p.id, {})
        
        itens_p = list(p.itens_norma.all())
        outros_blocos_info = []
        if itens_p:
            for ag in agendas_outras_todas:
                if agenda_id and str(ag.id) == str(agenda_id):
                    continue
                # Se o bloco tem algum dos itens da norma desta pergunta
                itens_em_comum = [item for item in itens_p if item in ag.itens_norma.all() or any(item in p_ag.itens_norma.all() for p_ag in ag.perguntas.all())]
                if itens_em_comum:
                    outros_blocos_info.append({
                        'agenda_id': ag.id,
                        'titulo': ag.titulo,
                        'itens_comum': [it.referencia for it in itens_em_comum],
                        'total_perguntas': ag.perguntas.count()
                    })

        itens_str = ", ".join([item.referencia for item in p.itens_norma.all()])
        if p.id == pergunta_auditados.id and not itens_str:
            itens_str = "Identificação / Auditados"

        perguntas_data.append({
            "id": p.id,
            "texto_pergunta": p.texto_pergunta,
            "dica_auditor": p.dica_auditor,
            "itens": itens_str,
            "itens_objects": [{"id": item.id, "ref": item.referencia, "titulo": item.titulo} for item in p.itens_norma.all()],
            "outros_blocos": outros_blocos_info,
            "classificacao": r.get("classificacao", "P"),
            "texto_resposta": r.get("texto_resposta", ""),
            "solicitacoes": r.get("solicitacoes", [])
        })
        
    context = {
        "auditoria": auditoria,
        "perguntas_json": json.dumps(perguntas_data)
    }
    return render(request, "auditoria/iso_entrevista.html", context)

@login_required
@require_POST
def api_iso_autosave_resposta(request):
    try:
        data = json.loads(request.body)
        auditoria_id = data.get("auditoria_id")
        pergunta_id = data.get("pergunta_id")
        texto_resposta = data.get("texto_resposta", "")
        classificacao = data.get("classificacao", "P")
        
        auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
        pergunta = get_object_or_404(BancoPergunta, pk=pergunta_id)
        
        resposta, created = RespostaEntrevistaIso.objects.update_or_create(
            auditoria=auditoria,
            pergunta=pergunta,
            defaults={
                "texto_resposta": texto_resposta,
                "classificacao": classificacao,
                "respondida_por": request.user
            }
        )
        return JsonResponse({"status": "success", "resposta_id": resposta.id})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)

@login_required
@require_POST
def api_iso_solicitacao_create(request):
    from .models import SolicitacaoEvidenciaIso, RespostaEntrevistaIso, AuditoriaIso, BancoPergunta
    try:
        data = json.loads(request.body)
        auditoria_id = data.get("auditoria_id")
        pergunta_id = data.get("pergunta_id")
        solicitacao_texto = data.get("solicitacao", "Nova Solicitação de Evidência").strip()
        evidencia_texto = data.get("evidencia", "").strip()
        conclusao = data.get("conclusao", "P")

        auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
        pergunta = get_object_or_404(BancoPergunta, pk=pergunta_id)

        resposta, _ = RespostaEntrevistaIso.objects.get_or_create(
            auditoria=auditoria,
            pergunta=pergunta,
            defaults={"respondida_por": request.user}
        )

        nova_sol = SolicitacaoEvidenciaIso.objects.create(
            resposta=resposta,
            solicitacao=solicitacao_texto,
            evidencia=evidencia_texto,
            conclusao=conclusao
        )

        return JsonResponse({
            "success": True,
            "solicitacao": {
                "id": nova_sol.id,
                "solicitacao": nova_sol.solicitacao,
                "evidencia": nova_sol.evidencia,
                "conclusao": nova_sol.conclusao
            }
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)

@login_required
@require_POST
def api_iso_solicitacao_update(request, pk):
    from .models import SolicitacaoEvidenciaIso
    try:
        sol = get_object_or_404(SolicitacaoEvidenciaIso, pk=pk)
        data = json.loads(request.body)

        if "solicitacao" in data:
            sol.solicitacao = data["solicitacao"]
        if "evidencia" in data:
            sol.evidencia = data["evidencia"]
        if "conclusao" in data:
            sol.conclusao = data["conclusao"]

        sol.save()
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)

@login_required
@require_POST
def api_iso_solicitacao_delete(request, pk):
    from .models import SolicitacaoEvidenciaIso
    try:
        sol = get_object_or_404(SolicitacaoEvidenciaIso, pk=pk)
        sol.delete()
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
@require_POST
def api_iso_marcar_nao_aplicavel(request):
    """
    Define um item da norma (e opcionalmente todos os seus sub-itens descendentes)
    como Não Aplicável (N/A) / Exclusão de Escopo nesta auditoria.
    """
    from .models import ItemNorma, RespostaEntrevistaIso, AuditoriaIso
    try:
        data = json.loads(request.body)
        auditoria_id = data.get("auditoria_id")
        item_id = data.get("item_id")
        referencia = data.get("referencia")
        justificativa = data.get("justificativa", "Item definido como Não Aplicável (N/A) / Exclusão de Escopo pelo auditor.").strip()
        status_target = data.get("status_target", "NA")
        incluir_sub_itens = data.get("incluir_sub_itens", True)

        auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
        
        if item_id:
            target_item = get_object_or_404(ItemNorma, pk=item_id)
            ref_root = target_item.referencia
        elif referencia:
            target_item = get_object_or_404(ItemNorma, norma=auditoria.norma, referencia=referencia)
            ref_root = referencia
        else:
            return JsonResponse({"success": False, "error": "Item não informado."}, status=400)

        if incluir_sub_itens:
            # Pega o próprio item e todos que começam com 'referencia.'
            itens_afetados = list(ItemNorma.objects.filter(norma=auditoria.norma, referencia=ref_root)) + \
                             list(ItemNorma.objects.filter(norma=auditoria.norma, referencia__startswith=ref_root + "."))
        else:
            itens_afetados = [target_item]

        agendas = auditoria.agendas.all().prefetch_related('perguntas', 'perguntas__itens_norma')
        perguntas_afetadas = set()
        
        for item_a in itens_afetados:
            for agenda in agendas:
                for p in agenda.perguntas.all():
                    if item_a in p.itens_norma.all() or (not p.itens_norma.exists() and item_a in agenda.itens_norma.all()):
                        perguntas_afetadas.add(p)

        count_updated = 0
        texto_na = justificativa if status_target == "NA" else ""
        
        if status_target == "NA":
            auditoria.itens_nao_aplicaveis.add(*itens_afetados)
        else:
            auditoria.itens_nao_aplicaveis.remove(*itens_afetados)

        for p in perguntas_afetadas:
            RespostaEntrevistaIso.objects.update_or_create(
                auditoria=auditoria,
                pergunta=p,
                defaults={
                    "classificacao": status_target,
                    "texto_resposta": texto_na,
                    "respondida_por": request.user
                }
            )
            count_updated += 1

        return JsonResponse({
            "success": True,
            "referencia": ref_root,
            "status_target": status_target,
            "itens_afetados_count": len(itens_afetados),
            "perguntas_atualizadas_count": count_updated
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)

def natural_sort_key(referencia):
    """
    Função de chave para ordenação numérica natural de referências normativas (ex: 7.3.2 vem antes de 7.3.10).
    """
    import re
    if not referencia:
        return []
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(referencia))]


@login_required
def iso_matriz_view(request, auditoria_id):
    from .models import AuditoriaIso, ItemNorma, RespostaEntrevistaIso
    
    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    agendas = list(auditoria.agendas.all().prefetch_related('perguntas', 'itens_norma', 'perguntas__itens_norma'))
    
    # Todos os itens de norma no escopo (ou da norma completa se o escopo estiver vazio)
    itens_escopo = auditoria.escopo_itens.all()
    if not itens_escopo.exists():
        itens_escopo = ItemNorma.objects.filter(norma=auditoria.norma)
        
    itens_escopo_list = list(itens_escopo)
    
    # Mapeamento de itens pai (que possuem sub-itens)
    parent_ids = set()
    for item in itens_escopo_list:
        prefix = item.referencia + '.'
        if any(other.referencia.startswith(prefix) for other in itens_escopo_list):
            parent_ids.add(item.id)
            
    # Respostas já preenchidas
    respostas = RespostaEntrevistaIso.objects.filter(auditoria=auditoria).prefetch_related('solicitacoes')
    respostas_map = {r.pergunta_id: r for r in respostas}
    
    # Mapeia itens explicitamente marcados como N/A na auditoria
    na_item_ids = set(auditoria.itens_nao_aplicaveis.values_list('id', flat=True))

    hierarchy = {"NC": 5, "P": 4, "OM": 3, "C": 2, "NA": 1}
    reverse_hierarchy = {v: k for k, v in hierarchy.items()}
    
    # Mapeamento rápido de agendas por item da norma
    agenda_item_ids_map = {agenda.id: set(agenda.itens_norma.values_list('id', flat=True)) for agenda in agendas}
    
    matriz_data = []
    
    for item in sorted(itens_escopo_list, key=lambda x: (x.ordem or 0, natural_sort_key(x.referencia))):
        is_parent = item.id in parent_ids
        
        # Encontra todos os blocos (agendas) e perguntas associadas a este item
        blocos_associados = []
        todas_perguntas_item_set = set()
        
        for agenda in agendas:
            ag_item_ids = agenda_item_ids_map[agenda.id]
            
            # Perguntas vinculadas diretamente a este item neste bloco
            perguntas_bloco_item = []
            for p in agenda.perguntas.all():
                p_item_ids = set(p.itens_norma.values_list('id', flat=True))
                
                # Se a pergunta tem vinculo explicito com este item OU se a pergunta nao tem vinculo e a agenda tem vinculo com este item
                if item.id in p_item_ids or (not p_item_ids and item.id in ag_item_ids):
                    perguntas_bloco_item.append(p)
                    todas_perguntas_item_set.add(p.id)
                    
            if perguntas_bloco_item or (item.id in ag_item_ids):
                perguntas_info = []
                for p in perguntas_bloco_item:
                    resp = respostas_map.get(p.id)
                    sols_list = []
                    if resp:
                        for s in resp.solicitacoes.all():
                            sols_list.append({
                                'id': s.id,
                                'solicitacao': s.solicitacao,
                                'evidencia': s.evidencia or '',
                                'conclusao': s.conclusao,
                                'conclusao_display': s.get_conclusao_display()
                            })

                    perguntas_info.append({
                        'id': p.id,
                        'texto_pergunta': p.texto_pergunta,
                        'dica_auditor': p.dica_auditor or '',
                        'classificacao': resp.classificacao if resp else 'P',
                        'classificacao_display': resp.get_classificacao_display() if resp else 'Pendente',
                        'texto_resposta': resp.texto_resposta if (resp and resp.texto_resposta) else '',
                        'solicitacoes': sols_list
                    })
                    
                blocos_associados.append({
                    'bloco_id': agenda.id,
                    'bloco_titulo': agenda.titulo,
                    'total_perguntas': len(perguntas_info),
                    'perguntas': perguntas_info
                })
                    
        # Status Calculado (Apenas para os níveis finais/folhas dos itens da norma)
        if is_parent:
            status_item = ""
        elif item.id in na_item_ids:
            status_item = "NA"
        elif not todas_perguntas_item_set:
            status_item = "P" if blocos_associados else "NA"
        else:
            pior_peso = 0
            for p_id in todas_perguntas_item_set:
                r = respostas_map.get(p_id)
                classificacao = r.classificacao if r else "P"
                peso = hierarchy.get(classificacao, 4)
                if peso > pior_peso:
                    pior_peso = peso
            status_item = reverse_hierarchy.get(pior_peso, "P")
            
        matriz_data.append({
            "id": item.id,
            "referencia": item.referencia,
            "titulo": item.titulo,
            "descricao": item.descricao or item.titulo,
            "is_parent": is_parent,
            "level": len(item.referencia.split('.')),
            "status": status_item,
            "qtd_perguntas": len(todas_perguntas_item_set) if not is_parent else "",
            "blocos_associados": blocos_associados,
            "blocos_associados_json": json.dumps(blocos_associados)
        })

    # Calcula as métricas e estatísticas do relatório (desconsiderando N/A)
    count_c = sum(1 for m in matriz_data if not m["is_parent"] and m["status"] == "C")
    count_nc = sum(1 for m in matriz_data if not m["is_parent"] and m["status"] == "NC")
    count_om = sum(1 for m in matriz_data if not m["is_parent"] and m["status"] == "OM")
    count_p = sum(1 for m in matriz_data if not m["is_parent"] and m["status"] == "P")
    count_na = sum(1 for m in matriz_data if not m["is_parent"] and m["status"] == "NA")

    total_avaliados = count_c + count_nc + count_om + count_p
    
    pct_c = round((count_c / total_avaliados * 100), 1) if total_avaliados > 0 else 0
    pct_nc = round((count_nc / total_avaliados * 100), 1) if total_avaliados > 0 else 0
    pct_om = round((count_om / total_avaliados * 100), 1) if total_avaliados > 0 else 0
    pct_p = round((count_p / total_avaliados * 100), 1) if total_avaliados > 0 else 0

    stats = {
        "count_c": count_c,
        "count_nc": count_nc,
        "count_om": count_om,
        "count_p": count_p,
        "count_na": count_na,
        "total_avaliados": total_avaliados,
        "pct_c": pct_c,
        "pct_nc": pct_nc,
        "pct_om": pct_om,
        "pct_p": pct_p,
    }
        
    context = {
        "auditoria": auditoria,
        "matriz_data": matriz_data,
        "stats": stats
    }
    
    return render(request, "auditoria/iso_matriz.html", context)


@login_required
def iso_auditoria_export_excel(request, auditoria_id):
    """Gera e exporta relatório em Excel (.xlsx) completo da Auditoria com 4 abas estruturadas"""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from django.http import HttpResponse
    from .models import AuditoriaIso, RespostaEntrevistaIso, ItemNorma

    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    agendas = list(auditoria.agendas.all().prefetch_related('perguntas', 'itens_norma', 'perguntas__itens_norma'))
    
    respostas = RespostaEntrevistaIso.objects.filter(auditoria=auditoria).prefetch_related('solicitacoes')
    respostas_map = {r.pergunta_id: r for r in respostas}

    wb = openpyxl.Workbook()
    
    # Estilos visuais
    font_header = Font(name="Arial", size=11, bold=True, color="FFFFFF")
    fill_header = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    fill_sub_header = PatternFill(start_color="E0E7FF", end_color="E0E7FF", fill_type="solid")
    font_sub_header = Font(name="Arial", size=10, bold=True, color="1E3A8A")
    font_title = Font(name="Arial", size=14, bold=True, color="1E3A8A")

    fill_c = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
    fill_nc = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
    fill_om = PatternFill(start_color="FEF9C3", end_color="FEF9C3", fill_type="solid")
    fill_na = PatternFill(start_color="F3F4F6", end_color="F3F4F6", fill_type="solid")
    fill_p = PatternFill(start_color="FFEDD5", end_color="FFEDD5", fill_type="solid")

    font_c = Font(name="Arial", size=10, bold=True, color="166534")
    font_nc = Font(name="Arial", size=10, bold=True, color="991B1B")
    font_om = Font(name="Arial", size=10, bold=True, color="854D0E")
    font_na = Font(name="Arial", size=10, bold=True, color="374151")
    font_p = Font(name="Arial", size=10, bold=True, color="9A3412")

    def apply_status_style(cell, val):
        val_upper = str(val).upper()
        if 'CONFORME' in val_upper and 'NÃO' not in val_upper:
            cell.fill, cell.font = fill_c, font_c
        elif 'NÃO CONFORME' in val_upper or 'NC' in val_upper:
            cell.fill, cell.font = fill_nc, font_nc
        elif 'OPORTUNIDADE' in val_upper or 'OM' in val_upper:
            cell.fill, cell.font = fill_om, font_om
        elif 'PENDENTE' in val_upper or 'P' in val_upper:
            cell.fill, cell.font = fill_p, font_p
        else:
            cell.fill, cell.font = fill_na, font_na

    # 1. Resumo Executivo
    ws_resumo = wb.active
    ws_resumo.title = "Resumo Executivo"
    ws_resumo['A1'] = f"RELATÓRIO DE AUDITORIA DE CONFORMIDADE ({auditoria.norma.codigo})"
    ws_resumo['A1'].font = font_title
    ws_resumo.merge_cells('A1:E1')

    meta_info = [
        ("Código da Auditoria", f"AUD-ISO-{auditoria.id}"),
        ("Norma de Referência", f"{auditoria.norma.codigo} - {auditoria.norma.descricao}"),
        ("Data de Início", auditoria.data_inicio.strftime('%d/%m/%Y')),
        ("Data de Fim Prevista", auditoria.data_fim.strftime('%d/%m/%Y')),
        ("Status Geral", auditoria.get_status_display()),
        ("Auditores Responsáveis", ", ".join([a.get_full_name() or a.username for a in auditoria.auditores.all()])),
    ]

    for idx, (label, val) in enumerate(meta_info, start=3):
        c_lbl = ws_resumo.cell(row=idx, column=1, value=label)
        c_lbl.font = font_sub_header
        c_lbl.fill = fill_sub_header
        ws_resumo.cell(row=idx, column=2, value=val).font = Font(name="Arial", size=10, bold=True)

    # 2. Matriz de Conformidade
    ws_matriz = wb.create_sheet(title="Matriz de Conformidade")
    headers_matriz = ["Referência", "Título do Requisito da Norma", "Qtd. Perguntas", "Status Calculado"]
    ws_matriz.append(headers_matriz)
    for col_idx in range(1, len(headers_matriz) + 1):
        cell = ws_matriz.cell(row=1, column=col_idx)
        cell.font = font_header
        cell.fill = fill_header

    itens_escopo = auditoria.escopo_itens.all()
    if not itens_escopo.exists():
        itens_escopo = ItemNorma.objects.filter(norma=auditoria.norma)
    itens_escopo_list = list(itens_escopo)

    status_display_map = {"C": "Conforme", "NC": "Não Conforme", "OM": "Oportunidade", "NA": "Não Aplicável", "P": "Pendente"}
    hierarchy = {"NC": 5, "P": 4, "OM": 3, "C": 2, "NA": 1}
    reverse_hierarchy = {v: k for k, v in hierarchy.items()}

    for item in sorted(itens_escopo_list, key=lambda x: (x.ordem or 0, natural_sort_key(x.referencia))):
        todas_perguntas_item_set = set()
        for agenda in agendas:
            for p in agenda.perguntas.all():
                if item in p.itens_norma.all():
                    todas_perguntas_item_set.add(p.id)
                    
        pior_peso = 0
        if todas_perguntas_item_set:
            for p_id in todas_perguntas_item_set:
                r = respostas_map.get(p_id)
                c = r.classificacao if r else "P"
                peso = hierarchy.get(c, 4)
                if peso > pior_peso:
                    pior_peso = peso
            st = reverse_hierarchy.get(pior_peso, "P")
        else:
            st = "P" if any(item in ag.itens_norma.all() for ag in agendas) else "NA"

        st_disp = status_display_map.get(st, "Pendente")
        ws_matriz.append([item.referencia, item.titulo, len(todas_perguntas_item_set), st_disp])
        r_idx = ws_matriz.max_row
        c_st = ws_matriz.cell(row=r_idx, column=4)
        apply_status_style(c_st, st_disp)
        c_st.alignment = Alignment(horizontal="center")

    # 3. Checklist & Evidências
    ws_checklist = wb.create_sheet(title="Checklist & Evidências")
    headers_check = ["Bloco / Agenda", "Requisito(s)", "Enunciado da Pergunta", "Dica do Auditor", "Classificação", "Evidências / Anotações"]
    ws_checklist.append(headers_check)
    for col_idx in range(1, len(headers_check) + 1):
        cell = ws_checklist.cell(row=1, column=col_idx)
        cell.font = font_header
        cell.fill = fill_header

    for agenda in agendas:
        for p in agenda.perguntas.all():
            r = respostas_map.get(p.id)
            classif_disp = r.get_classificacao_display() if r else "Pendente"
            evid_texto = r.texto_resposta if (r and r.texto_resposta) else "Aguardando preenchimento"
            itens_str = ", ".join([it.referencia for it in p.itens_norma.all()]) or "Identificação / Geral"
            
            ws_checklist.append([
                agenda.titulo,
                itens_str,
                p.texto_pergunta,
                p.dica_auditor or "",
                classif_disp,
                evid_texto
            ])
            r_idx = ws_checklist.max_row
            c_cl = ws_checklist.cell(row=r_idx, column=5)
            apply_status_style(c_cl, classif_disp)

    # 4. Solicitações de Evidência
    ws_sols = wb.create_sheet(title="Solicitações & Amostragens")
    headers_sols = ["Bloco / Agenda", "Pergunta Relacionada", "Item / Documento Solicitado", "Evidência Constatada", "Conclusão da Amostra"]
    ws_sols.append(headers_sols)
    for col_idx in range(1, len(headers_sols) + 1):
        cell = ws_sols.cell(row=1, column=col_idx)
        cell.font = font_header
        cell.fill = fill_header

    for agenda in agendas:
        for p in agenda.perguntas.all():
            r = respostas_map.get(p.id)
            if r:
                for sol in r.solicitacoes.all():
                    ws_sols.append([
                        agenda.titulo,
                        p.texto_pergunta,
                        sol.solicitacao,
                        sol.evidencia or "Não registrada",
                        sol.get_conclusao_display()
                    ])
                    r_idx = ws_sols.max_row
                    c_c = ws_sols.cell(row=r_idx, column=5)
                    apply_status_style(c_c, sol.get_conclusao_display())

    # Auto-fit colunas
    for sheet in wb.worksheets:
        for col in sheet.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            sheet.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 65)

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response['Content-Disposition'] = f'attachment; filename="Relatorio_Auditoria_ISO_{auditoria.id}.xlsx"'
    wb.save(response)
    return response


# ==========================================
# VIEWS SETUP ISO 13485 (CRUD FRONTEND)
# ==========================================

@login_required
def iso_setup_dashboard(request):
    """Nível 1: Visão Global das Normas Cadastradas"""
    normas = Norma.objects.all().order_by('codigo')
    return render(request, "auditoria/iso/setup/dashboard.html", {
        "normas": normas,
    })

@login_required
def iso_norma_detail(request, pk):
    """Nível 2: Visão Específica da Norma (Itens, Perguntas, Modelos, Agendas)"""
    from .models import ModeloAuditoriaIso
    norma = get_object_or_404(Norma, pk=pk)
    
    itens_qs = ItemNorma.objects.filter(norma=norma).order_by('ordem', 'referencia')
    itens = []
    for item in itens_qs:
        item.nivel = item.referencia.count('.')
        itens.append(item)
        
    perguntas = BancoPergunta.objects.filter(itens_norma__norma=norma).distinct().prefetch_related('itens_norma')
        
    modelos = ModeloAuditoriaIso.objects.filter(norma=norma).prefetch_related('perguntas')
    auditorias = AuditoriaIso.objects.filter(norma=norma).order_by('-criado_em')
    
    return render(request, "auditoria/iso/setup/norma_detail.html", {
        "norma": norma,
        "itens": itens,
        "perguntas": perguntas,
        "modelos": modelos,
        "auditorias": auditorias,
        "active_tab": request.GET.get('tab', 'itens')
    })

# --- Norma CRUD ---
@login_required
def iso_norma_create(request):
    if request.method == "POST":
        form = NormaIsoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Norma cadastrada com sucesso!")
            return redirect(reverse('auditoria:iso_setup_dashboard') + "?tab=normas")
    else:
        form = NormaIsoForm()
    return render(request, "auditoria/iso/setup/form_generico.html", {"form": form, "title": "Nova Norma", "back_url": reverse('auditoria:iso_setup_dashboard') + "?tab=normas"})

@login_required
def iso_norma_edit(request, pk):
    norma = get_object_or_404(Norma, pk=pk)
    if request.method == "POST":
        form = NormaIsoForm(request.POST, instance=norma)
        if form.is_valid():
            form.save()
            messages.success(request, "Norma atualizada!")
            return redirect(reverse('auditoria:iso_setup_dashboard') + "?tab=normas")
    else:
        form = NormaIsoForm(instance=norma)
    return render(request, "auditoria/iso/setup/form_generico.html", {"form": form, "title": f"Editar Norma: {norma.codigo}", "back_url": reverse('auditoria:iso_setup_dashboard') + "?tab=normas"})

@login_required
@require_POST
def iso_norma_archive(request, pk):
    norma = get_object_or_404(Norma, pk=pk)
    norma.ativa = not norma.ativa
    norma.save()
    msg = "arquivada" if not norma.ativa else "desarquivada"
    messages.success(request, f"Norma {msg} com sucesso!")
    return redirect('auditoria:iso_norma_detail', pk=pk)

@login_required
@require_POST
def iso_norma_delete(request, pk):
    norma = get_object_or_404(Norma, pk=pk)
    norma.delete()
    messages.success(request, "Norma removida com sucesso!")
    return redirect(reverse('auditoria:iso_setup_dashboard') + "?tab=normas")

# --- ItemNorma CRUD ---
@login_required
def iso_item_detail_api(request, pk):
    from django.http import JsonResponse
    item = get_object_or_404(ItemNorma, pk=pk)
    return JsonResponse({
        "id": item.id,
        "norma_codigo": item.norma.codigo,
        "norma_id": item.norma_id,
        "referencia": item.referencia,
        "titulo": item.titulo,
        "descricao": item.descricao or "",
        "ordem": item.ordem,
        "edit_url": reverse('auditoria:iso_item_edit', args=[item.id]),
        "delete_url": reverse('auditoria:iso_item_delete', args=[item.id]),
    })

@login_required
def iso_item_create(request):
    if request.method == "POST":
        form = ItemNormaIsoForm(request.POST)
        if form.is_valid():
            item = form.save()
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'id': item.id})
            messages.success(request, "Item da norma cadastrado com sucesso!")
            return redirect(reverse('auditoria:iso_setup_dashboard') + "?tab=itens")
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    else:
        form = ItemNormaIsoForm()
    return render(request, "auditoria/iso/setup/form_generico.html", {"form": form, "title": "Novo Item da Norma", "back_url": reverse('auditoria:iso_setup_dashboard') + "?tab=itens"})

@login_required
def iso_item_edit(request, pk):
    item = get_object_or_404(ItemNorma, pk=pk)
    if request.method == "POST":
        form = ItemNormaIsoForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'id': item.id, 'referencia': item.referencia, 'titulo': item.titulo, 'descricao': item.descricao or ''})
            messages.success(request, "Item atualizado!")
            return redirect(reverse('auditoria:iso_setup_dashboard') + "?tab=itens")
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    else:
        form = ItemNormaIsoForm(instance=item)
    return render(request, "auditoria/iso/setup/form_generico.html", {"form": form, "title": f"Editar Item: {item.referencia}", "back_url": reverse('auditoria:iso_setup_dashboard') + "?tab=itens"})

@login_required
@require_POST
def iso_item_delete(request, pk):
    item = get_object_or_404(ItemNorma, pk=pk)
    item.delete()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'id': pk})
    messages.success(request, "Item removido com sucesso!")
    return redirect(reverse('auditoria:iso_setup_dashboard') + "?tab=itens")

# --- BancoPergunta CRUD ---
@login_required
def iso_pergunta_create(request):
    if request.method == "POST":
        form = BancoPerguntaIsoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Pergunta adicionada ao banco!")
            return redirect(reverse('auditoria:iso_setup_dashboard') + "?tab=perguntas")
    else:
        form = BancoPerguntaIsoForm()
    return render(request, "auditoria/iso/setup/form_generico.html", {"form": form, "title": "Nova Pergunta de Auditoria", "back_url": reverse('auditoria:iso_setup_dashboard') + "?tab=perguntas"})

@login_required
def iso_pergunta_edit(request, pk):
    pergunta = get_object_or_404(BancoPergunta, pk=pk)
    if request.method == "POST":
        form = BancoPerguntaIsoForm(request.POST, instance=pergunta)
        if form.is_valid():
            form.save()
            messages.success(request, "Pergunta atualizada!")
            return redirect(reverse('auditoria:iso_setup_dashboard') + "?tab=perguntas")
    else:
        form = BancoPerguntaIsoForm(instance=pergunta)
    return render(request, "auditoria/iso/setup/form_generico.html", {"form": form, "title": "Editar Pergunta", "back_url": reverse('auditoria:iso_setup_dashboard') + "?tab=perguntas"})

@login_required
@require_POST
def iso_pergunta_delete(request, pk):
    pergunta = get_object_or_404(BancoPergunta, pk=pk)
    pergunta.delete()
    messages.success(request, "Pergunta removida com sucesso!")
    return redirect(reverse('auditoria:iso_setup_dashboard') + "?tab=perguntas")

# --- ModeloAuditoriaIso CRUD ---
@login_required
def iso_modelo_create(request):
    from .models import ModeloAuditoriaIso
    from .forms import ModeloAuditoriaIsoForm
    norma_id = request.GET.get('norma') or request.POST.get('norma')
    
    if request.method == "POST":
        form = ModeloAuditoriaIsoForm(request.POST, initial={'norma': norma_id} if norma_id else None)
        if form.is_valid():
            modelo = form.save()
            messages.success(request, f"Modelo de Auditoria '{modelo.titulo}' criado com sucesso!")
            target_norma = norma_id or modelo.norma_id
            if target_norma:
                return redirect(reverse('auditoria:iso_norma_detail', args=[target_norma]) + "?tab=modelos")
            return redirect(reverse('auditoria:iso_setup_dashboard'))
    else:
        initial = {'norma': norma_id} if norma_id else {}
        form = ModeloAuditoriaIsoForm(initial=initial)
        
    back_url = reverse('auditoria:iso_norma_detail', args=[norma_id]) + "?tab=modelos" if norma_id else reverse('auditoria:iso_setup_dashboard')
    
    perguntas_norma = BancoPergunta.objects.all().prefetch_related('itens_norma')
    if norma_id:
        perguntas_norma = BancoPergunta.objects.filter(itens_norma__norma_id=norma_id).distinct().prefetch_related('itens_norma')
        
    return render(request, "auditoria/iso/setup/form_modelo.html", {
        "form": form,
        "title": "Novo Modelo de Auditoria (Template)",
        "back_url": back_url,
        "perguntas_norma": perguntas_norma,
        "perguntas_selecionadas_ids": [],
    })

@login_required
def iso_modelo_edit(request, pk):
    from .models import ModeloAuditoriaIso
    from .forms import ModeloAuditoriaIsoForm
    modelo = get_object_or_404(ModeloAuditoriaIso, pk=pk)
    norma_id = modelo.norma_id
    
    if request.method == "POST":
        form = ModeloAuditoriaIsoForm(request.POST, instance=modelo)
        if form.is_valid():
            form.save()
            messages.success(request, f"Modelo '{modelo.titulo}' atualizado com sucesso!")
            return redirect(reverse('auditoria:iso_norma_detail', args=[norma_id]) + "?tab=modelos")
    else:
        form = ModeloAuditoriaIsoForm(instance=modelo)
        
    back_url = reverse('auditoria:iso_norma_detail', args=[norma_id]) + "?tab=modelos"
    perguntas_norma = BancoPergunta.objects.filter(itens_norma__norma_id=norma_id).distinct().prefetch_related('itens_norma')
    perguntas_selecionadas_ids = set(modelo.perguntas.values_list('id', flat=True))
    
    return render(request, "auditoria/iso/setup/form_modelo.html", {
        "form": form,
        "title": f"Editar Modelo: {modelo.titulo}",
        "back_url": back_url,
        "perguntas_norma": perguntas_norma,
        "perguntas_selecionadas_ids": perguntas_selecionadas_ids,
    })

@login_required
def iso_modelo_detail(request, pk):
    """Visão de Detalhes do Modelo (Template Mode com Visão por Blocos e Matriz Orientada aos Itens da Norma)"""
    from .models import ModeloAuditoriaIso, ItemNorma
    modelo = get_object_or_404(ModeloAuditoriaIso, pk=pk)
    blocos = modelo.blocos.all().prefetch_related('perguntas', 'itens_norma')
    itens_norma_todos = list(ItemNorma.objects.filter(norma=modelo.norma).order_by('ordem', 'referencia'))
    
    # Identifica itens que são pais/agrupadores na norma (possuem sub-itens)
    parent_ids_global = set()
    for item in itens_norma_todos:
        if item.parent_id:
            parent_ids_global.add(item.parent_id)
        prefix = item.referencia + '.'
        if any(other.referencia.startswith(prefix) for other in itens_norma_todos if other.id != item.id):
            parent_ids_global.add(item.id)

    # Considera apenas os itens de último nível (folhas sem sub-itens)
    itens_norma_folhas = [item for item in itens_norma_todos if item.id not in parent_ids_global]
    
    # Matriz de Mapeamento Orientado aos Itens da Norma
    matriz_requisitos = []
    total_multi_associacoes = 0
    total_alvo_modelo = 0
    
    total_cobertos_100 = 0
    total_pendentes = 0

    for item in itens_norma_folhas:
        blocos_associados = []
        for bloco in blocos:
            is_alvo = bloco.itens_norma.filter(id=item.id).exists()
            if is_alvo:
                perguntas_do_item = [p for p in bloco.perguntas.all() if p.itens_norma.filter(id=item.id).exists()]
                blocos_associados.append({
                    'bloco': bloco,
                    'perguntas': perguntas_do_item,
                    'total_perguntas': len(perguntas_do_item)
                })
        
        if blocos_associados:
            total_alvo_modelo += 1
            is_multi = len(blocos_associados) > 1
            if is_multi:
                total_multi_associacoes += 1

            is_coberto_100 = all(b['total_perguntas'] > 0 for b in blocos_associados)
            if is_coberto_100:
                total_cobertos_100 += 1
            else:
                total_pendentes += 1
                
            matriz_requisitos.append({
                'item': item,
                'blocos_associados': blocos_associados,
                'total_blocos': len(blocos_associados),
                'is_multi': is_multi,
                'tem_cobertura': any(b['total_perguntas'] > 0 for b in blocos_associados),
                'is_coberto_100': is_coberto_100,
                'status_cobertura': 'COMPLETO' if is_coberto_100 else 'PENDENTE'
            })

    total_single_associacoes = total_alvo_modelo - total_multi_associacoes

    return render(request, "auditoria/iso/setup/modelo_detail.html", {
        "modelo": modelo,
        "blocos": blocos,
        "itens_norma_todos": itens_norma_todos,
        "matriz_requisitos": matriz_requisitos,
        "total_alvo_modelo": total_alvo_modelo,
        "total_multi_associacoes": total_multi_associacoes,
        "total_single_associacoes": total_single_associacoes,
        "total_cobertos_100": total_cobertos_100,
        "total_pendentes": total_pendentes,
        "mode": "template",
        "back_url": reverse('auditoria:iso_norma_detail', args=[modelo.norma_id]) + "?tab=modelos"
    })

@login_required
@require_POST
def iso_modelo_bloco_create(request, modelo_id):
    from .models import ModeloAuditoriaIso, BlocoModeloIso
    from django.http import JsonResponse
    modelo = get_object_or_404(ModeloAuditoriaIso, pk=modelo_id)
    titulo = request.POST.get("titulo")
    if not titulo:
        return JsonResponse({'success': False, 'message': 'O título do bloco é obrigatório.'}, status=400)
        
    bloco = BlocoModeloIso.objects.create(modelo=modelo, titulo=titulo)
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'id': bloco.id, 'titulo': bloco.titulo})
        
    messages.success(request, f"Bloco '{bloco.titulo}' adicionado ao modelo!")
    return redirect('auditoria:iso_modelo_detail', pk=modelo.id)

@login_required
@require_POST
def iso_modelo_bloco_edit(request, modelo_id, pk):
    from .models import BlocoModeloIso
    from django.http import JsonResponse
    bloco = get_object_or_404(BlocoModeloIso, pk=pk, modelo_id=modelo_id)
    titulo = request.POST.get("titulo")
    if titulo:
        bloco.titulo = titulo
        bloco.save()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    messages.success(request, "Título do bloco atualizado!")
    return redirect('auditoria:iso_modelo_detail', pk=modelo_id)

@login_required
@require_POST
def iso_modelo_bloco_delete(request, modelo_id, pk):
    from .models import BlocoModeloIso
    bloco = get_object_or_404(BlocoModeloIso, pk=pk, modelo_id=modelo_id)
    bloco.delete()
    messages.success(request, "Bloco removido do modelo!")
    return redirect('auditoria:iso_modelo_detail', pk=modelo_id)

@login_required
def iso_modelo_bloco_perguntas(request, modelo_id, pk):
    from .models import BlocoModeloIso, BancoPergunta, ItemNorma
    bloco = get_object_or_404(BlocoModeloIso, pk=pk, modelo_id=modelo_id)
    if request.method == "POST":
        if "vincular_pergunta_id" in request.POST:
            p_id = request.POST.get("vincular_pergunta_id")
            if p_id:
                bloco.perguntas.add(p_id)
                messages.success(request, "Pergunta vinculada a este bloco do modelo com sucesso!")
                return redirect('auditoria:iso_modelo_bloco_perguntas', modelo_id=modelo_id, pk=pk)

        pergunta_ids = request.POST.getlist("perguntas")
        bloco.perguntas.set(pergunta_ids)
        messages.success(request, "Perguntas vinculadas ao bloco do modelo!")
        return redirect('auditoria:iso_modelo_bloco_perguntas', modelo_id=modelo_id, pk=pk)
        
    perguntas_disponiveis = BancoPergunta.objects.filter(itens_norma__norma=bloco.modelo.norma).prefetch_related('itens_norma').order_by('itens_norma__ordem', 'itens_norma__referencia').distinct()
    perguntas_vinculadas = bloco.perguntas.all().prefetch_related('itens_norma').order_by('itens_norma__ordem', 'itens_norma__referencia').distinct()
    perguntas_vinculadas_ids = set(perguntas_vinculadas.values_list('id', flat=True))
    
    # Análise de Cobertura de Escopo Planejado para o Bloco do Modelo
    itens_alvo_todos = list(bloco.itens_norma.all())
    
    # Identifica itens que possuem sub-itens selecionados dentro do escopo alvo (pais/agrupadores)
    parent_ids_in_alvo = set()
    for item in itens_alvo_todos:
        prefix = item.referencia + '.'
        if any(other.referencia.startswith(prefix) for other in itens_alvo_todos if other.id != item.id):
            parent_ids_in_alvo.add(item.id)

    # Mantém apenas os itens do último nível (folhas sem sub-itens no escopo)
    itens_alvo = [item for item in itens_alvo_todos if item.id not in parent_ids_in_alvo]
    total_alvo = len(itens_alvo)
    
    itens_cobertos_ids = set()
    for p in perguntas_vinculadas:
        for item in p.itens_norma.all():
            itens_cobertos_ids.add(item.id)

    # Identifica itens cobertos por perguntas em OUTROS blocos do mesmo modelo
    itens_cobertos_outros_blocos_ids = set()
    outros_blocos = list(bloco.modelo.blocos.exclude(id=bloco.id).prefetch_related('perguntas', 'perguntas__itens_norma'))
    
    for b in outros_blocos:
        for p in b.perguntas.all():
            for item in p.itens_norma.all():
                if item.id not in itens_cobertos_ids:
                    itens_cobertos_outros_blocos_ids.add(item.id)
            
    cobertura_status = []
    total_coberto = 0
    for item in itens_alvo:
        is_coberto_neste_bloco = item.id in itens_cobertos_ids
        is_coberto_outro_bloco = item.id in itens_cobertos_outros_blocos_ids

        # Coleta perguntas em OUTROS blocos para este item
        perguntas_outros_blocos = []
        for b in outros_blocos:
            for p in b.perguntas.all():
                if item in p.itens_norma.all():
                    perguntas_outros_blocos.append({
                        'pergunta_id': p.id,
                        'texto_pergunta': p.texto_pergunta,
                        'dica_auditor': p.dica_auditor or '',
                        'bloco_id': b.id,
                        'bloco_titulo': b.titulo
                    })

        if is_coberto_neste_bloco:
            total_coberto += 1
            status_code = 'VERDE'
        elif is_coberto_outro_bloco:
            status_code = 'AMARELO'
        else:
            status_code = 'VERMELHO'

        cobertura_status.append({
            'item': item,
            'coberto': is_coberto_neste_bloco,
            'status_code': status_code,
            'perguntas_outros_blocos': perguntas_outros_blocos,
            'perguntas_outros_blocos_json': json.dumps(perguntas_outros_blocos),
        })
        
    porcentagem_cobertura = round((total_coberto / total_alvo * 100)) if total_alvo > 0 else 0
    itens_norma_todos = ItemNorma.objects.filter(norma=bloco.modelo.norma).order_by('ordem', 'referencia')
    
    return render(request, "auditoria/iso/setup/modelo_bloco_perguntas.html", {
        "bloco": bloco,
        "modelo": bloco.modelo,
        "perguntas_disponiveis": perguntas_disponiveis,
        "perguntas_vinculadas": perguntas_vinculadas,
        "perguntas_vinculadas_ids": perguntas_vinculadas_ids,
        "itens_cobertos_ids": list(itens_cobertos_ids),
        "total_alvo": total_alvo,
        "total_coberto": total_coberto,
        "porcentagem_cobertura": porcentagem_cobertura,
        "cobertura_status": cobertura_status,
        "itens_norma_todos": itens_norma_todos,
        "back_url": reverse('auditoria:iso_modelo_detail', args=[modelo_id])
    })

@login_required
@require_POST
def iso_modelo_bloco_pergunta_create(request, modelo_id, pk):
    """Cria uma nova pergunta no Banco Geral e a vincula atomicamente ao Bloco do Modelo"""
    from .models import BlocoModeloIso, BancoPergunta
    from django.db import transaction
    bloco = get_object_or_404(BlocoModeloIso, pk=pk, modelo_id=modelo_id)
    
    texto_pergunta = request.POST.get("texto_pergunta")
    dica_resposta = request.POST.get("dica_resposta", "")
    item_ids = request.POST.getlist("itens_norma")
    
    if not texto_pergunta:
        messages.error(request, "O enunciado da pergunta é obrigatório.")
        return redirect('auditoria:iso_modelo_bloco_perguntas', modelo_id=modelo_id, pk=pk)
        
    with transaction.atomic():
        nova_pergunta = BancoPergunta.objects.create(
            texto_pergunta=texto_pergunta,
            dica_auditor=dica_resposta
        )
        if item_ids:
            nova_pergunta.itens_norma.set(item_ids)
            
        bloco.perguntas.add(nova_pergunta)
        
    messages.success(request, f"Pergunta '{nova_pergunta.texto_pergunta[:40]}...' criada no Banco Geral e vinculada ao bloco!")
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == 'true':
        from django.http import JsonResponse
        return JsonResponse({
            'success': True,
            'pergunta_id': nova_pergunta.id,
            'texto_pergunta': nova_pergunta.texto_pergunta,
            'bloco_id': bloco.id,
            'bloco_titulo': bloco.titulo,
            'message': f"Pergunta criada e vinculada ao bloco '{bloco.titulo}' com sucesso!"
        })

    next_url = request.POST.get('next') or request.GET.get('next') or request.META.get('HTTP_REFERER')
    if next_url and ('modelos' in next_url or 'setup' in next_url):
        return redirect(next_url)
    return redirect('auditoria:iso_modelo_bloco_perguntas', modelo_id=modelo_id, pk=pk)

@login_required
@require_POST
def iso_pergunta_edit(request, pk):
    """Edita uma pergunta existente no Banco Geral de Perguntas"""
    from .models import BancoPergunta
    from django.http import JsonResponse
    pergunta = get_object_or_404(BancoPergunta, pk=pk)
    
    texto_pergunta = request.POST.get("texto_pergunta")
    dica_resposta = request.POST.get("dica_resposta", "")
    item_ids = request.POST.getlist("itens_norma")
    
    if not texto_pergunta:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == 'true':
            return JsonResponse({'success': False, 'error': 'O enunciado da pergunta é obrigatório.'}, status=400)
        messages.error(request, "O enunciado da pergunta é obrigatório.")
        return redirect(request.META.get('HTTP_REFERER', '/'))
        
    pergunta.texto_pergunta = texto_pergunta
    pergunta.dica_auditor = dica_resposta
    if item_ids:
        pergunta.itens_norma.set(item_ids)
    pergunta.save()
    
    messages.success(request, f"Pergunta '{pergunta.texto_pergunta[:40]}...' atualizada com sucesso!")
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == 'true':
        return JsonResponse({
            'success': True,
            'pergunta_id': pergunta.id,
            'texto_pergunta': pergunta.texto_pergunta,
            'dica_auditor': pergunta.dica_auditor,
            'message': 'Pergunta atualizada com sucesso!'
        })
        
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect(request.META.get('HTTP_REFERER', '/'))

@login_required
@require_POST
def iso_modelo_bloco_alvo_update(request, modelo_id, pk):
    from .models import BlocoModeloIso
    from django.http import JsonResponse
    bloco = get_object_or_404(BlocoModeloIso, pk=pk, modelo_id=modelo_id)
    item_ids = request.POST.getlist("itens_alvo")
    bloco.itens_norma.set(item_ids)
    
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"success": True, "message": "Escopo alvo do bloco atualizado!"})
        
    messages.success(request, "Escopo alvo do bloco atualizado com sucesso!")
    return redirect('auditoria:iso_modelo_detail', pk=modelo_id)

@login_required
@require_POST
def iso_modelo_archive(request, pk):
    from .models import ModeloAuditoriaIso
    modelo = get_object_or_404(ModeloAuditoriaIso, pk=pk)
    modelo.ativo = not modelo.ativo
    modelo.save()
    status_str = "arquivado" if not modelo.ativo else "desarquivado"
    messages.success(request, f"Modelo '{modelo.titulo}' {status_str} com sucesso!")
    return redirect('auditoria:iso_modelo_detail', pk=pk)

@login_required
@require_POST
def iso_modelo_delete(request, pk):
    from .models import ModeloAuditoriaIso
    modelo = get_object_or_404(ModeloAuditoriaIso, pk=pk)
    norma_id = modelo.norma_id
    modelo.delete()
    messages.success(request, "Modelo de Auditoria removido com sucesso!")
    return redirect(reverse('auditoria:iso_norma_detail', args=[norma_id]) + "?tab=modelos")

# --- AuditoriaIso CRUD e Agendas ---

@login_required
def iso_auditoria_detail(request, pk):
    from .models import AuditoriaIso, ModeloAuditoriaIso
    auditoria = get_object_or_404(AuditoriaIso, pk=pk)
    agendas = auditoria.agendas.all()
    modelos_norma = ModeloAuditoriaIso.objects.filter(norma=auditoria.norma, ativo=True)
    
    agendas_progresso = []
    for agenda in agendas:
        agendas_progresso.append({
            'agenda': agenda,
            'progresso': agenda.progresso()
        })
        
    return render(request, "auditoria/iso/setup/auditoria_detail.html", {
        "auditoria": auditoria,
        "agendas_progresso": agendas_progresso,
        "modelos_norma": modelos_norma,
    })

@login_required
@require_POST
def iso_auditoria_archive(request, pk):
    from .models import AuditoriaIso
    auditoria = get_object_or_404(AuditoriaIso, pk=pk)
    auditoria.arquivada = not auditoria.arquivada
    if auditoria.arquivada:
        auditoria.status = "ARQUIVADA"
        msg = f"Auditoria '{auditoria.norma.codigo}' arquivada com sucesso!"
    else:
        auditoria.status = "PLANEJADA"
        msg = f"Auditoria '{auditoria.norma.codigo}' desarquivada com sucesso!"
    auditoria.save()
    messages.success(request, msg)
    return redirect(reverse('auditoria:iso_norma_detail', args=[auditoria.norma_id]) + "?tab=agendas")

@login_required
@require_POST
def iso_auditoria_delete(request, pk):
    from .models import AuditoriaIso
    auditoria = get_object_or_404(AuditoriaIso, pk=pk)
    norma_id = auditoria.norma_id
    auditoria.delete()
    messages.success(request, "Planejamento de Auditoria excluído com sucesso!")
    return redirect(reverse('auditoria:iso_norma_detail', args=[norma_id]) + "?tab=agendas")

@login_required
@require_POST
def iso_agenda_archive(request, auditoria_id, pk):
    from .models import AgendaAuditoriaIso
    agenda = get_object_or_404(AgendaAuditoriaIso, pk=pk, auditoria_id=auditoria_id)
    agenda.arquivada = not agenda.arquivada
    agenda.save()
    status_str = "arquivado" if agenda.arquivada else "desarquivado"
    messages.success(request, f"Bloco '{agenda.titulo}' {status_str} com sucesso!")
    return redirect('auditoria:iso_auditoria_detail', pk=auditoria_id)

@login_required
@require_POST
def iso_agenda_delete(request, auditoria_id, pk):
    from .models import AgendaAuditoriaIso
    agenda = get_object_or_404(AgendaAuditoriaIso, pk=pk, auditoria_id=auditoria_id)
    agenda.delete()
    messages.success(request, "Bloco da agenda removido com sucesso!")
    return redirect('auditoria:iso_auditoria_detail', pk=auditoria_id)

@login_required
def iso_agenda_create(request, auditoria_id):
    from .models import AuditoriaIso
    from .forms import AgendaAuditoriaIsoCreateForm
    from django.http import JsonResponse
    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    
    if request.method == "POST":
        form = AgendaAuditoriaIsoCreateForm(request.POST)
        if form.is_valid():
            agenda = form.save(commit=False)
            agenda.auditoria = auditoria
            agenda.save()
            form.save_m2m()
            
            # Instanciação do Modelo Base (Clonagem em Lote dos Blocos e Perguntas)
            if agenda.modelo_base:
                blocos_modelo = agenda.modelo_base.blocos.all().prefetch_related('perguntas', 'itens_norma')
                if blocos_modelo.exists():
                    primeiro_bloco = blocos_modelo.first()
                    agenda.titulo = primeiro_bloco.titulo
                    agenda.save()
                    agenda.perguntas.set(primeiro_bloco.perguntas.all())
                    agenda.itens_norma.set(primeiro_bloco.itens_norma.all())
                    
                    for b in blocos_modelo[1:]:
                        nova_agenda = AgendaAuditoriaIso.objects.create(
                            auditoria=auditoria,
                            modelo_base=agenda.modelo_base,
                            titulo=b.titulo
                        )
                        nova_agenda.perguntas.set(b.perguntas.all())
                        nova_agenda.itens_norma.set(b.itens_norma.all())
                else:
                    perguntas_modelo = agenda.modelo_base.perguntas.all()
                    agenda.perguntas.set(perguntas_modelo)
                    itens_alvo_ids = {item.id for p in perguntas_modelo.prefetch_related('itens_norma') for item in p.itens_norma.all()}
                    if itens_alvo_ids:
                        agenda.itens_norma.set(itens_alvo_ids)
            
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'id': agenda.id,
                    'titulo': agenda.titulo,
                    'detail_url': reverse('auditoria:iso_agenda_detail', args=[auditoria.id, agenda.id]),
                    'edit_url': reverse('auditoria:iso_agenda_edit', args=[auditoria.id, agenda.id]),
                    'delete_url': reverse('auditoria:iso_agenda_delete', args=[auditoria.id, agenda.id]),
                    'vincular_url': reverse('auditoria:iso_agenda_perguntas_edit', args=[auditoria.id, agenda.id]),
                    'entrevista_url': reverse('auditoria:iso_entrevista_view', args=[auditoria.id]) + f"?agenda_id={agenda.id}",
                })
                
            messages.success(request, "Agenda criada com sucesso!")
            return redirect('auditoria:iso_auditoria_detail', pk=auditoria.id)
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    else:
        form = AgendaAuditoriaIsoCreateForm()
        
    return render(request, "auditoria/iso/setup/agenda_form.html", {
        "form": form, 
        "auditoria": auditoria,
        "title": "Nova Agenda de Auditoria",
        "back_url": reverse('auditoria:iso_auditoria_detail', kwargs={'pk': auditoria.id})
    })

@login_required
def iso_agenda_edit(request, auditoria_id, pk):
    from .models import AgendaAuditoriaIso, AuditoriaIso
    from .forms import AgendaAuditoriaIsoEditForm
    from django.http import JsonResponse
    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    agenda = get_object_or_404(AgendaAuditoriaIso, pk=pk, auditoria=auditoria)
    
    if request.method == "POST":
        form = AgendaAuditoriaIsoEditForm(request.POST, instance=agenda)
        if form.is_valid():
            form.save()
            
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'id': agenda.id,
                    'titulo': agenda.titulo,
                    'data_str': agenda.data.strftime('%d/%m/%Y') if agenda.data else None,
                    'hora_inicio_str': agenda.hora_inicio.strftime('%H:%M') if agenda.hora_inicio else None,
                    'hora_fim_str': agenda.hora_fim.strftime('%H:%M') if agenda.hora_fim else None,
                })
            
            messages.success(request, "Agenda atualizada!")
            return redirect('auditoria:iso_auditoria_detail', pk=auditoria.id)
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    else:
        form = AgendaAuditoriaIsoEditForm(instance=agenda)
        
    # Allow fetching the initial data for the edit modal
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' and request.method == "GET":
        from django.http import JsonResponse
        return JsonResponse({
            'titulo': agenda.titulo,
            'data': agenda.data.strftime('%Y-%m-%d') if agenda.data else '',
            'hora_inicio': agenda.hora_inicio.strftime('%H:%M') if agenda.hora_inicio else '',
            'hora_fim': agenda.hora_fim.strftime('%H:%M') if agenda.hora_fim else '',
            'action_url': reverse('auditoria:iso_agenda_edit', args=[auditoria.id, agenda.id])
        })
        
    return render(request, "auditoria/iso/setup/agenda_form.html", {
        "form": form, 
        "auditoria": auditoria,
        "title": f"Editar Agenda: {agenda.titulo}",
        "back_url": reverse('auditoria:iso_auditoria_detail', kwargs={'pk': auditoria.id})
    })

@login_required
@require_POST
def iso_agenda_delete(request, auditoria_id, pk):
    from .models import AgendaAuditoriaIso
    agenda = get_object_or_404(AgendaAuditoriaIso, pk=pk, auditoria_id=auditoria_id)
    agenda.delete()
    messages.success(request, "Agenda removida com sucesso!")
    return redirect('auditoria:iso_auditoria_detail', pk=auditoria_id)

@login_required
def iso_agenda_detail(request, auditoria_id, pk):
    from .models import AgendaAuditoriaIso, AuditoriaIso, ItemNorma
    from .forms import BancoPerguntaIsoForm
    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    agenda = get_object_or_404(AgendaAuditoriaIso, pk=pk, auditoria=auditoria)
    
    # Formulario para criar nova pergunta direto no bloco
    form_nova_pergunta = BancoPerguntaIsoForm()
    itens_norma_todos = ItemNorma.objects.filter(norma=auditoria.norma).order_by('referencia')
    if not itens_norma_todos.exists():
        itens_norma_todos = ItemNorma.objects.all().order_by('referencia')
    
    if request.method == "POST" and "vincular_pergunta_id" in request.POST:
        p_id = request.POST.get("vincular_pergunta_id")
        if p_id:
            agenda.perguntas.add(p_id)
            messages.success(request, "Pergunta vinculada a este bloco da agenda com sucesso!")
            return redirect('auditoria:iso_agenda_detail', auditoria_id=auditoria_id, pk=pk)

    # Análise de Cobertura de Escopo (Apenas itens de último nível / folhas)
    itens_alvo_todos = sorted(list(agenda.itens_norma.all()), key=lambda x: (x.ordem or 0, natural_sort_key(x.referencia)))
    
    parent_ids_in_alvo = set()
    for item in itens_alvo_todos:
        prefix = item.referencia + '.'
        if any(other.referencia.startswith(prefix) for other in itens_alvo_todos if other.id != item.id):
            parent_ids_in_alvo.add(item.id)

    itens_alvo = [item for item in itens_alvo_todos if item.id not in parent_ids_in_alvo]
    itens_cobertos_qs = agenda.itens_cobertos()
    itens_cobertos_ids = set(itens_cobertos_qs.values_list('id', flat=True))
    
    # Identifica perguntas e itens em OUTROS blocos desta mesma auditoria
    outras_agendas = list(auditoria.agendas.exclude(id=agenda.id).prefetch_related('perguntas', 'perguntas__itens_norma'))
    
    itens_cobertos_outras_agendas_ids = set()
    for ag in outras_agendas:
        for p in ag.perguntas.all():
            for item in p.itens_norma.all():
                if item.id not in itens_cobertos_ids:
                    itens_cobertos_outras_agendas_ids.add(item.id)

    cobertura_status = []
    total_coberto = 0
    for item in itens_alvo:
        is_coberto_neste_bloco = item.id in itens_cobertos_ids
        is_coberto_outro_bloco = item.id in itens_cobertos_outras_agendas_ids

        perguntas_outros_blocos = []
        for ag in outras_agendas:
            for p in ag.perguntas.all():
                if item in p.itens_norma.all():
                    perguntas_outros_blocos.append({
                        'pergunta_id': p.id,
                        'texto_pergunta': p.texto_pergunta,
                        'dica_auditor': p.dica_auditor or '',
                        'bloco_id': ag.id,
                        'bloco_titulo': ag.titulo
                    })

        if is_coberto_neste_bloco:
            total_coberto += 1
            status_code = 'VERDE'
        elif is_coberto_outro_bloco:
            status_code = 'AMARELO'
        else:
            status_code = 'VERMELHO'

        cobertura_status.append({
            'item': item,
            'coberto': is_coberto_neste_bloco,
            'status_code': status_code,
            'perguntas_outros_blocos': perguntas_outros_blocos,
            'perguntas_outros_blocos_json': json.dumps(perguntas_outros_blocos),
        })

    total_alvo = len(itens_alvo)
    porcentagem_cobertura = round((total_coberto / total_alvo * 100)) if total_alvo > 0 else 0
    
    # Perguntas ordenadas rigorosamente pela ordem numerica natural do item da norma (ex: 7.3.2 antes de 7.3.10)
    def get_pergunta_sort_key(p):
        first_item = p.itens_norma.all()
        if first_item:
            item = first_item[0]
            return (item.ordem or 0, natural_sort_key(item.referencia))
        return (999, [])

    perguntas_lista = list(agenda.perguntas.all().prefetch_related('itens_norma'))
    perguntas_ordenadas = sorted(perguntas_lista, key=get_pergunta_sort_key)

    return render(request, "auditoria/iso/setup/agenda_detail.html", {
        "auditoria": auditoria,
        "agenda": agenda,
        "perguntas": perguntas_ordenadas,
        "form_nova_pergunta": form_nova_pergunta,
        "itens_norma_todos": itens_norma_todos,
        "itens_alvo": itens_alvo,
        "cobertura_status": cobertura_status,
        "itens_cobertos_ids": itens_cobertos_ids,
        "total_alvo": total_alvo,
        "total_coberto": total_coberto,
        "porcentagem_cobertura": porcentagem_cobertura,
    })

@login_required
@require_POST
def iso_agenda_alvo_update(request, auditoria_id, pk):
    from .models import AgendaAuditoriaIso, AuditoriaIso
    from django.http import JsonResponse
    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    agenda = get_object_or_404(AgendaAuditoriaIso, pk=pk, auditoria=auditoria)
    
    item_ids = request.POST.getlist("itens_alvo")
    agenda.itens_norma.set(item_ids)
    
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"success": True, "message": "Escopo alvo atualizado com sucesso!"})

    messages.success(request, "Itens alvo do escopo planejados com sucesso!")
    return redirect("auditoria:iso_agenda_detail", auditoria_id=auditoria_id, pk=pk)

@login_required
@require_POST
def iso_agenda_pergunta_create(request, auditoria_id, pk):
    from .models import AgendaAuditoriaIso, AuditoriaIso, BancoPergunta
    from django.http import JsonResponse
    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    agenda = get_object_or_404(AgendaAuditoriaIso, pk=pk, auditoria=auditoria)
    
    texto_pergunta = request.POST.get("texto_pergunta")
    dica_resposta = request.POST.get("dica_resposta", "") or request.POST.get("dica_auditor", "")
    item_ids = request.POST.getlist("itens_norma")
    
    if not texto_pergunta:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'O enunciado da pergunta é obrigatório.'}, status=400)
        messages.error(request, "O enunciado da pergunta é obrigatório.")
        return redirect('auditoria:iso_agenda_detail', auditoria_id=auditoria.id, pk=agenda.id)

    nova_pergunta = BancoPergunta.objects.create(
        texto_pergunta=texto_pergunta,
        dica_auditor=dica_resposta
    )
    if item_ids:
        nova_pergunta.itens_norma.set(item_ids)
        
    agenda.perguntas.add(nova_pergunta)
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'pergunta_id': nova_pergunta.id,
            'texto_pergunta': nova_pergunta.texto_pergunta,
            'agenda_id': agenda.id,
            'agenda_titulo': agenda.titulo,
            'total_perguntas': agenda.perguntas.count(),
            'message': f"Pergunta criada com sucesso e vinculada ao bloco '{agenda.titulo}'!"
        })

    messages.success(request, "Pergunta criada e vinculada com sucesso!")
    return redirect('auditoria:iso_agenda_detail', auditoria_id=auditoria.id, pk=agenda.id)

@login_required
def iso_agenda_perguntas_edit(request, auditoria_id, pk):
    from .models import AgendaAuditoriaIso, AuditoriaIso
    from .forms import AgendaPerguntasForm
    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    agenda = get_object_or_404(AgendaAuditoriaIso, pk=pk, auditoria=auditoria)
    
    if request.method == "POST":
        form = AgendaPerguntasForm(request.POST, instance=agenda)
        if form.is_valid():
            form.save()
            messages.success(request, "Perguntas vinculadas com sucesso!")
            return redirect('auditoria:iso_agenda_detail', auditoria_id=auditoria.id, pk=agenda.id)
    else:
        form = AgendaPerguntasForm(instance=agenda)
        
    return render(request, "auditoria/iso/setup/agenda_perguntas_form.html", {
        "form": form, 
        "auditoria": auditoria,
        "agenda": agenda,
        "title": f"Vincular Perguntas: {agenda.titulo}",
        "back_url": reverse('auditoria:iso_agenda_detail', kwargs={'auditoria_id': auditoria.id, 'pk': agenda.id})
    })

@login_required
def iso_auditoria_create(request):
    from .forms import AuditoriaIsoForm
    if request.method == "POST":
        form = AuditoriaIsoForm(request.POST)
        if form.is_valid():
            auditoria = form.save()
            messages.success(request, "Auditoria criada com sucesso! Selecione como deseja estruturar o checklist.")
            return redirect('auditoria:iso_auditoria_detail', pk=auditoria.id)
    else:
        norma_id = request.GET.get('norma')
        initial = {}
        if norma_id:
            initial['norma'] = norma_id
        form = AuditoriaIsoForm(initial=initial)
    return render(request, "auditoria/iso/setup/auditoria_form.html", {"form": form, "title": "Planejar Nova Auditoria", "back_url": reverse('auditoria:iso_setup_dashboard') + "?tab=auditorias"})

@login_required
@require_POST
def iso_auditoria_import_modelo(request, pk):
    """Clona atomicamente todos os blocos, requisitos alvo e perguntas de um ModeloAuditoriaIso para a AuditoriaIso (pk)"""
    from .models import AuditoriaIso, ModeloAuditoriaIso, AgendaAuditoriaIso
    from django.db import transaction
    from django.http import JsonResponse

    auditoria = get_object_or_404(AuditoriaIso, pk=pk)
    modelo_id = request.POST.get("modelo_id")
    
    if not modelo_id:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"success": False, "error": "Modelo de auditoria não selecionado."}, status=400)
        messages.error(request, "Selecione um modelo de auditoria válido.")
        return redirect('auditoria:iso_auditoria_detail', pk=pk)
        
    modelo = get_object_or_404(ModeloAuditoriaIso, pk=modelo_id, norma=auditoria.norma)
    blocos_modelo = modelo.blocos.all().prefetch_related('perguntas', 'itens_norma')
    
    if not blocos_modelo.exists():
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"success": False, "error": "O modelo selecionado não possui blocos/requisitos cadastrados."}, status=400)
        messages.error(request, "O modelo selecionado não possui blocos cadastrados.")
        return redirect('auditoria:iso_auditoria_detail', pk=pk)

    agendas_criadas = []
    with transaction.atomic():
        for b in blocos_modelo:
            nova_agenda = AgendaAuditoriaIso.objects.create(
                auditoria=auditoria,
                modelo_base=modelo,
                titulo=b.titulo
            )
            nova_agenda.perguntas.set(b.perguntas.all())
            nova_agenda.itens_norma.set(b.itens_norma.all())
            agendas_criadas.append(nova_agenda)

    auditoria.status = "PLANEJADA"
    auditoria.save()

    messages.success(request, f"Modelo '{modelo.titulo}' importado com sucesso ({len(agendas_criadas)} blocos duplicados)!")

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "success": True,
            "message": f"Modelo '{modelo.titulo}' importado com sucesso!",
            "total_blocos": len(agendas_criadas),
            "redirect_url": reverse('auditoria:iso_auditoria_detail', args=[pk])
        })

    return redirect('auditoria:iso_auditoria_detail', pk=pk)

@login_required
def iso_auditoria_edit(request, pk):
    from .forms import AuditoriaIsoForm
    auditoria = get_object_or_404(AuditoriaIso, pk=pk)
    if request.method == "POST":
        form = AuditoriaIsoForm(request.POST, instance=auditoria)
        if form.is_valid():
            form.save()
            messages.success(request, "Planejamento de auditoria atualizado!")
            return redirect(reverse('auditoria:iso_setup_dashboard') + "?tab=auditorias")
    else:
        form = AuditoriaIsoForm(instance=auditoria)
    return render(request, "auditoria/iso/setup/auditoria_form.html", {"form": form, "title": f"Editar Auditoria: {auditoria.id}", "back_url": reverse('auditoria:iso_setup_dashboard') + "?tab=auditorias"})

@login_required
@require_POST
def iso_auditoria_delete(request, pk):
    auditoria = get_object_or_404(AuditoriaIso, pk=pk)
    auditoria.delete()
    messages.success(request, "Auditoria cancelada/removida com sucesso!")
    return redirect(reverse('auditoria:iso_setup_dashboard') + "?tab=auditorias")


@login_required
def iso_agenda_sincronizar_modelo(request, auditoria_id, pk):
    """
    Sincroniza a Agenda da Auditoria com o Modelo Base, importando
    perguntas e itens alvos adicionados posteriormente ao Modelo.
    """
    from .models import AgendaAuditoriaIso, BlocoModeloIso, ModeloAuditoriaIso
    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    agenda = get_object_or_404(AgendaAuditoriaIso, pk=pk, auditoria=auditoria)
    
    modelo = agenda.modelo_base
    if not modelo:
        bloco_match = BlocoModeloIso.objects.filter(modelo__norma=auditoria.norma, titulo__iexact=agenda.titulo).first()
        if bloco_match:
            modelo = bloco_match.modelo
            agenda.modelo_base = modelo
            agenda.save()

    if not modelo:
        messages.warning(request, "Esta agenda não possui um Modelo Base associado para sincronizar.")
        return redirect('auditoria:iso_agenda_detail', auditoria_id=auditoria_id, pk=pk)

    bloco_modelo = modelo.blocos.filter(titulo__iexact=agenda.titulo).first()
    
    if bloco_modelo:
        perguntas_modelo = bloco_modelo.perguntas.all()
        itens_modelo = bloco_modelo.itens_norma.all()
    else:
        perguntas_modelo = modelo.perguntas.all()
        itens_modelo = []

    existentes_p_ids = set(agenda.perguntas.values_list('id', flat=True))
    existentes_item_ids = set(agenda.itens_norma.values_list('id', flat=True))

    novas_perguntas = [p for p in perguntas_modelo if p.id not in existentes_p_ids]
    novos_itens = [item for item in itens_modelo if item.id not in existentes_item_ids]

    if novas_perguntas:
        agenda.perguntas.add(*novas_perguntas)
    if novos_itens:
        agenda.itens_norma.add(*novos_itens)

    if novas_perguntas or novos_itens:
        messages.success(
            request, 
            f"Sincronização concluída! {len(novas_perguntas)} nova(s) pergunta(s) e {len(novos_itens)} item(ns) alvo foram incluídos a partir do modelo '{modelo.titulo}'."
        )
    else:
        messages.info(request, f"A agenda já está 100% atualizada e sincronizada com o modelo '{modelo.titulo}'.")

    return redirect('auditoria:iso_agenda_detail', auditoria_id=auditoria_id, pk=pk)
