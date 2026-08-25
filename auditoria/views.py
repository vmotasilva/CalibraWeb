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
import re
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

PONTOS_FORTES_CATALOGO = [
    {
        "titulo": "Domínio dos Processos Produtivos",
        "descricao": "Colaboradores dominam os processos produtivos com segurança técnica, padrão operacional e consistência.",
        "icone": "bi-person-check-fill",
    },
    {
        "titulo": "Transparência e Cooperação",
        "descricao": "Postura transparente, cooperativa e aberta de toda a organização ao longo de todas as avaliações.",
        "icone": "bi-eye-fill",
    },
    {
        "titulo": "Prontidão em Buscar Evidências",
        "descricao": "Agilidade e facilidade no acesso imediato a registros, documentos, amostras e comprovações solicitadas.",
        "icone": "bi-lightning-charge-fill",
    },
    {
        "titulo": "Rastreabilidade dos Produtos",
        "descricao": "Rastreabilidade completa de ponta a ponta — fluxo produtivo, lote de matéria-prima e testes de controle.",
        "icone": "bi-diagram-3-fill",
    },
    {
        "titulo": "Engajamento da Alta Direção e Liderança",
        "descricao": "Comprometimento visível e ativo da gestão com a política da qualidade, recursos e metas estratégicas.",
        "icone": "bi-award-fill",
    },
    {
        "titulo": "Organização, Limpeza e 5S",
        "descricao": "Excelente nível de organização, identificação visual, limpeza e segregação nas áreas produtivas e estoques.",
        "icone": "bi-stars",
    },
    {
        "titulo": "Controle Metrológico Rigoroso",
        "descricao": "Gestão sistemática dos instrumentos com calibração RBC em dia, critérios de aceitação e rastreabilidade.",
        "icone": "bi-speedometer2",
    },
    {
        "titulo": "Competência e Treinamento da Equipe",
        "descricao": "Equipe técnica qualificada, registros de capacitação regulares e matriz de polivalência atualizada.",
        "icone": "bi-mortarboard-fill",
    },
    {
        "titulo": "Cultura de Melhoria Contínua",
        "descricao": "Tratamento ágil de ações corretivas e preventivas com foco na causa raiz e evolução contínua dos processos.",
        "icone": "bi-arrow-repeat",
    },
    {
        "titulo": "Padronização e Controle Documental",
        "descricao": "Procedimentos e instruções de trabalho claros, revisados, disponíveis nos postos e estritamente seguidos.",
        "icone": "bi-file-earmark-check-fill",
    },
    {
        "titulo": "Foco no Cliente e Requisitos Especiais",
        "descricao": "Atenção dedicada aos requisitos de clientes, tratativa de reclamações e conformidade de especificações.",
        "icone": "bi-heart-fill",
    },
    {
        "titulo": "Segurança e Conformidade Regulatória",
        "descricao": "Alinhamento estrito às exigências legais, sanitárias e normativas aplicáveis aos produtos e processos.",
        "icone": "bi-shield-shaded",
    },
]


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
            opcoes_disponiveis = []
            if pergunta.tipo_resposta == "SIM_NAO":
                cor_sim = pergunta.get_cor_resposta("Sim") or "#198754"
                cor_nao = pergunta.get_cor_resposta("Não") or "#dc3545"
                opcoes_disponiveis = [
                    {"label": "Sim", "color": cor_sim},
                    {"label": "Não", "color": cor_nao},
                ]
            elif pergunta.tipo_resposta == "LISTA":
                opcoes_disponiveis = list(getattr(pergunta, "opcoes_resposta_com_cores", []) or [])

            item = {
                "pergunta_id": pergunta.id,
                "ordem": pergunta.ordem,
                "pergunta": pergunta.pergunta,
                "descricao_detalhada": pergunta.descricao_detalhada,
                "obrigatoria": pergunta.obrigatoria,
                "tipo_resposta": pergunta.tipo_resposta,
                "tipo_resposta_display": pergunta.get_tipo_resposta_display(),
                "opcoes_resposta_com_cores": list(getattr(pergunta, "opcoes_resposta_com_cores", []) or []),
                "opcoes_disponiveis": opcoes_disponiveis,
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

        respostas_por_dia = item["respostas_por_dia"]
        has_resposta_dia = any((respostas_por_dia.get(k) or "").strip() for k in dia_keys)
        usa_colunas_dia = has_resposta_dia

        linha = {
            **item,
            "usa_colunas_dia": usa_colunas_dia,
            "dia_values": [respostas_por_dia.get(k, "") for k in dia_keys],
            "dia_cells": [
                {
                    "pergunta_id": item["pergunta_id"],
                    "dia_key": k,
                    "value": respostas_por_dia.get(k, ""),
                    "color": item["respostas_por_dia_cores"].get(k, ""),
                    "label": dia_labels.get(k, k),
                    "short_label": str(dia_labels.get(k, k))[:3].upper(),
                    "tipo_resposta": item["tipo_resposta"],
                    "opcoes_disponiveis": item["opcoes_disponiveis"],
                    "opcoes_json": json.dumps(item["opcoes_disponiveis"]),
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
@require_POST
def api_atualizar_resposta_inline(request, pk):
    """
    API rápida para atualizar o valor de uma resposta diretamente pelo farol (popover)
    sem necessidade de recarregar a tela inteira.
    """
    registro = get_object_or_404(
        _filter_registros_para_usuario(
            request.user,
            RegistroAuditoria.objects.select_related("modelo"),
        ),
        pk=pk,
    )

    pergunta_id_raw = (request.POST.get("pergunta_id") or "").strip()
    dia_semana = (request.POST.get("dia_semana") or "").strip() or None
    grid_item = (request.POST.get("grid_item") or "").strip()
    novo_valor = (request.POST.get("valor") or "").strip()

    if not pergunta_id_raw.isdigit():
        return JsonResponse({"success": False, "error": "Pergunta inválida."}, status=400)

    pergunta = get_object_or_404(
        PerguntaAuditoria,
        id=int(pergunta_id_raw),
        modelo=registro.modelo,
        ativo=True,
    )

    resposta, _created = RespostaAuditoria.objects.update_or_create(
        registro=registro,
        pergunta=pergunta,
        dia_semana=dia_semana,
        grid_item=grid_item,
        defaults={"valor": novo_valor},
    )

    registro.atualizar_progresso()
    cor = _resolve_cor_resposta(pergunta, novo_valor)

    # Recalcular resumo rápido para atualizar contadores/legendas na tela
    resumo = _build_resumo_respostas_registro(registro)

    return JsonResponse({
        "success": True,
        "novo_valor": novo_valor,
        "nova_cor": cor or ("#198754" if novo_valor in ["Sim", "Conforme"] else ("#dc3545" if novo_valor in ["Não", "Não conforme"] else "")),
        "progresso": registro.progresso,
        "percentual_preenchimento": resumo["percentual_preenchimento"],
        "preenchidas": resumo["preenchidas"],
        "total_perguntas": resumo["total_perguntas"],
        "blocos_resumo": [
            {
                "nome": b["nome"],
                "tem_lista_resumo": b.get("tem_lista_resumo", False),
                "lista_resumo": b.get("lista_resumo", []),
                "lista_total_respostas": b.get("lista_total_respostas", 0),
            }
            for b in resumo["blocos"]
        ],
    })


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

from .models import AuditoriaIso, RespostaEntrevistaIso, BancoPergunta, SolicitacaoEvidenciaIso, ItemNorma, AgendaAuditoriaIso, BlocoModeloIso, ModeloAuditoriaIso

def consolidar_solicitacoes_perguntas(auditoria=None):
    """
    Garante que todas as solicitações de evidência estejam vinculadas
    à pergunta ativa canônica de seus respectivos itens da norma.
    Se uma pergunta foi desativada ou se existem perguntas duplicadas
    para o mesmo item, migra automaticamente as solicitações e respostas
    para a pergunta ativa canônica do item, preservando o histórico integral.
    Também remove perguntas inativas de agendas, blocos e modelos.
    """
    try:
        # 1. Recuperar respostas de perguntas inativas e desvinculá-las de agendas/blocos
        inativas = list(BancoPergunta.objects.filter(ativa=False))
        inativas_ids = [p.id for p in inativas]
        
        if inativas_ids:
            # Desvincula de todas as agendas, blocos e modelos
            for ag in AgendaAuditoriaIso.objects.filter(perguntas__in=inativas_ids):
                ag.perguntas.remove(*inativas_ids)
            for bl in BlocoModeloIso.objects.filter(perguntas__in=inativas_ids):
                bl.perguntas.remove(*inativas_ids)
            for mo in ModeloAuditoriaIso.objects.filter(perguntas__in=inativas_ids):
                mo.perguntas.remove(*inativas_ids)

        for p_inativa in inativas:
            resps = RespostaEntrevistaIso.objects.filter(pergunta=p_inativa)
            if not resps.exists():
                continue
            
            p_ativa = BancoPergunta.objects.filter(ativa=True, texto_pergunta__iexact=p_inativa.texto_pergunta).first()
            if not p_ativa and p_inativa.itens_norma.exists():
                p_ativa = BancoPergunta.objects.filter(ativa=True, itens_norma__in=p_inativa.itens_norma.all()).first()
            if not p_ativa:
                p_ativa = BancoPergunta.objects.filter(ativa=True).order_by('id').first()
                
            if p_ativa and p_ativa.id != p_inativa.id:
                for resp in resps:
                    resp_ativa, _ = RespostaEntrevistaIso.objects.get_or_create(
                        auditoria=resp.auditoria,
                        pergunta=p_ativa,
                        defaults={'respondida_por': resp.respondida_por}
                    )
                    SolicitacaoEvidenciaIso.objects.filter(resposta=resp).update(resposta=resp_ativa)
                    if resp.texto_resposta and not resp_ativa.texto_resposta:
                        resp_ativa.texto_resposta = resp.texto_resposta
                        resp_ativa.save(update_fields=['texto_resposta'])
                    resp.delete()

        # 2. Para cada ItemNorma com mais de uma pergunta vinculada, consolida na pergunta canônica
        for item in ItemNorma.objects.prefetch_related('perguntas_vinculadas').all():
            perguntas_item = list(item.perguntas_vinculadas.filter(ativa=True).order_by('id'))
            if len(perguntas_item) > 1:
                p_canon = perguntas_item[0]
                for p_dup in perguntas_item[1:]:
                    for resp_dup in RespostaEntrevistaIso.objects.filter(pergunta=p_dup):
                        resp_canon, _ = RespostaEntrevistaIso.objects.get_or_create(
                            auditoria=resp_dup.auditoria,
                            pergunta=p_canon,
                            defaults={'respondida_por': resp_dup.respondida_por}
                        )
                        SolicitacaoEvidenciaIso.objects.filter(resposta=resp_dup).update(resposta=resp_canon)
                        if resp_dup.texto_resposta and not resp_canon.texto_resposta:
                            resp_canon.texto_resposta = resp_dup.texto_resposta
                            resp_canon.save(update_fields=['texto_resposta'])
                        resp_dup.delete()
    except Exception:
        pass

@login_required
def iso_auditoria_list(request):
    auditorias = AuditoriaIso.objects.all().order_by("-data_inicio")
    return render(request, "auditoria/iso_auditoria_list.html", {"auditorias": auditorias})

@login_required
def iso_entrevista_view(request, auditoria_id):
    consolidar_solicitacoes_perguntas()
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

    # Desduplicação Automática no Bloco: cada item é avaliado apenas 1 vez neste bloco
    itens_vistos_entrevista = set()
    perguntas_lista = []
    for p in sorted(list(perguntas), key=get_pergunta_sort_key):
        item_ids_p = set(p.itens_norma.values_list('id', flat=True))
        if item_ids_p and item_ids_p.issubset(itens_vistos_entrevista):
            continue
        itens_vistos_entrevista.update(item_ids_p)
        perguntas_lista.append(p)
    
    # Garante a existência e atualização da pergunta padrão de Identificação dos Auditados (Nome e Função)
    texto_pergunta_auditados = f"Quais são os nomes e funções das pessoas auditadas / entrevistadas neste bloco ({agenda.titulo})?"
    pergunta_auditados, _ = BancoPergunta.objects.get_or_create(
        texto_pergunta=texto_pergunta_auditados,
        defaults={
            "dica_auditor": "Registre o nome completo e a função / cargo de cada participante entrevistado nesta etapa da auditoria.",
            "ativa": True
        }
    )

    # Prepend a pergunta de auditados na PRIMEIRA POSIÇÃO da entrevista
    perguntas_lista = [p for p in perguntas_lista if p.id != pergunta_auditados.id]
    perguntas_lista.insert(0, pergunta_auditados)
    
    # Pré-carrega todas as agendas da auditoria para mapeamento de blocos de origem
    agendas_auditoria = list(
        auditoria.agendas.filter(arquivada=False).prefetch_related('itens_norma', 'perguntas')
    )
    pergunta_to_agendas_map = {}
    for ag in agendas_auditoria:
        for pag in ag.perguntas.all():
            if pag.id not in pergunta_to_agendas_map:
                pergunta_to_agendas_map[pag.id] = []
            pergunta_to_agendas_map[pag.id].append({
                'id': ag.id,
                'titulo': ag.titulo
            })

    # Obter respostas já existentes e auto-migrar anotações antigas para Solicitações se necessário
    respostas = RespostaEntrevistaIso.objects.filter(auditoria=auditoria).prefetch_related('solicitacoes', 'solicitacoes__imagens', 'pergunta__itens_norma')
    from .models import SolicitacaoEvidenciaIso
    respostas_dict = {}
    solicitacoes_por_item = {}

    for r in respostas:
        sols_qs = list(r.solicitacoes.all())
        # Se existem anotações no texto_resposta livre mas nenhuma solicitação foi cadastrada ainda,
        # converte automaticamente as anotações legadas na primeira Solicitação de Evidência
        if not sols_qs and r.texto_resposta and r.texto_resposta.strip():
            nova_sol = SolicitacaoEvidenciaIso.objects.create(
                resposta=r,
                solicitacao="Evidências / Documentos Registrados",
                evidencia=r.texto_resposta.strip(),
                conclusao=r.classificacao if r.classificacao in ['C', 'NC', 'OM', 'NA'] else 'P'
            )
            sols_qs.append(nova_sol)

        sols = []
        for s in sols_qs:
            if s.agenda:
                bloco_nome_s = s.agenda.titulo
                is_bloco_atual_s = (str(s.agenda_id) == str(agenda_id)) if agenda_id else True
            else:
                ag_list = pergunta_to_agendas_map.get(r.pergunta_id, [])
                if agenda_id:
                    tem_atual = any(str(ag['id']) == str(agenda_id) for ag in ag_list)
                    bloco_nome_s = agenda.titulo if tem_atual else (ag_list[0]['titulo'] if ag_list else "Geral")
                    is_bloco_atual_s = tem_atual
                else:
                    bloco_nome_s = ", ".join(ag['titulo'] for ag in ag_list) if ag_list else "Geral"
                    is_bloco_atual_s = True

            imgs_s = [
                {
                    "id": img.id,
                    "url": img.url_imagem,
                    "legenda": img.legenda,
                    "nome": img.nome_arquivo,
                    "criado_em": img.criado_em.strftime("%d/%m/%Y %H:%M")
                }
                for img in s.imagens.all()
            ]

            sols.append({
                "id": s.id,
                "solicitacao": s.solicitacao,
                "evidencia": s.evidencia,
                "conclusao": s.conclusao,
                "grau_nc": s.grau_nc,
                "pergunta_id": r.pergunta_id,
                "bloco_nome": bloco_nome_s,
                "is_bloco_atual": is_bloco_atual_s,
                "imagens": imgs_s
            })

        respostas_dict[r.pergunta_id] = {
            "classificacao": r.classificacao,
            "grau_nc": r.grau_nc,
            "texto_resposta": r.texto_resposta,
            "solicitacoes": sols
        }

        # Indexa as solicitações por cada item da norma vinculado à pergunta
        for it in r.pergunta.itens_norma.all():
            if it.id not in solicitacoes_por_item:
                solicitacoes_por_item[it.id] = []
            for s in sols:
                if not any(exist['id'] == s['id'] for exist in solicitacoes_por_item[it.id]):
                    solicitacoes_por_item[it.id].append(s)
        
    # Otimização de Performance: pré-indexação em memória das outras agendas e requisitos
    agendas_outras_todas = list(
        auditoria.agendas.filter(arquivada=False).prefetch_related('itens_norma', 'perguntas__itens_norma')
    )

    # Mapeamento rápido: item_id -> lista de dicts de agendas
    item_to_agendas = {}
    agendas_para_transfer = []
    
    for ag in agendas_outras_todas:
        perguntas_ag = []
        ag_item_ids = set(ag.itens_norma.values_list('id', flat=True))
        
        for pag in ag.perguntas.all():
            pag_item_ids = list(pag.itens_norma.values_list('id', flat=True))
            ag_item_ids.update(pag_item_ids)
            itens_sorted = sorted(pag.itens_norma.all(), key=lambda it: natural_sort_key(it.referencia))
            itens_str = ", ".join(it.referencia for it in itens_sorted)
            perguntas_ag.append({
                "id": pag.id,
                "texto_curto": pag.texto_pergunta[:80] + ("..." if len(pag.texto_pergunta) > 80 else ""),
                "itens": itens_str or "—",
                "primeira_ref": itens_sorted[0].referencia if itens_sorted else "999"
            })

        # Ordena as perguntas do bloco pelo código/item da norma (ex: 6.2 antes de 7.4.1, 7.4.1 antes de 7.4.10)
        perguntas_ag.sort(key=lambda p: (natural_sort_key(p['primeira_ref']), p['texto_curto']))

        agendas_para_transfer.append({
            "id": ag.id,
            "titulo": ag.titulo,
            "perguntas": perguntas_ag
        })

        if not agenda_id or str(ag.id) != str(agenda_id):
            for i_id in ag_item_ids:
                if i_id not in item_to_agendas:
                    item_to_agendas[i_id] = []
                item_to_agendas[i_id].append({
                    'agenda_id': ag.id,
                    'titulo': ag.titulo,
                    'total_perguntas': len(perguntas_ag)
                })

    perguntas_data = []
    for p in perguntas_lista:
        r = respostas_dict.get(p.id, {})
        itens_p = list(p.itens_norma.all())
        
        # Consolida todas as solicitações dos itens da norma avaliados nesta pergunta
        sols_consolidadas = []
        sols_ids_vistos = set()

        # 1. Solicitações diretas da pergunta atual
        for s in r.get("solicitacoes", []):
            if s["id"] not in sols_ids_vistos:
                sols_ids_vistos.add(s["id"])
                sols_consolidadas.append(s)

        # 2. Solicitações de outros blocos/perguntas vinculadas aos mesmos itens da norma
        for item in itens_p:
            for s in solicitacoes_por_item.get(item.id, []):
                if s["id"] not in sols_ids_vistos:
                    sols_ids_vistos.add(s["id"])
                    sols_consolidadas.append(s)
        
        # Agrupa outros blocos rapidamente
        blocos_vistos = {}
        for item in itens_p:
            for ag_info in item_to_agendas.get(item.id, []):
                b_id = ag_info['agenda_id']
                if b_id not in blocos_vistos:
                    blocos_vistos[b_id] = {
                        'agenda_id': b_id,
                        'titulo': ag_info['titulo'],
                        'itens_comum': [],
                        'total_perguntas': ag_info['total_perguntas']
                    }
                if item.referencia not in blocos_vistos[b_id]['itens_comum']:
                    blocos_vistos[b_id]['itens_comum'].append(item.referencia)

        itens_str = ", ".join([item.referencia for item in itens_p])
        if p.id == pergunta_auditados.id and not itens_str:
            itens_str = "Identificação / Auditados"

        # Calcula status dinâmico a partir das solicitações consolidadas do item
        if sols_consolidadas:
            conclusoes = [s["conclusao"] for s in sols_consolidadas]
            if "NC" in conclusoes:
                classificacao_final = "NC"
            elif "OM" in conclusoes:
                classificacao_final = "OM"
            elif any(c in ["C", "OBS"] for c in conclusoes):
                classificacao_final = "C"
            elif all(c == "NA" for c in conclusoes):
                classificacao_final = "NA"
            else:
                classificacao_final = "P"
        else:
            raw_c = r.get("classificacao", "P")
            classificacao_final = "C" if raw_c == "OBS" else raw_c

        perguntas_data.append({
            "id": p.id,
            "texto_pergunta": p.texto_pergunta,
            "dica_auditor": p.dica_auditor or "",
            "itens": itens_str,
            "itens_objects": [
                {
                    "id": item.id,
                    "ref": item.referencia,
                    "titulo": item.titulo,
                    "descricao": item.descricao or "",
                    "evidencia_padrao": item.evidencia_padrao or ""
                }
                for item in itens_p
            ],
            "outros_blocos": list(blocos_vistos.values()),
            "classificacao": classificacao_final,
            "grau_nc": r.get("grau_nc"),
            "texto_resposta": r.get("texto_resposta", ""),
            "solicitacoes": sols_consolidadas
        })

    # Itens de Atalho Especial da Norma para Acesso Rápido Global
    itens_atalho_qs = ItemNorma.objects.filter(norma=auditoria.norma, atalho_especial=True).order_by('ordem', 'referencia')
    itens_atalho_data = [
        {
            "id": it.id,
            "referencia": it.referencia,
            "titulo": it.titulo,
            "descricao": it.descricao or "",
            "evidencia_padrao": it.evidencia_padrao or "",
            "pergunta_padrao": it.pergunta_padrao or ""
        }
        for it in itens_atalho_qs
    ]

    context = {
        "auditoria": auditoria,
        "agenda": agenda if agenda_id else None,
        "perguntas_json": json.dumps(perguntas_data),
        "agendas_json": json.dumps(agendas_para_transfer),
        "itens_atalho_json": json.dumps(itens_atalho_data)
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
        grau_nc = data.get("grau_nc") if classificacao == "NC" else None
        
        auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
        pergunta = get_object_or_404(BancoPergunta, pk=pergunta_id)
        
        resposta, created = RespostaEntrevistaIso.objects.update_or_create(
            auditoria=auditoria,
            pergunta=pergunta,
            defaults={
                "texto_resposta": texto_resposta,
                "classificacao": classificacao,
                "grau_nc": grau_nc,
                "respondida_por": request.user
            }
        )
        return JsonResponse({"status": "success", "resposta_id": resposta.id})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)

@login_required
@require_POST
def api_iso_solicitacao_create(request):
    from .models import SolicitacaoEvidenciaIso, RespostaEntrevistaIso, AuditoriaIso, BancoPergunta, AgendaAuditoriaIso
    try:
        data = json.loads(request.body)
        auditoria_id = data.get("auditoria_id")
        pergunta_id = data.get("pergunta_id")
        agenda_id = data.get("agenda_id")
        solicitacao_texto = data.get("solicitacao", "Nova Solicitação de Evidência").strip()
        evidencia_texto = data.get("evidencia", "").strip()
        conclusao = data.get("conclusao", "P")
        grau_nc = data.get("grau_nc") if conclusao == "NC" else None

        auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
        pergunta = get_object_or_404(BancoPergunta, pk=pergunta_id)
        agenda = AgendaAuditoriaIso.objects.filter(pk=agenda_id, auditoria=auditoria).first() if agenda_id else None

        resposta, _ = RespostaEntrevistaIso.objects.get_or_create(
            auditoria=auditoria,
            pergunta=pergunta,
            defaults={"respondida_por": request.user}
        )

        nova_sol = SolicitacaoEvidenciaIso.objects.create(
            resposta=resposta,
            agenda=agenda,
            solicitacao=solicitacao_texto,
            evidencia=evidencia_texto,
            conclusao=conclusao,
            grau_nc=grau_nc
        )

        return JsonResponse({
            "success": True,
            "solicitacao": {
                "id": nova_sol.id,
                "solicitacao": nova_sol.solicitacao,
                "evidencia": nova_sol.evidencia,
                "conclusao": nova_sol.conclusao,
                "grau_nc": nova_sol.grau_nc,
                "bloco_nome": agenda.titulo if agenda else "Geral",
                "is_bloco_atual": True,
                "imagens": []
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
        if "grau_nc" in data:
            sol.grau_nc = data["grau_nc"] if sol.conclusao == "NC" else None

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
def api_iso_solicitacao_upload_imagem(request, pk):
    """
    Upload de fotos e imagens vinculadas a uma Solicitação de Evidência.
    Processa arquivos normais (multipart/form-data) ou payloads base64,
    gerando backup persistente no banco PostgreSQL para resiliência serverless.
    """
    import base64
    from .models import SolicitacaoEvidenciaIso, ImagemSolicitacaoIso
    try:
        sol = get_object_or_404(SolicitacaoEvidenciaIso, pk=pk)
        legenda = request.POST.get("legenda", "").strip()
        nome_arquivo = ""
        arquivo_base64 = ""
        uploaded_file = request.FILES.get("imagem") or request.FILES.get("arquivo") or request.FILES.get("file")

        if uploaded_file:
            nome_arquivo = uploaded_file.name
            file_bytes = uploaded_file.read()
            uploaded_file.seek(0)
            content_type = getattr(uploaded_file, 'content_type', 'image/jpeg') or 'image/jpeg'
            b64_str = base64.b64encode(file_bytes).decode('utf-8')
            arquivo_base64 = f"data:{content_type};base64,{b64_str}"

            try:
                img_obj = ImagemSolicitacaoIso.objects.create(
                    solicitacao=sol,
                    arquivo=uploaded_file,
                    arquivo_base64=arquivo_base64,
                    nome_arquivo=nome_arquivo,
                    legenda=legenda,
                )
            except OSError:
                img_obj = ImagemSolicitacaoIso.objects.create(
                    solicitacao=sol,
                    arquivo=None,
                    arquivo_base64=arquivo_base64,
                    nome_arquivo=nome_arquivo,
                    legenda=legenda,
                )
        else:
            try:
                data = json.loads(request.body)
                arquivo_base64 = data.get("base64", "").strip()
                nome_arquivo = data.get("nome", "evidencia.jpg").strip()
                legenda = data.get("legenda", "").strip()
            except Exception:
                arquivo_base64 = request.POST.get("base64", "").strip()
                nome_arquivo = request.POST.get("nome", "evidencia.jpg").strip()

            if not arquivo_base64:
                return JsonResponse({"success": False, "error": "Nenhuma imagem informada."}, status=400)

            img_obj = ImagemSolicitacaoIso.objects.create(
                solicitacao=sol,
                arquivo_base64=arquivo_base64,
                nome_arquivo=nome_arquivo,
                legenda=legenda,
            )

        return JsonResponse({
            "success": True,
            "imagem": {
                "id": img_obj.id,
                "url": img_obj.url_imagem,
                "legenda": img_obj.legenda,
                "nome": img_obj.nome_arquivo,
                "criado_em": img_obj.criado_em.strftime("%d/%m/%Y %H:%M")
            }
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
@require_POST
def api_iso_solicitacao_delete_imagem(request, pk):
    """Exclui uma imagem de evidência."""
    from .models import ImagemSolicitacaoIso
    try:
        img_obj = get_object_or_404(ImagemSolicitacaoIso, pk=pk)
        if img_obj.arquivo:
            try:
                img_obj.arquivo.delete(save=False)
            except Exception:
                pass
        img_obj.delete()
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
@require_POST
def api_iso_solicitacao_update_legenda_imagem(request, pk):
    """Atualiza a legenda descritiva de uma imagem."""
    from .models import ImagemSolicitacaoIso
    try:
        img_obj = get_object_or_404(ImagemSolicitacaoIso, pk=pk)
        data = json.loads(request.body)
        img_obj.legenda = data.get("legenda", "").strip()
        img_obj.save()
        return JsonResponse({"success": True, "legenda": img_obj.legenda})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
@require_POST
def api_iso_solicitacao_transferir(request, pk):
    """Transfere uma solicitação de evidência para outra pergunta/bloco."""
    from .models import SolicitacaoEvidenciaIso, RespostaEntrevistaIso, AuditoriaIso, BancoPergunta, AgendaAuditoriaIso
    try:
        sol = get_object_or_404(SolicitacaoEvidenciaIso, pk=pk)
        data = json.loads(request.body)
        auditoria_id = data.get("auditoria_id")
        pergunta_destino_id = data.get("pergunta_destino_id")
        agenda_destino_id = data.get("agenda_id") or data.get("bloco_id")

        if not auditoria_id or not pergunta_destino_id:
            return JsonResponse({"success": False, "error": "Parâmetros insuficientes."}, status=400)

        auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
        pergunta_destino = get_object_or_404(BancoPergunta, pk=pergunta_destino_id)

        # Cria ou obtém a resposta de destino
        resposta_destino, _ = RespostaEntrevistaIso.objects.get_or_create(
            auditoria=auditoria,
            pergunta=pergunta_destino,
            defaults={"respondida_por": request.user}
        )

        # Atualiza a agenda de destino se informada
        if agenda_destino_id:
            agenda_dest = AgendaAuditoriaIso.objects.filter(pk=agenda_destino_id, auditoria=auditoria).first()
            if agenda_dest:
                sol.agenda = agenda_dest

        # Move a solicitação para a nova resposta
        sol.resposta = resposta_destino
        sol.save()

        bloco_nome = sol.agenda.titulo if sol.agenda else "Geral"

        return JsonResponse({
            "success": True,
            "message": f"Solicitação transferida com sucesso para o bloco '{bloco_nome}'!",
            "bloco_nome": bloco_nome
        })
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
    consolidar_solicitacoes_perguntas()
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
    respostas = RespostaEntrevistaIso.objects.filter(auditoria=auditoria).prefetch_related('solicitacoes', 'solicitacoes__imagens')
    respostas_map = {r.pergunta_id: r for r in respostas}
    
    # Mapeamento rápido de agendas por item da norma (usando .all() para aproveitar o prefetch)
    agenda_item_ids_map = {agenda.id: set(item.id for item in agenda.itens_norma.all()) for agenda in agendas}
    
    # Pre-calcular os itens de norma de cada pergunta para evitar queries no loop triplo
    pergunta_item_ids_map = {}
    for agenda in agendas:
        for p in agenda.perguntas.all():
            if p.id not in pergunta_item_ids_map:
                pergunta_item_ids_map[p.id] = set(item.id for item in p.itens_norma.all())
                
    # Mapeia itens explicitamente marcados como N/A na auditoria
    na_item_ids = set(auditoria.itens_nao_aplicaveis.values_list('id', flat=True))

    hierarchy = {"NC": 5, "P": 4, "OM": 3, "C": 2, "NA": 1}
    reverse_hierarchy = {v: k for k, v in hierarchy.items()}
    
    matriz_data = []
    
    for item in sorted(itens_escopo_list, key=lambda x: (x.ordem or 0, natural_sort_key(x.referencia))):
        is_parent = item.id in parent_ids
        
        # Encontra todos os blocos (agendas) e perguntas associadas a este item
        blocos_associados = []
        blocos_vistos_item = set()
        todas_perguntas_item_set = set()
        
        for agenda in agendas:
            if agenda.id in blocos_vistos_item:
                continue

            ag_item_ids = agenda_item_ids_map[agenda.id]
            
            # Perguntas vinculadas diretamente a este item neste bloco
            perguntas_bloco_item = []
            perguntas_vistas_bloco = set()
            for p in agenda.perguntas.all():
                if p.id in perguntas_vistas_bloco:
                    continue
                p_item_ids = pergunta_item_ids_map[p.id]
                
                # Se a pergunta tem vinculo explicito com este item OU se a pergunta nao tem vinculo e a agenda tem vinculo com este item
                if item.id in p_item_ids or (not p_item_ids and item.id in ag_item_ids):
                    perguntas_vistas_bloco.add(p.id)
                    perguntas_bloco_item.append(p)
                    todas_perguntas_item_set.add(p.id)
                    
            if perguntas_bloco_item or (item.id in ag_item_ids):
                blocos_vistos_item.add(agenda.id)
                perguntas_info = []
                for p in perguntas_bloco_item:
                    resp = respostas_map.get(p.id)
                    sols_list = []
                    if resp:
                        for s in resp.solicitacoes.all():
                            # Se a solicitação pertence especificamente a outra agenda, não a duplica neste bloco
                            if s.agenda_id and s.agenda_id != agenda.id:
                                continue
                            sols_list.append({
                                'id': s.id,
                                'solicitacao': s.solicitacao,
                                'evidencia': s.evidencia or '',
                                'conclusao': s.conclusao,
                                'conclusao_display': s.get_conclusao_display(),
                                'bloco_origem': s.agenda.titulo if s.agenda else agenda.titulo,
                                'imagens': [
                                    {
                                        'id': img.id,
                                        'url': img.url_imagem,
                                        'legenda': img.legenda,
                                        'nome': img.nome_arquivo,
                                        'criado_em': img.criado_em.strftime("%d/%m/%Y %H:%M")
                                    }
                                    for img in s.imagens.all()
                                ]
                            })

                    class_calc = resp.classificacao if resp else 'P'
                    class_display = resp.get_classificacao_display() if resp else 'Pendente'
                    if sols_list:
                        conclusoes = [s['conclusao'] for s in sols_list]
                        if "NC" in conclusoes:
                            class_calc = "NC"
                            class_display = "Não Conforme"
                        elif "OM" in conclusoes:
                            class_calc = "OM"
                            class_display = "Oportunidade de Melhoria"
                        elif "C" in conclusoes:
                            class_calc = "C"
                            class_display = "Conforme"

                    perguntas_info.append({
                        'id': p.id,
                        'texto_pergunta': p.texto_pergunta,
                        'dica_auditor': p.dica_auditor or '',
                        'classificacao': class_calc,
                        'classificacao_display': class_display,
                        'texto_resposta': resp.texto_resposta if (resp and resp.texto_resposta) else '',
                        'solicitacoes': sols_list
                    })
                    
                blocos_associados.append({
                    'bloco_id': agenda.id,
                    'bloco_titulo': agenda.titulo,
                    'total_perguntas': len(perguntas_info),
                    'perguntas': perguntas_info
                })
        
        # Coleta todas as solicitações de evidência de todas as perguntas que cobrem este item
        sols_do_item = []
        for p_id in todas_perguntas_item_set:
            r = respostas_map.get(p_id)
            if r:
                for s in r.solicitacoes.all():
                    sols_do_item.append(s)

        # Status Calculado baseado estritamente nas solicitações de evidência do item
        if is_parent:
            status_item = ""
        elif item.id in na_item_ids:
            status_item = "NA"
        elif sols_do_item:
            conclusoes = [s.conclusao for s in sols_do_item]
            if "NC" in conclusoes:
                status_item = "NC"
            elif "OM" in conclusoes:
                status_item = "OM"
            elif any(c in ["C", "OBS"] for c in conclusoes):
                # Se houver amostras C ou OBS (sem NC/OM), o item está Conforme
                if all(c == "P" for c in conclusoes):
                    status_item = "P"
                else:
                    status_item = "C"
            elif all(c == "NA" for c in conclusoes):
                status_item = "NA"
            else:
                status_item = "P"
        else:
            # Sem solicitações registradas para o item
            status_item = "P" if blocos_associados else "NA"
            
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

    # Calcula as métricas e estatísticas do relatório (desconsiderando N/A e OBS)
    count_c = sum(1 for m in matriz_data if not m["is_parent"] and m["status"] == "C")
    count_obs = 0
    count_nc = sum(1 for m in matriz_data if not m["is_parent"] and m["status"] == "NC")
    count_om = sum(1 for m in matriz_data if not m["is_parent"] and m["status"] == "OM")
    count_p = sum(1 for m in matriz_data if not m["is_parent"] and m["status"] == "P")
    count_na = sum(1 for m in matriz_data if not m["is_parent"] and m["status"] == "NA")

    # Contabilizar apenas C, NC e OM (OBS, NA e P excluídos do percentual)
    total_avaliados = count_c + count_nc + count_om + count_p
    total_percentual_base = count_c + count_nc + count_om

    pct_c = round((count_c / total_percentual_base * 100), 1) if total_percentual_base > 0 else 0
    pct_nc = round((count_nc / total_percentual_base * 100), 1) if total_percentual_base > 0 else 0
    pct_om = round((count_om / total_percentual_base * 100), 1) if total_percentual_base > 0 else 0
    pct_obs = 0
    pct_p = round((count_p / total_avaliados * 100), 1) if total_avaliados > 0 else 0

    stats = {
        "count_c": count_c,
        "count_obs": count_obs,
        "count_nc": count_nc,
        "count_om": count_om,
        "count_p": count_p,
        "count_na": count_na,
        "total_avaliados": total_avaliados,
        "pct_c": pct_c,
        "pct_obs": pct_obs,
        "pct_nc": pct_nc,
        "pct_om": pct_om,
        "pct_p": pct_p,
    }
        
    # Monta lista de agendas e perguntas para modal de transferência
    agendas_para_transfer = []
    for ag in auditoria.agendas.filter(arquivada=False).prefetch_related('perguntas', 'perguntas__itens_norma'):
        perguntas_ag = []
        for pag in ag.perguntas.all():
            itens_sorted = sorted(pag.itens_norma.all(), key=lambda it: natural_sort_key(it.referencia))
            itens_str = ", ".join(it.referencia for it in itens_sorted)
            perguntas_ag.append({
                "id": pag.id,
                "texto_curto": pag.texto_pergunta[:80] + ("..." if len(pag.texto_pergunta) > 80 else ""),
                "itens": itens_str or "—",
                "primeira_ref": itens_sorted[0].referencia if itens_sorted else "999"
            })
        
        perguntas_ag.sort(key=lambda p: (natural_sort_key(p['primeira_ref']), p['texto_curto']))

        agendas_para_transfer.append({
            "id": ag.id,
            "titulo": ag.titulo,
            "perguntas": perguntas_ag
        })

    context = {
        "auditoria": auditoria,
        "matriz_data": matriz_data,
        "stats": stats,
        "agendas_json": json.dumps(agendas_para_transfer)
    }
    return render(request, "auditoria/iso_matriz.html", context)


def chunks_list(lst, n):
    """Divide uma lista em pedaços de tamanho n para evitar overflow em slides"""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


@login_required
def iso_fechamento_presentation_view(request, auditoria_id):
    """
    MOTOR DE ENCERRAMENTO & APRESENTAÇÃO EXECUTIVA (16:9 SLIDE DECK)
    Calcula as métricas da auditoria, roda o Motor de Decisão (Fail-Fast)
    e gera a apresentação em formato de slides corporativos.
    """
    from .models import AuditoriaIso, RespostaEntrevistaIso, ItemNorma
    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    agendas = list(auditoria.agendas.all().prefetch_related('perguntas', 'itens_norma', 'perguntas__itens_norma'))

    # Coleta de Itens do Escopo
    itens_escopo = auditoria.escopo_itens.all()
    if not itens_escopo.exists():
        itens_escopo = ItemNorma.objects.filter(norma=auditoria.norma)
    itens_escopo_list = list(itens_escopo)

    # Itens Pais (que possuem filhos)
    parent_ids = set()
    for item in itens_escopo_list:
        prefix = item.referencia + '.'
        if any(other.referencia.startswith(prefix) for other in itens_escopo_list):
            parent_ids.add(item.id)

    respostas = RespostaEntrevistaIso.objects.filter(auditoria=auditoria).prefetch_related('solicitacoes', 'pergunta__itens_norma')
    respostas_map = {r.pergunta_id: r for r in respostas}
    na_item_ids = set(auditoria.itens_nao_aplicaveis.values_list('id', flat=True))

    from .models import AvaliacaoFinalRequisitoIso
    avaliacoes_finais_map = {
        av.item_norma_id: av
        for av in AvaliacaoFinalRequisitoIso.objects.filter(auditoria=auditoria)
    }

    hierarchy = {"NC": 5, "P": 4, "OM": 3, "C": 2, "NA": 1}
    reverse_hierarchy = {v: k for k, v in hierarchy.items()}

    destaques_conformes = []
    pontos_a_melhorar = []
    conselhos_por_item = []
    conselhos_map = {}
    
    count_c = 0
    count_obs = 0
    count_om = 0
    count_nc_menor = 0
    count_nc_maior = 0
    count_p = 0
    count_na = 0

    for item in sorted(itens_escopo_list, key=lambda x: (x.ordem or 0, natural_sort_key(x.referencia))):
        if item.id in parent_ids:
            continue  # Apenas folhas

        todas_perguntas_dict = {}
        for ag in agendas:
            for p in ag.perguntas.all():
                if item in p.itens_norma.all() or (not p.itens_norma.exists() and item in ag.itens_norma.all()):
                    todas_perguntas_dict[p.id] = p
                    
        # Garante que respostas/perguntas órfãs (ex: criadas via painel de revisão) sejam incluídas
        for r in respostas:
            if item in r.pergunta.itens_norma.all():
                todas_perguntas_dict[r.pergunta_id] = r.pergunta
                
        todas_perguntas_item = list(todas_perguntas_dict.values())

        av_final = avaliacoes_finais_map.get(item.id)

        if av_final:
            status_item = av_final.classificacao
        elif item.id in na_item_ids:
            status_item = "NA"
        elif not todas_perguntas_item:
            status_item = "P" if any(item in ag.itens_norma.all() for ag in agendas) else "NA"
        else:
            pior_peso = 0
            for p in todas_perguntas_item:
                r = respostas_map.get(p.id)
                c = r.classificacao if r else "P"
                if c == "OBS":
                    c = "C"  # OBS não afeta o status do item
                peso = hierarchy.get(c, 2)
                if peso > pior_peso:
                    pior_peso = peso
            status_item = reverse_hierarchy.get(pior_peso, "P")

        # 1. Fallback/Override global: garante que NCs ou OMs transferidos sejam refletidos no status global do item
        has_dangling_nc = False
        has_dangling_om = False
        for p in todas_perguntas_item:
            r = respostas_map.get(p.id)
            if r:
                for s in r.solicitacoes.all():
                    if s.conclusao == 'NC':
                        has_dangling_nc = True
                    elif s.conclusao == 'OM':
                        has_dangling_om = True
        
        if has_dangling_nc:
            status_item = 'NC'
        elif has_dangling_om and status_item != 'NC':
            status_item = 'OM'

        # 2. Coleta evidências globais para definir grau_nc e destaques
        evidencias_globais = []
        evidencias_globais_vistas = set()
        for p in todas_perguntas_item:
            r = respostas_map.get(p.id)
            if r:
                for s in r.solicitacoes.all():
                    if s.conclusao == 'OBS':
                        count_obs += 1
                        obs_txt = f"{s.solicitacao.strip()}: {s.evidencia.strip()}" if (s.evidencia and s.solicitacao) else (s.evidencia.strip() if s.evidencia else s.solicitacao.strip())
                        if obs_txt:
                            if item.referencia not in conselhos_map:
                                conselhos_map[item.referencia] = {
                                    'referencia': item.referencia,
                                    'titulo': item.titulo,
                                    'conselhos': []
                                }
                                conselhos_por_item.append(conselhos_map[item.referencia])
                            conselhos_map[item.referencia]['conselhos'].append(obs_txt)

                    ev_txt = f"{s.solicitacao.strip()}: {s.evidencia.strip()}" if (s.evidencia and s.solicitacao) else (s.evidencia.strip() if s.evidencia else s.solicitacao.strip())
                    if ev_txt and ev_txt not in evidencias_globais_vistas:
                        evidencias_globais_vistas.add(ev_txt)
                        evidencias_globais.append(ev_txt)
                
                if r.texto_resposta and r.texto_resposta.strip():
                    txt = r.texto_resposta.strip()
                    if txt not in evidencias_globais_vistas:
                        evidencias_globais_vistas.add(txt)
                        evidencias_globais.append(txt)

        if av_final and av_final.justificativa and av_final.justificativa.strip():
            just_txt = f"Revisão: {av_final.justificativa.strip()}"
            if just_txt not in evidencias_globais_vistas:
                evidencias_globais.insert(0, just_txt)

        # 3. Contadores globais
        if status_item == 'NA':
            count_na += 1
        elif status_item == 'P':
            count_p += 1
        elif status_item == 'C':
            count_c += 1
            destaques_conformes.append({
                'referencia': item.referencia,
                'titulo': item.titulo,
                'evidencias': evidencias_globais[:3] or ["Processo e evidências documentais em conformidade."]
            })
        elif status_item == 'OM':
            count_om += 1
        elif status_item == 'NC':
            is_maior_global = False
            if av_final and av_final.grau_nc:
                is_maior_global = (av_final.grau_nc == 'MAIOR')
            else:
                graus_definidos = []
                for p in todas_perguntas_item:
                    r = respostas_map.get(p.id)
                    if r:
                        if r.grau_nc: graus_definidos.append(r.grau_nc)
                        for s in r.solicitacoes.all():
                            if s.conclusao == 'NC' and s.grau_nc:
                                graus_definidos.append(s.grau_nc)
                if graus_definidos:
                    is_maior_global = any(g == 'MAIOR' for g in graus_definidos)
                else:
                    is_maior_global = any('crítica' in ev.lower() or 'grave' in ev.lower() or 'sistêmica' in ev.lower() for ev in evidencias_globais)
            
            if is_maior_global:
                count_nc_maior += 1
            else:
                count_nc_menor += 1

        # 4. Geração de Cards (pontos_a_melhorar) agrupada por Item (sem duplicar por Agenda)
        if status_item in ['NC', 'OM']:
            evidencias_nc = []
            evidencias_om = []
            amostras_conformes = []
            evidencias_vistas = set()
            amostras_vistas = set()

            for p in todas_perguntas_item:
                r = respostas_map.get(p.id)
                if r:
                    for s in r.solicitacoes.all():
                        tit = s.solicitacao.strip() if s.solicitacao else ""
                        if not tit or tit.lower() == "sem título":
                            continue
                            
                        bloco = s.agenda.titulo if s.agenda else "Geral"
                        ev_txt = f"[{bloco}] {tit}: {s.evidencia.strip()}" if s.evidencia else f"[{bloco}] {tit}"
                        
                        if s.conclusao == 'NC' and status_item == 'NC':
                            if ev_txt and ev_txt not in evidencias_vistas:
                                evidencias_vistas.add(ev_txt)
                                evidencias_nc.append(ev_txt)
                        elif s.conclusao == 'OM':
                            if ev_txt and ev_txt not in evidencias_vistas:
                                evidencias_vistas.add(ev_txt)
                                evidencias_om.append(ev_txt)
                        else:
                            if ev_txt and ev_txt not in amostras_vistas:
                                amostras_vistas.add(ev_txt)
                                amostras_conformes.append(ev_txt)
                    
                    if r.texto_resposta and r.texto_resposta.strip():
                        txt = r.texto_resposta.strip()
                        if txt not in evidencias_vistas:
                            if r.classificacao == 'NC' and status_item == 'NC':
                                evidencias_vistas.add(txt)
                                evidencias_nc.append(txt)
                            elif r.classificacao == 'OM':
                                evidencias_vistas.add(txt)
                                evidencias_om.append(txt)

            if status_item == 'OM':
                pontos_a_melhorar.append({
                    'tipo': 'OM',
                    'badge': 'Oportunidade',
                    'cor': 'warning',
                    'cor_text': 'dark',
                    'bg_badge': '#ffc107',
                    'icone': 'bi-lightbulb-fill',
                    'referencia': item.referencia,
                    'titulo': item.titulo,
                    'evidencias_nc': evidencias_nc,
                    'evidencias_om': evidencias_om or ["Oportunidade de aprimoramento identificada no processo."],
                    'amostras_conformes': amostras_conformes
                })
            elif status_item == 'NC':
                pontos_a_melhorar.append({
                    'tipo': 'NC_MAIOR' if is_maior_global else 'NC_MENOR',
                    'badge': 'NC Maior' if is_maior_global else 'NC Menor',
                    'cor': 'danger',
                    'cor_text': 'white',
                    'bg_badge': '#dc3545',
                    'icone': 'bi-exclamation-triangle-fill',
                    'referencia': item.referencia,
                    'titulo': item.titulo,
                    'evidencias_nc': evidencias_nc or ["Evidência objetiva de não conformidade ao requisito."],
                    'evidencias_om': evidencias_om,
                    'amostras_conformes': amostras_conformes
                })

    total_avaliados = count_c + count_om + count_nc_menor + count_nc_maior + count_p
    # OBS não entra no percentual nem nos status de itens: o percentual é C / (C + NC + OM)
    total_percentual_base = count_c + count_om + count_nc_menor + count_nc_maior
    percentual_conformidade = round((count_c / total_percentual_base * 100), 1) if total_percentual_base > 0 else 0.0

    # ── CARGA DO MOTOR DE REGRAS (ELIMINAÇÃO EM CASCATA / FAIL-FAST) ──────────
    try:
        regras = {r.status_resultado: r for r in auditoria.norma.regras_veredicto.all()}
    except Exception:
        regras = {}

    regra_apto = regras.get('APTO')
    regra_ressalva = regras.get('RESSALVA')
    regra_inapto = regras.get('INAPTO')

    # 1. Card Vermelho (INADEQUADO) - Gatilhos Críticos (Teto)
    gatilho_nc_maior_inapto = regra_inapto.max_nc_maior if (regra_inapto and regra_inapto.max_nc_maior is not None) else 4
    gatilho_nc_menor_inapto = regra_inapto.max_nc_menor if (regra_inapto and regra_inapto.max_nc_menor is not None) else 15

    # 2. Card Verde (ADEQUADO) - Gatilhos de Perfeição (Piso)
    limite_nc_maior_apto = regra_apto.max_nc_maior if (regra_apto and regra_apto.max_nc_maior is not None) else 0
    limite_nc_menor_apto = regra_apto.max_nc_menor if (regra_apto and regra_apto.max_nc_menor is not None) else 2

    # Lógica do Motor por Cascata Estrita:
    # 1º: Atingiu qualquer gatilho crítico? -> INADEQUADO (OBS NÃO impacta gatilhos de NC)
    if count_nc_maior >= gatilho_nc_maior_inapto or count_nc_menor >= gatilho_nc_menor_inapto:
        veredito = {
            'status': 'INAPTO',
            'titulo': 'INADEQUADO / NÃO CONFORME',
            'cor_css': 'danger',
            'cor_badge': 'bg-danger text-white',
            'icone': 'bi-x-octagon-fill',
            'parecer': regra_inapto.texto_parecer_padrao if (regra_inapto and regra_inapto.texto_parecer_padrao) else 
                "Sistema inadequado e com alto risco crítico. As evidências apontam falhas sistêmicas ou acúmulo excessivo de desvios que inviabilizam a recomendação neste ciclo. Recomenda-se reavaliação integral e nova auditoria."
        }
    # 2º: Está dentro do piso de excelência? -> ADEQUADO
    elif count_nc_maior <= limite_nc_maior_apto and count_nc_menor <= limite_nc_menor_apto:
        veredito = {
            'status': 'APTO',
            'titulo': 'ADEQUADO / CONFORME',
            'cor_css': 'success',
            'cor_badge': 'bg-success text-white',
            'icone': 'bi-check-circle-fill',
            'parecer': regra_apto.texto_parecer_padrao if (regra_apto and regra_apto.texto_parecer_padrao) else 
                "Sistema de Gestão Adequado e Conforme. Os processos demonstram maturidade e conformidade aos requisitos normativos."
        }
    # 3º: Não é perfeito e não quebrou o teto crítico -> MELHORIA NECESSÁRIA (Fallback)
    else:
        veredito = {
            'status': 'RESSALVA',
            'titulo': 'MELHORIA NECESSÁRIA / RESSALVA',
            'cor_css': 'warning',
            'cor_badge': 'bg-warning text-dark',
            'icone': 'bi-exclamation-triangle-fill',
            'parecer': regra_ressalva.texto_parecer_padrao if (regra_ressalva and regra_ressalva.texto_parecer_padrao) else 
                "Melhorias são necessárias devido ao risco encontrado nos desvios pontuais. Exige-se apresentação de plano de ação corretiva formal em prazo determinado."
        }

    # Explicação Resumida da Regra / Motivo do Enquadramento
    if veredito['status'] == 'INAPTO':
        motivos = []
        if count_nc_maior >= gatilho_nc_maior_inapto:
            motivos.append(f"{count_nc_maior} Não Conformidade(s) Maior(es) (limite de reprovação: ≥ {gatilho_nc_maior_inapto})")
        if count_nc_menor >= gatilho_nc_menor_inapto:
            motivos.append(f"{count_nc_menor} Não Conformidade(s) Menor(es) (limite de reprovação: ≥ {gatilho_nc_menor_inapto})")
        explicacao = f"Enquadrado como Inadequado por atingir o limite crítico de desvios: {' e '.join(motivos)}."
    elif veredito['status'] == 'APTO':
        explicacao = f"Enquadrado como Adequado/Conforme por atender todos os requisitos e manter os desvios dentro do piso de tolerância da norma (máximo de {limite_nc_maior_apto} NC Maior e até {limite_nc_menor_apto} NC Menor)."
    else:
        motivos = []
        if count_nc_maior > limite_nc_maior_apto:
            motivos.append(f"{count_nc_maior} NC Maior (limite para aprovação direta: máx. {limite_nc_maior_apto})")
        if count_nc_menor > limite_nc_menor_apto:
            motivos.append(f"{count_nc_menor} NC Menor (limite para aprovação direta: máx. {limite_nc_menor_apto})")
        motivo_str = f" ({', '.join(motivos)})" if motivos else ""
        explicacao = f"Enquadrado em Ressalva{motivo_str}: desvios identificados exigem plano de ação corretiva formal dentro do prazo estabelecido, sem inviabilizar a recomendação do sistema."

    veredito['explicacao_regra'] = explicacao
    veredito['limite_nc_maior_apto'] = limite_nc_maior_apto
    veredito['limite_nc_menor_apto'] = limite_nc_menor_apto
    veredito['gatilho_nc_maior_inapto'] = gatilho_nc_maior_inapto
    veredito['gatilho_nc_menor_inapto'] = gatilho_nc_menor_inapto

    # Agrupamento das Agendas por Dia da Auditoria (Separados por Dia)
    from collections import defaultdict
    agendas_por_dia = defaultdict(list)
    for ag in auditoria.agendas.all().order_by('data', 'hora_inicio').prefetch_related('perguntas', 'itens_norma', 'perguntas__itens_norma'):
        data_chave = ag.data_real or ag.data
        agendas_por_dia[data_chave].append(ag)

    slides_agendas = []
    dia_num = 1
    for data_dia, ag_list in sorted(agendas_por_dia.items(), key=lambda x: (x[0] is None, x[0])):
        lotes_dia = list(chunks_list(ag_list, 6))
        total_lotes_dia = len(lotes_dia)
        for sub_idx, lote in enumerate(lotes_dia):
            sub_label = f" (Parte {sub_idx + 1}/{total_lotes_dia})" if total_lotes_dia > 1 else ""
            data_formatada = data_dia.strftime("%d/%m/%Y") if data_dia else "Geral"
            slides_agendas.append({
                'data': data_dia,
                'data_formatada': data_formatada,
                'dia_label': f"Dia {dia_num}: {data_formatada}{sub_label}",
                'agendas': lote,
                'total_requisitos_dia': sum(a.perguntas.count() for a in ag_list)
            })
        dia_num += 1



    from .models import PontoForteAuditoriaIso
    pontos_fortes_qs = list(auditoria.pontos_fortes.all().order_by('ordem', 'id'))
    if not pontos_fortes_qs and not auditoria.pontos_fortes.exists():
        for idx, pf in enumerate(PONTOS_FORTES_CATALOGO[:4]):
            PontoForteAuditoriaIso.objects.create(
                auditoria=auditoria,
                titulo=pf['titulo'],
                descricao=pf['descricao'],
                icone=pf['icone'],
                ordem=idx
            )
        pontos_fortes_qs = list(auditoria.pontos_fortes.all().order_by('ordem', 'id'))

    slides_descobertas_positivas = [pontos_fortes_qs] if pontos_fortes_qs else []

    # ── COLETA UNIFICADA DE PESSOAS AUDITADAS / ENTREVISTADAS ──
    from django.db.models import Q
    import re

    # 1. Busca respostas originais das entrevistas dos blocos
    respostas_auditados_qs = list(
        RespostaEntrevistaIso.objects.filter(auditoria=auditoria)
        .filter(
            Q(pergunta__texto_pergunta__icontains="auditadas") |
            Q(pergunta__texto_pergunta__icontains="entrevistadas") |
            Q(pergunta__texto_pergunta__icontains="nomes e funções") |
            Q(pergunta__dica_auditor__icontains="participante entrevistado")
        )
        .select_related('pergunta')
        .prefetch_related('solicitacoes')
    )

    def extrair_apenas_nome(texto: str) -> str:
        """Extrai apenas o nome da pessoa, descartando cargos ou departamentos após ' - ', ' – ' ou ' — '."""
        if not texto:
            return ""
        val = str(texto).strip()
        for sep in [' - ', ' – ', ' — ', '  -  ', ' -', '- ']:
            if sep in val:
                val = val.split(sep, 1)[0].strip()
        for suffix in ['(Participantes)', '(Participante)', '(Entrevistados)', '(Entrevistado)', '(Auditado)', '(Auditados)']:
            if val.endswith(suffix):
                val = val[:-len(suffix)].strip()
        for sep in [' - ', ' – ', ' — ']:
            if sep in val:
                val = val.split(sep, 1)[0].strip()
        return val.strip()

    nomes_entrevistados_blocos_originais = []
    nomes_originais_vistos = set()

    for resp in respostas_auditados_qs:
        for s in resp.solicitacoes.all():
            ev = (s.evidencia or "").strip()
            sol = (s.solicitacao or "").strip()
            sol_lower = sol.lower()
            is_generic = sol_lower in [
                'entrevistado', 'entrevistados', 'pessoa auditada', 'pessoas auditadas',
                'amostra', 'amostra #1', 'amostra #2', 'amostra #3', 'amostra #4', 'amostra #5',
                'solicitação', 'solicitacao', ''
            ]
            cand = ""
            if ev:
                cand = extrair_apenas_nome(ev)
            elif sol and not is_generic:
                cand = extrair_apenas_nome(sol)

            if cand and len(cand) >= 2:
                if cand.lower() not in nomes_originais_vistos:
                    nomes_originais_vistos.add(cand.lower())
                    nomes_entrevistados_blocos_originais.append(cand)
        
        if resp.texto_resposta and resp.texto_resposta.strip():
            for linha in re.split(r'[;\n]', resp.texto_resposta):
                l_clean = extrair_apenas_nome(linha)
                if l_clean and l_clean.lower() not in nomes_originais_vistos and len(l_clean) >= 2:
                    nomes_originais_vistos.add(l_clean.lower())
                    nomes_entrevistados_blocos_originais.append(l_clean)

    # 2. Fonte de exibição: preenchido EXCLUSIVAMENTE pelo campo Representantes (encerramento_representantes)
    pessoas_auditadas_lista = []
    if auditoria.encerramento_representantes and auditoria.encerramento_representantes.strip():
        nomes_para_exibir_brutos = [linha.strip() for linha in re.split(r'[;\n]', auditoria.encerramento_representantes) if linha.strip()]
        nomes_vistos = set()
        for item_str in nomes_para_exibir_brutos:
            item_clean = extrair_apenas_nome(item_str)
            if not item_clean or len(item_clean) < 2:
                continue
            key = item_clean.lower()
            if key not in nomes_vistos:
                nomes_vistos.add(key)
                pessoas_auditadas_lista.append({
                    'nome': item_clean,
                    'texto_completo': item_clean
                })

    # Ordena sempre em ordem alfabética (A-Z)
    pessoas_auditadas_lista.sort(key=lambda x: x['nome'].lower())
    nomes_entrevistados_blocos_originais.sort(key=lambda x: x.lower())

    # O slide só é renderizado se o campo Representantes estiver preenchido
    slides_pessoas_auditadas = [pessoas_auditadas_lista] if pessoas_auditadas_lista else []

    destaques_conformes.sort(key=lambda x: natural_sort_key(x['referencia']))
    slides_pontos_fortes = list(chunks_list(destaques_conformes, 4))
    slides_pontos_melhorar = list(chunks_list(pontos_a_melhorar, 3))
    slides_conselhos = list(chunks_list(conselhos_por_item, 3))

    context = {
        'auditoria': auditoria,
        'agendas': agendas,
        'slides_agendas': slides_agendas,
        'pessoas_auditadas_lista': pessoas_auditadas_lista,
        'nomes_entrevistados_blocos_originais': nomes_entrevistados_blocos_originais,
        'slides_pessoas_auditadas': slides_pessoas_auditadas,
        'metricas': {
            'total_avaliados': total_avaliados,
            'percentual_conformidade': percentual_conformidade,
            'total_c': count_c,
            'total_obs': count_obs,
            'total_om': count_om,
            'total_nc_menor': count_nc_menor,
            'total_nc_maior': count_nc_maior,
            'total_nc': count_nc_menor + count_nc_maior,
            'total_na': count_na,
            'total_p': count_p,
        },
        'veredito': veredito,
        'itens_conformes': destaques_conformes,
        'slides_descobertas_positivas': slides_descobertas_positivas,
        'pontos_fortes_catalogo': PONTOS_FORTES_CATALOGO,
        'pontos_fortes_todos': pontos_fortes_qs,
        'slides_pontos_fortes': slides_pontos_fortes,
        'slides_pontos_melhorar': slides_pontos_melhorar,
        'slides_conselhos': slides_conselhos,
    }
    return render(request, "auditoria/iso/fechamento_presentation.html", context)

@login_required
@require_POST
def api_iso_pontos_fortes_adicionar(request, auditoria_id):
    from .models import AuditoriaIso, PontoForteAuditoriaIso
    from django.http import JsonResponse

    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    titulo = request.POST.get('titulo', '').strip()
    descricao = request.POST.get('descricao', '').strip()
    icone = request.POST.get('icone', 'bi-shield-fill-check').strip() or 'bi-shield-fill-check'

    if not titulo:
        return JsonResponse({'success': False, 'error': 'Título é obrigatório.'}, status=400)

    ordem_max = auditoria.pontos_fortes.count()
    novo_pf = PontoForteAuditoriaIso.objects.create(
        auditoria=auditoria,
        titulo=titulo,
        descricao=descricao,
        icone=icone,
        ordem=ordem_max
    )
    return JsonResponse({
        'success': True,
        'id': novo_pf.id,
        'titulo': novo_pf.titulo,
        'descricao': novo_pf.descricao,
        'icone': novo_pf.icone,
        'message': f"Ponto forte '{titulo}' adicionado com sucesso."
    })

@login_required
@require_POST
def api_iso_pontos_fortes_remover(request, auditoria_id, pk):
    from .models import AuditoriaIso, PontoForteAuditoriaIso
    from django.http import JsonResponse

    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    pf = get_object_or_404(PontoForteAuditoriaIso, auditoria=auditoria, pk=pk)
    titulo = pf.titulo
    pf.delete()
    return JsonResponse({'success': True, 'message': f"Ponto forte '{titulo}' removido."})

@login_required
def api_iso_pontos_fortes_listar(request, auditoria_id):
    from .models import AuditoriaIso
    from django.http import JsonResponse

    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    pontos_fortes = list(auditoria.pontos_fortes.all().values('id', 'titulo', 'descricao', 'icone', 'ordem'))
    return JsonResponse({'success': True, 'pontos_fortes': pontos_fortes})
@login_required
def iso_auditoria_export_excel(request, auditoria_id):
    """
    Exportação do Relatório Excel (Checklist da Norma) utilizando a estratégia
    de Template Injection para preservar formatações e fórmulas da aba Resultados.
    """
    from django.http import HttpResponse
    from .models import AuditoriaIso
    from .services.checklist_export import generate_auditoria_excel_buffer

    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    try:
        excel_buffer = generate_auditoria_excel_buffer(auditoria)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect(request.META.get('HTTP_REFERER', reverse('auditoria:iso_fechamento_presentation', kwargs={'auditoria_id': auditoria.id})))

    # Nome amigável do arquivo
    codigo_norma = re.sub(r'[^a-zA-Z0-9_-]', '_', auditoria.norma.codigo)
    filename = f"Checklist_Auditoria_{codigo_norma}_{auditoria.id}.xlsx"

    response = HttpResponse(
        excel_buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def iso_auditoria_export_docx(request, auditoria_id):
    """
    Exportação do Relatório de Auditoria Interna em formato Word (.docx),
    com injeção de conteúdos complexos (HTML da Síntese, Imagens, Agrupamento por Área Funcional
    e Tabela Nativa de Avaliação Geral).
    """
    from django.http import HttpResponse
    from .models import AuditoriaIso
    from .services.relatorio_docx_export import generate_relatorio_docx_buffer

    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    try:
        docx_buffer = generate_relatorio_docx_buffer(auditoria)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect(request.META.get('HTTP_REFERER', reverse('auditoria:iso_fechamento_presentation', kwargs={'auditoria_id': auditoria.id})))

    codigo_norma = re.sub(r'[^a-zA-Z0-9_-]', '_', auditoria.norma.codigo)
    data_str = auditoria.data_inicio.strftime('%Y%m%d') if auditoria.data_inicio else str(auditoria.id)
    filename = f"Relatorio_Auditoria_{codigo_norma}_{data_str}.docx"

    response = HttpResponse(
        docx_buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_POST
def iso_norma_upload_template(request, pk):
    """
    Realiza o upload ou substituição de template DOCX ou XLSX para a Norma.
    Garante persistência em banco via Base64 e suporte a FileSystemStorage seguro.
    """
    import base64
    from django.utils import timezone
    from django.core.files.base import ContentFile

    norma = get_object_or_404(Norma, pk=pk)
    tipo = request.POST.get("tipo", "").strip().lower()
    uploaded_file = request.FILES.get("arquivo")

    if not uploaded_file:
        messages.error(request, "Nenhum arquivo enviado.")
        return redirect(f"{reverse('auditoria:iso_norma_detail', kwargs={'pk': norma.id})}?tab=uploads")

    file_name = uploaded_file.name
    ext = file_name.split(".")[-1].lower()
    file_bytes = uploaded_file.read()
    file_b64 = base64.b64encode(file_bytes).decode('utf-8')

    if tipo == "docx":
        if ext != "docx":
            messages.error(request, "Formato inválido. O template de Relatório Executivo deve ser um arquivo .docx.")
            return redirect(f"{reverse('auditoria:iso_norma_detail', kwargs={'pk': norma.id})}?tab=uploads")
        
        norma.template_docx_base64 = file_b64
        norma.template_docx_nome_original = file_name
        norma.template_docx_atualizado_em = timezone.now()

        # Tenta salvar no storage se gravável
        try:
            if norma.template_docx:
                norma.template_docx.delete(save=False)
            norma.template_docx.save(file_name, ContentFile(file_bytes), save=False)
        except Exception:
            pass

        norma.save()
        messages.success(request, f"Template de Relatório Word ({file_name}) carregado com sucesso!")

    elif tipo == "xlsx":
        if ext != "xlsx":
            messages.error(request, "Formato inválido. O template de Checklist deve ser um arquivo .xlsx.")
            return redirect(f"{reverse('auditoria:iso_norma_detail', kwargs={'pk': norma.id})}?tab=uploads")
        
        norma.template_xlsx_base64 = file_b64
        norma.template_xlsx_nome_original = file_name
        norma.template_xlsx_atualizado_em = timezone.now()

        try:
            if norma.template_xlsx:
                norma.template_xlsx.delete(save=False)
            norma.template_xlsx.save(file_name, ContentFile(file_bytes), save=False)
        except Exception:
            pass

        norma.save()
        messages.success(request, f"Template de Checklist Excel ({file_name}) carregado com sucesso!")
    else:
        messages.error(request, "Tipo de template não reconhecido.")

    return redirect(f"{reverse('auditoria:iso_norma_detail', kwargs={'pk': norma.id})}?tab=uploads")


@login_required
@require_POST
def iso_norma_delete_template(request, pk, tipo):
    """
    Remove o template DOCX ou XLSX da Norma.
    """
    norma = get_object_or_404(Norma, pk=pk)
    tipo = tipo.strip().lower()

    if tipo == "docx":
        try:
            if norma.template_docx:
                norma.template_docx.delete(save=False)
        except Exception:
            pass
        norma.template_docx = None
        norma.template_docx_base64 = ""
        norma.template_docx_nome_original = ""
        norma.template_docx_atualizado_em = None
        norma.save()
        messages.success(request, "Template de Relatório Word (.docx) excluído.")
    elif tipo == "xlsx":
        try:
            if norma.template_xlsx:
                norma.template_xlsx.delete(save=False)
        except Exception:
            pass
        norma.template_xlsx = None
        norma.template_xlsx_base64 = ""
        norma.template_xlsx_nome_original = ""
        norma.template_xlsx_atualizado_em = None
        norma.save()
        messages.success(request, "Template de Checklist Excel (.xlsx) excluído.")

    return redirect(f"{reverse('auditoria:iso_norma_detail', kwargs={'pk': norma.id})}?tab=uploads")


@login_required
def iso_norma_download_template(request, pk, tipo):
    """
    Faz o download do template atual (DOCX ou XLSX) cadastrado na Norma.
    """
    import base64
    from django.http import HttpResponse, FileResponse, Http404
    norma = get_object_or_404(Norma, pk=pk)
    tipo = tipo.strip().lower()

    if tipo == "docx":
        if norma.template_docx_base64:
            data = base64.b64decode(norma.template_docx_base64)
            filename = norma.template_docx_nome_original or f"template_relatorio_{norma.codigo}.docx"
            response = HttpResponse(data, content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        elif norma.template_docx:
            try:
                filename = norma.template_docx_nome_original or f"template_relatorio_{norma.codigo}.docx"
                return FileResponse(norma.template_docx.open('rb'), as_attachment=True, filename=filename)
            except Exception:
                pass
        raise Http404("Nenhum template DOCX cadastrado para esta norma.")

    elif tipo == "xlsx":
        if norma.template_xlsx_base64:
            data = base64.b64decode(norma.template_xlsx_base64)
            filename = norma.template_xlsx_nome_original or f"template_checklist_{norma.codigo}.xlsx"
            response = HttpResponse(data, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        elif norma.template_xlsx:
            try:
                filename = norma.template_xlsx_nome_original or f"template_checklist_{norma.codigo}.xlsx"
                return FileResponse(norma.template_xlsx.open('rb'), as_attachment=True, filename=filename)
            except Exception:
                pass
        raise Http404("Nenhum template XLSX cadastrado para esta norma.")
    else:
        raise Http404("Tipo inválido.")


@login_required
def iso_norma_download_template_padrao(request, tipo):
    """
    Gera e entrega o template base de referência com todas as tags e estruturas pré-configuradas.
    """
    from django.http import HttpResponse, Http404
    tipo = tipo.strip().lower()

    if tipo == "docx":
        from .services.relatorio_docx_export import ensure_master_template_docx_exists
        template_path = ensure_master_template_docx_exists()
        with open(template_path, 'rb') as f:
            content = f.read()
        response = HttpResponse(content, content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        response['Content-Disposition'] = 'attachment; filename="Template_Base_Relatorio_Auditoria.docx"'
        return response
    elif tipo == "xlsx":
        from .services.checklist_export import build_clean_checklist_template
        wb = build_clean_checklist_template()
        import io
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="Template_Base_Checklist_Auditoria.xlsx"'
        return response
    else:
        raise Http404("Tipo inválido.")


@login_required
@require_POST
def api_iso_fechamento_salvar(request, auditoria_id):
    """
    Salva a Síntese Executiva (HTML WYSIWYG) e metadados de fechamento da auditoria.
    """
    from .models import AuditoriaIso
    try:
        auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
        data = json.loads(request.body)
        
        if "sintese" in data:
            auditoria.sintese = data.get("sintese", "").strip()
        if "conclusao_texto" in data:
            auditoria.conclusao_texto = data.get("conclusao_texto", "").strip()
        if "encerramento_representantes" in data:
            raw_rep = data.get("encerramento_representantes", "").strip()
            def clean_nome_single(n):
                val = str(n).strip()
                for sep in [' - ', ' – ', ' — ', '  -  ', ' -', '- ']:
                    if sep in val:
                        val = val.split(sep, 1)[0].strip()
                for suffix in ['(Participantes)', '(Participante)', '(Entrevistados)', '(Entrevistado)', '(Auditado)', '(Auditados)']:
                    if val.endswith(suffix):
                        val = val[:-len(suffix)].strip()
                for sep in [' - ', ' – ', ' — ']:
                    if sep in val:
                        val = val.split(sep, 1)[0].strip()
                return val.strip()

            linhas_limpas = []
            for linha in re.split(r'[;\n]', raw_rep):
                c = clean_nome_single(linha)
                if c and len(c) >= 2:
                    linhas_limpas.append(c)
            # Remove duplicados preservando ordem
            seen = set()
            dedup = []
            for n in linhas_limpas:
                if n.lower() not in seen:
                    seen.add(n.lower())
                    dedup.append(n)
            auditoria.encerramento_representantes = "\n".join(dedup)
        if "encerramento_auditores" in data:
            auditoria.encerramento_auditores = data.get("encerramento_auditores", "").strip()
        if "empresa_auditada" in data:
            empresa = data.get("empresa_auditada", "").strip()
            auditoria.empresa_auditada = empresa
            auditoria.unidade = empresa
        if "escopo" in data:
            auditoria.escopo = data.get("escopo", "").strip()

        auditoria.save()
        return JsonResponse({"success": True, "message": "Dados do relatório salvos com sucesso!"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)

@login_required
@require_POST
def api_iso_auditoria_editar_planejamento(request, auditoria_id):
    """
    Edição rápida dos dados de planejamento da Auditoria ISO
    (Unidade, Auditor Líder, Tipo de Auditoria, Escopo, Objetivo, Período, etc.).
    """
    from .models import AuditoriaIso
    try:
        auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
        data = json.loads(request.body)
        
        if "unidade" in data:
            unidade = data.get("unidade", "").strip()
            auditoria.unidade = unidade
            auditoria.empresa_auditada = unidade
        if "municipio" in data:
            auditoria.municipio = data.get("municipio", "").strip()
        if "auditor_lider" in data:
            auditoria.auditor_lider = data.get("auditor_lider", "").strip()
        if "responsavel_qms" in data:
            auditoria.responsavel_qms = data.get("responsavel_qms", "").strip()
        if "tipo_auditoria" in data:
            auditoria.tipo_auditoria = data.get("tipo_auditoria") or "PRESENCIAL"
        if "empresa_auditada" in data:
            auditoria.empresa_auditada = data.get("empresa_auditada", "").strip()
        if "escopo" in data:
            auditoria.escopo = data.get("escopo", "").strip()
        if "objetivo" in data:
            auditoria.objetivo = data.get("objetivo", "").strip()
        if "data_inicio" in data and data["data_inicio"]:
            auditoria.data_inicio = data["data_inicio"]
        if "data_fim" in data and data["data_fim"]:
            auditoria.data_fim = data["data_fim"]

        auditoria.save()
        return JsonResponse({
            "success": True,
            "message": "Planejamento da auditoria atualizado com sucesso!",
            "empresa_auditada": auditoria.unidade or auditoria.empresa_auditada,
            "escopo": auditoria.escopo,
            "tipo_auditoria": auditoria.tipo_auditoria
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


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
    from organization.models import Unidade
    from django.contrib.auth import get_user_model
    User = get_user_model()

    norma = get_object_or_404(Norma, pk=pk)
    
    itens_qs = ItemNorma.objects.filter(norma=norma).order_by('ordem', 'referencia')
    itens = []
    for item in itens_qs:
        item.nivel = item.referencia.count('.')
        itens.append(item)
        
    perguntas_qs = BancoPergunta.objects.filter(itens_norma__norma=norma, ativa=True).distinct().prefetch_related('itens_norma')
    
    def get_pergunta_sort_key(p):
        items = list(p.itens_norma.all())
        if items:
            def parse_ref(ref):
                parts = (ref or '').split('.')
                return [int(x) if x.isdigit() else x for x in parts]
            min_item = min(items, key=lambda it: (it.ordem or 0, parse_ref(it.referencia)))
            return (min_item.ordem or 0, parse_ref(min_item.referencia), p.id)
        return (999999, [], p.id)
        
    perguntas = sorted(list(perguntas_qs), key=get_pergunta_sort_key)
        
    modelos = ModeloAuditoriaIso.objects.filter(norma=norma).prefetch_related('perguntas')
    auditorias = AuditoriaIso.objects.filter(norma=norma).order_by('-criado_em')

    try:
        regras_dict = {r.status_resultado: r for r in norma.regras_veredicto.all()}
    except Exception:
        regras_dict = {}

    unidades = Unidade.objects.filter(ativo=True).order_by('nome')
    usuarios = User.objects.filter(is_active=True).order_by('first_name', 'username')

    return render(request, "auditoria/iso/setup/norma_detail.html", {
        "norma": norma,
        "itens": itens,
        "perguntas": perguntas,
        "modelos": modelos,
        "auditorias": auditorias,
        "unidades": unidades,
        "usuarios": usuarios,
        "regra_apto": regras_dict.get('APTO'),
        "regra_ressalva": regras_dict.get('RESSALVA'),
        "regra_inapto": regras_dict.get('INAPTO'),
        "active_tab": request.GET.get('tab', 'itens')
    })


@login_required
@require_POST
def iso_norma_regras_salvar(request, pk):
    """Salva a parametrização do Motor de Aprovação para a Norma"""
    from .models import RegraVeredictoNorma
    norma = get_object_or_404(Norma, pk=pk)

    from django.utils import timezone
    now = timezone.now()

    # 1. Apto
    RegraVeredictoNorma.objects.update_or_create(
        norma=norma,
        status_resultado='APTO',
        defaults={
            'min_percentual_conformidade': float(request.POST.get('apto_min_pct', 95.0) or 95.0),
            'max_nc_maior': int(request.POST.get('apto_max_nc_maior', 0) or 0),
            'max_nc_menor': int(request.POST.get('apto_max_nc_menor', 2) or 2),
            'texto_parecer_padrao': request.POST.get('apto_texto', '').strip(),
            'cor_badge': '#198754'
        }
    )

    # 2. Ressalva
    RegraVeredictoNorma.objects.update_or_create(
        norma=norma,
        status_resultado='RESSALVA',
        defaults={
            'min_percentual_conformidade': float(request.POST.get('ressalva_min_pct', 80.0) or 80.0),
            'max_nc_maior': int(request.POST.get('ressalva_max_nc_maior', 0) or 0),
            'max_nc_menor': int(request.POST.get('ressalva_max_nc_menor', 5) or 5),
            'texto_parecer_padrao': request.POST.get('ressalva_texto', '').strip(),
            'cor_badge': '#ffc107'
        }
    )

    # 3. Inapto (Gatilhos Críticos / Teto)
    RegraVeredictoNorma.objects.update_or_create(
        norma=norma,
        status_resultado='INAPTO',
        defaults={
            'min_percentual_conformidade': 0.0,
            'max_nc_maior': int(request.POST.get('inapto_gatilho_nc_maior', 4) or 4),
            'max_nc_menor': int(request.POST.get('inapto_gatilho_nc_menor', 15) or 15),
            'texto_parecer_padrao': request.POST.get('inapto_texto', '').strip(),
            'cor_badge': '#dc3545'
        }
    )

    messages.success(request, f"Regras de Aprovação e Fechamento da norma '{norma.codigo}' salvas com sucesso!")
    return redirect(f"{reverse('auditoria:iso_norma_detail', kwargs={'pk': norma.id})}?tab=regras")

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
        "pergunta_padrao": item.pergunta_padrao or "",
        "evidencia_padrao": item.evidencia_padrao or "",
        "ordem": item.ordem,
        "atalho_especial": item.atalho_especial,
        "edit_url": reverse('auditoria:iso_item_edit', args=[item.id]),
        "delete_url": reverse('auditoria:iso_item_delete', args=[item.id]),
    })

@login_required
@require_POST
def iso_item_toggle_atalho_api(request, pk):
    from django.http import JsonResponse
    item = get_object_or_404(ItemNorma, pk=pk)
    item.atalho_especial = not item.atalho_especial
    item.save(update_fields=['atalho_especial'])
    return JsonResponse({
        "success": True,
        "id": item.id,
        "referencia": item.referencia,
        "atalho_especial": item.atalho_especial
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
    from django.db.models.deletion import ProtectedError
    pergunta = get_object_or_404(BancoPergunta, pk=pk)
    
    norma_id = request.POST.get('norma') or request.GET.get('norma')
    itens = list(pergunta.itens_norma.all())
    if not norma_id and itens:
        norma_id = itens[0].norma_id

    # Antes de excluir, migra todas as respostas e solicitações para a pergunta ativa canônica do item
    for item in itens:
        p_canon = item.perguntas_vinculadas.filter(ativa=True).exclude(pk=pergunta.pk).order_by('id').first()
        if p_canon:
            for resp in RespostaEntrevistaIso.objects.filter(pergunta=pergunta):
                resp_canon, _ = RespostaEntrevistaIso.objects.get_or_create(
                    auditoria=resp.auditoria,
                    pergunta=p_canon,
                    defaults={'respondida_por': resp.respondida_por}
                )
                SolicitacaoEvidenciaIso.objects.filter(resposta=resp).update(resposta=resp_canon)
                if resp.texto_resposta and not resp_canon.texto_resposta:
                    resp_canon.texto_resposta = resp.texto_resposta
                    resp_canon.save(update_fields=['texto_resposta'])
                resp.delete()
                
            # Substitui pergunta nas agendas e blocos
            for ag in AgendaAuditoriaIso.objects.filter(perguntas=pergunta):
                ag.perguntas.remove(pergunta)
                ag.perguntas.add(p_canon)
            for bl in BlocoModeloIso.objects.filter(perguntas=pergunta):
                bl.perguntas.remove(pergunta)
                bl.perguntas.add(p_canon)
            for mo in ModeloAuditoriaIso.objects.filter(perguntas=pergunta):
                mo.perguntas.remove(pergunta)
                mo.perguntas.add(p_canon)

    try:
        pergunta.delete()
        messages.success(request, "Pergunta removida com sucesso e todas as solicitações foram vinculadas ao item da norma!")
    except ProtectedError:
        # Se ainda restarem respostas protegidas em outro contexto, desativa a pergunta mantendo a integridade
        pergunta.ativa = False
        pergunta.save(update_fields=['ativa'])
        messages.warning(
            request,
            "Esta pergunta possuía respostas registradas no histórico. "
            "Ela foi desativada e todas as suas solicitações foram preservadas e associadas ao item da norma."
        )
    except Exception as e:
        messages.error(request, f"Não foi possível remover a pergunta: {e}")

    if norma_id:
        return redirect(reverse('auditoria:iso_norma_detail', args=[norma_id]) + "?tab=perguntas")
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
        
    perguntas_disponiveis = BancoPergunta.objects.filter(itens_norma__norma=bloco.modelo.norma).prefetch_related('itens_norma').distinct()
    
    def get_pergunta_sort_key(p):
        first_item = p.itens_norma.all()
        if first_item:
            item = first_item[0]
            return (item.ordem or 0, natural_sort_key(item.referencia))
        return (999, [])

    # Remove perguntas inativas do bloco se houver
    inativas_ids = list(bloco.perguntas.filter(ativa=False).values_list('id', flat=True))
    if inativas_ids:
        bloco.perguntas.remove(*inativas_ids)

    perguntas_vinculadas = sorted(list(bloco.perguntas.filter(ativa=True).prefetch_related('itens_norma')), key=get_pergunta_sort_key)
    perguntas_vinculadas_ids = set(p.id for p in perguntas_vinculadas)
    
    # Análise de Cobertura de Escopo Planejado para o Bloco do Modelo (Ordenação Natural de Requisitos)
    itens_alvo_todos = sorted(list(bloco.itens_norma.all()), key=lambda x: (x.ordem or 0, natural_sort_key(x.referencia)))
    
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
    itens_norma_todos = sorted(list(ItemNorma.objects.filter(norma=bloco.modelo.norma)), key=lambda x: (x.ordem or 0, natural_sort_key(x.referencia)))
    
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
    """Cria (ou reutiliza) uma pergunta no Banco Geral e a vincula ao Bloco do Modelo.
    Anti-duplicata por ItemNorma: se o item já tem uma BancoPergunta vinculada, reutiliza ela.
    """
    from .models import BlocoModeloIso, BancoPergunta, ItemNorma
    from django.db import transaction
    bloco = get_object_or_404(BlocoModeloIso, pk=pk, modelo_id=modelo_id)

    texto_pergunta = (request.POST.get("texto_pergunta") or "").strip()
    dica_resposta = request.POST.get("dica_resposta", "")
    item_ids = request.POST.getlist("itens_norma")

    if not texto_pergunta:
        messages.error(request, "O enunciado da pergunta é obrigatório.")
        return redirect('auditoria:iso_modelo_bloco_perguntas', modelo_id=modelo_id, pk=pk)

    with transaction.atomic():
        # Anti-duplicata por item: se algum dos itens informados já tem uma pergunta, reutiliza a primeira
        existente = None
        if item_ids:
            existente = BancoPergunta.objects.filter(
                itens_norma__id__in=item_ids
            ).order_by('id').first()

        if existente:
            nova_pergunta = existente
            if not nova_pergunta.dica_auditor and dica_resposta:
                nova_pergunta.dica_auditor = dica_resposta
                nova_pergunta.save(update_fields=['dica_auditor'])
            foi_criada = False
        else:
            nova_pergunta = BancoPergunta.objects.create(
                texto_pergunta=texto_pergunta,
                dica_auditor=dica_resposta
            )
            foi_criada = True

        if item_ids:
            # Adiciona itens sem remover os já existentes (union)
            nova_pergunta.itens_norma.add(*item_ids)

            # Auto-define como padrão para o item se unitário e sem padrão definido
            if len(item_ids) == 1 and foi_criada:
                try:
                    item_unico = ItemNorma.objects.get(pk=item_ids[0])
                    if not item_unico.pergunta_padrao:
                        item_unico.pergunta_padrao = texto_pergunta
                        item_unico.evidencia_padrao = dica_resposta
                        item_unico.save(update_fields=['pergunta_padrao', 'evidencia_padrao'])
                except ItemNorma.DoesNotExist:
                    pass

        bloco.perguntas.add(nova_pergunta)

    acao = "criada" if foi_criada else "já existia (reutilizada)"
    messages.success(request, f"Pergunta '{nova_pergunta.texto_pergunta[:40]}...' {acao} e vinculada ao bloco!")

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == 'true':
        from django.http import JsonResponse
        return JsonResponse({
            'success': True,
            'pergunta_id': nova_pergunta.id,
            'texto_pergunta': nova_pergunta.texto_pergunta,
            'foi_criada': foi_criada,
            'bloco_id': bloco.id,
            'bloco_titulo': bloco.titulo,
            'message': f"Pergunta {acao} e vinculada ao bloco '{bloco.titulo}'!"
        })

    next_url = request.POST.get('next') or request.GET.get('next') or request.META.get('HTTP_REFERER')
    if next_url and ('modelos' in next_url or 'setup' in next_url):
        return redirect(next_url)
    return redirect('auditoria:iso_modelo_bloco_perguntas', modelo_id=modelo_id, pk=pk)

@login_required
@require_POST
def iso_modelo_bloco_sincronizar(request, modelo_id, pk):
    """Sincroniza perguntas existentes no Banco Geral que cobrem os requisitos alvo do bloco."""
    from .models import BlocoModeloIso, BancoPergunta
    bloco = get_object_or_404(BlocoModeloIso, pk=pk, modelo_id=modelo_id)
    
    itens_alvo = bloco.itens_norma.all()
    perguntas_sincronizadas = BancoPergunta.objects.filter(itens_norma__in=itens_alvo, ativa=True).distinct()
    
    count_antes = bloco.perguntas.count()
    bloco.perguntas.add(*perguntas_sincronizadas)
    count_depois = bloco.perguntas.count()
    
    adicionadas = count_depois - count_antes
    messages.success(request, f"{adicionadas} pergunta(s) sincronizada(s) com sucesso a partir dos requisitos alvo deste bloco!")
    
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

    # Desduplicação Automática e Filtro de Ativas: garante que apenas perguntas ativas e não-duplicadas sejam exibidas no bloco
    inativas_ids = list(agenda.perguntas.filter(ativa=False).values_list('id', flat=True))
    if inativas_ids:
        agenda.perguntas.remove(*inativas_ids)

    perguntas_raw = list(agenda.perguntas.filter(ativa=True).prefetch_related('itens_norma'))
    itens_vistos = set()
    perguntas_unicas = []
    perguntas_remover_ids = []
    
    for p in perguntas_raw:
        item_ids_p = set(p.itens_norma.values_list('id', flat=True))
        # Se todos os itens desta pergunta já foram cobertos por outra pergunta anterior neste bloco, é duplicata
        if item_ids_p and item_ids_p.issubset(itens_vistos):
            perguntas_remover_ids.append(p.id)
        else:
            itens_vistos.update(item_ids_p)
            perguntas_unicas.append(p)

    # Desvincula automaticamente as duplicadas do bloco
    if perguntas_remover_ids:
        agenda.perguntas.remove(*perguntas_remover_ids)

    perguntas_ordenadas = sorted(perguntas_unicas, key=get_pergunta_sort_key)

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
    """Cria (ou reutiliza) uma pergunta no Banco Geral e a vincula à Agenda.
    Anti-duplicata por ItemNorma: se o item já tem uma BancoPergunta, reutiliza ela.
    """
    from .models import AgendaAuditoriaIso, AuditoriaIso, BancoPergunta, ItemNorma
    from django.http import JsonResponse
    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    agenda = get_object_or_404(AgendaAuditoriaIso, pk=pk, auditoria=auditoria)

    texto_pergunta = (request.POST.get("texto_pergunta") or "").strip()
    dica_resposta = request.POST.get("dica_resposta", "") or request.POST.get("dica_auditor", "")
    item_ids = request.POST.getlist("itens_norma")

    if not texto_pergunta:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'O enunciado da pergunta é obrigatório.'}, status=400)
        messages.error(request, "O enunciado da pergunta é obrigatório.")
        return redirect('auditoria:iso_agenda_detail', auditoria_id=auditoria.id, pk=agenda.id)

    # Anti-duplicata por item: se o item já tem uma pergunta no banco, reutiliza a mais antiga
    existente = None
    if item_ids:
        existente = BancoPergunta.objects.filter(
            itens_norma__id__in=item_ids
        ).order_by('id').first()

    if existente:
        nova_pergunta = existente
        if not nova_pergunta.dica_auditor and dica_resposta:
            nova_pergunta.dica_auditor = dica_resposta
            nova_pergunta.save(update_fields=['dica_auditor'])
        foi_criada = False
    else:
        nova_pergunta = BancoPergunta.objects.create(
            texto_pergunta=texto_pergunta,
            dica_auditor=dica_resposta
        )
        foi_criada = True

    # Valida conflito de item no bloco SOMENTE para perguntas que ainda não estão no bloco
    if item_ids and not agenda.perguntas.filter(pk=nova_pergunta.pk).exists():
        itens_no_bloco = ItemNorma.objects.filter(
            id__in=item_ids,
            perguntas_vinculadas__agendas_vinculadas=agenda
        ).distinct()
        if itens_no_bloco.exists():
            conflito_refs = ", ".join([it.referencia for it in itens_no_bloco])
            err_msg = f"Este bloco ({agenda.titulo}) já possui pergunta avaliando o(s) item(ns) [{conflito_refs}]."
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': err_msg}, status=400)
            messages.error(request, err_msg)
            return redirect('auditoria:iso_agenda_detail', auditoria_id=auditoria.id, pk=agenda.id)

    if item_ids:
        # Adiciona itens sem remover os já existentes (union)
        nova_pergunta.itens_norma.add(*item_ids)

    agenda.perguntas.add(nova_pergunta)

    acao = "criada" if foi_criada else "já existia (reutilizada)"
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'pergunta_id': nova_pergunta.id,
            'texto_pergunta': nova_pergunta.texto_pergunta,
            'foi_criada': foi_criada,
            'agenda_id': agenda.id,
            'agenda_titulo': agenda.titulo,
            'total_perguntas': agenda.perguntas.count(),
            'message': f"Pergunta {acao} e vinculada ao bloco '{agenda.titulo}'!"
        })

    messages.success(request, f"Pergunta {acao} e vinculada com sucesso!")
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

@login_required
def iso_auditoria_cronograma(request, auditoria_id):
    from collections import defaultdict
    from .models import AuditoriaIso
    from datetime import datetime
    
    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    agendas_qs = auditoria.agendas.filter(data__isnull=False).order_by('data', 'hora_inicio').prefetch_related('itens_norma')
    
    # Pre-build hierarchy for item condensing
    from .models import ItemNorma
    all_norma_items = ItemNorma.objects.filter(norma=auditoria.norma).select_related('parent')
    parent_to_children = defaultdict(list)
    item_by_id = {}
    for item in all_norma_items:
        item_by_id[item.id] = item
        if item.parent_id:
            parent_to_children[item.parent_id].append(item.id)
            
    def get_condensed_items(agenda_items):
        selected_items = list(agenda_items)
        if not selected_items:
            return []

        # Identifica e descarta itens que são pais/prefixos de outros itens na mesma sequência (mantém apenas as folhas / último nível)
        parent_ids = set()
        for item in selected_items:
            prefix = item.referencia + '.'
            if any(other.referencia.startswith(prefix) for other in selected_items if other.id != item.id):
                parent_ids.add(item.id)

        folhas = [item for item in selected_items if item.id not in parent_ids]
        
        def sort_key(item):
            parts = item.referencia.split('.')
            return ((item.ordem or 0), [int(p) if p.isdigit() else p for p in parts])
            
        return sorted(folhas, key=sort_key)
    
    total_agendas = agendas_qs.count()
    total_concluidas = agendas_qs.filter(concluida=True).count()
    progresso_geral = int((total_concluidas / total_agendas) * 100) if total_agendas > 0 else 0

    # Pré-calcular cores globais dos itens da norma na auditoria (baseado nas solicitações e respostas)
    from .models import SolicitacaoEvidenciaIso, RespostaEntrevistaIso

    # 1. Coleta todas as solicitações registradas na auditoria
    sols_todas = SolicitacaoEvidenciaIso.objects.filter(
        resposta__auditoria=auditoria
    ).select_related('resposta__pergunta').prefetch_related('resposta__pergunta__itens_norma')

    item_pior_global = {}
    for sol in sols_todas:
        concl = sol.conclusao
        prio = 0
        if concl == 'NC':
            prio = 4
        elif concl == 'OM':
            prio = 3
        elif concl in ['C', 'OBS']:
            prio = 2
        elif concl == 'NA':
            prio = 1
            
        for item in sol.resposta.pergunta.itens_norma.all():
            if prio > item_pior_global.get(item.id, 0):
                item_pior_global[item.id] = prio

    # 2. Respostas diretas sem solicitações ou cadastradas no veredicto
    respostas_todas = RespostaEntrevistaIso.objects.filter(
        auditoria=auditoria
    ).prefetch_related('pergunta__itens_norma')
    for resp in respostas_todas:
        cls = resp.classificacao
        prio = 0
        if cls == 'NC':
            prio = 4
        elif cls == 'OM':
            prio = 3
        elif cls in ['C', 'OBS']:
            prio = 2
        elif cls == 'NA':
            prio = 1
        for item in resp.pergunta.itens_norma.all():
            if item.id not in item_pior_global or item_pior_global[item.id] == 0:
                if prio > item_pior_global.get(item.id, 0):
                    item_pior_global[item.id] = prio

    PRIO_TO_CSS = {
        4: 'bg-danger',
        3: 'bg-warning text-dark',
        2: 'bg-success',
        1: 'bg-secondary',
        0: 'bg-secondary'
    }
    item_css_global = {item_id: PRIO_TO_CSS.get(prio, 'bg-secondary') for item_id, prio in item_pior_global.items()}

    cronograma_planejado = defaultdict(list)
    cronograma_ajustado = defaultdict(list)

    for agenda in agendas_qs:
        agenda.condensed_items = get_condensed_items(agenda.itens_norma.all())
        # Anexa css_class a cada item condensado refletindo a avaliação do item na auditoria
        for ci in agenda.condensed_items:
            ci.css_class = item_css_global.get(ci.id, 'bg-secondary')
        cronograma_planejado[agenda.data].append(agenda)
        data_ajustada = agenda.data_real or agenda.data
        cronograma_ajustado[data_ajustada].append(agenda)
        
    def format_reps(rep_str):
        items = [x.strip() for x in (rep_str or "").replace('\n', ',').split(',') if x.strip()]
        return sorted(items)
        
    def inject_gaps(agendas_list, is_ajustado=False, is_first_day=False, is_last_day=False):
        import datetime
        result = []
        prev_fim = None
        last_data = None
        
        has_abertura_in_list = any('abertura' in (a.titulo or '').lower() for a in agendas_list)
        has_encerramento_in_list = any('encerramento' in (a.titulo or '').lower() for a in agendas_list)
        has_revisao_in_list = any('revisão' in (a.titulo or '').lower() or 'revisao' in (a.titulo or '').lower() for a in agendas_list)

        for i, a in enumerate(agendas_list):
            inicio = a.hora_inicio_real if is_ajustado and a.hora_inicio_real else a.hora_inicio
            fim = a.hora_fim_real if is_ajustado and a.hora_fim_real else a.hora_fim
            data = a.data_real if is_ajustado and a.data_real else a.data
            last_data = data
            
            if is_first_day and i == 0 and inicio and not has_abertura_in_list:
                inicio_dt = datetime.datetime.combine(datetime.date.today(), inicio)
                abertura_inicio = (inicio_dt - datetime.timedelta(minutes=30)).time()
                rep_str = getattr(auditoria, 'abertura_representantes', '') or 'Todos'
                result.append({
                    'is_gap': True,
                    'special_type': 'abertura',
                    'auditores_nomes': getattr(auditoria, 'abertura_auditores', '') or 'Equipe',
                    'representantes': rep_str,
                    'representantes_list': format_reps(rep_str),
                    'hora_inicio': abertura_inicio,
                    'hora_fim': inicio,
                    'titulo': 'Reunião de Abertura',
                    'data': data
                })
            
            if prev_fim and inicio and inicio > prev_fim:
                result.append({
                    'is_gap': True,
                    'hora_inicio': prev_fim,
                    'hora_fim': inicio,
                    'titulo': 'Intervalo',
                    'data': data
                })
            
            # Anota se a agenda é um intervalo ou cerimônia especial
            tit_lower = (a.titulo or '').lower()
            if 'abertura' in tit_lower:
                a.special_type = 'abertura'
                a.is_intervalo = True
            elif 'encerramento' in tit_lower:
                a.special_type = 'encerramento'
                a.is_intervalo = True
            elif 'revisão' in tit_lower or 'revisao' in tit_lower:
                a.special_type = 'revisao'
                a.is_intervalo = True
            elif 'intervalo' in tit_lower or 'almoço' in tit_lower or 'almoco' in tit_lower or 'pausa' in tit_lower or 'coffee' in tit_lower:
                a.is_intervalo = True

            a.representantes_list = format_reps(a.representantes)
            result.append(a)
            if fim:
                prev_fim = fim
                
        if is_last_day and prev_fim and last_data:
            prev_fim_dt = datetime.datetime.combine(datetime.date.today(), prev_fim)
            
            if not has_revisao_in_list:
                revisao_fim_dt = prev_fim_dt + datetime.timedelta(hours=1, minutes=30)
                rep_str_rev = getattr(auditoria, 'revisao_representantes', '') or 'Equipe'
                result.append({
                    'is_gap': True,
                    'special_type': 'revisao',
                    'auditores_nomes': getattr(auditoria, 'revisao_auditores', '') or 'Equipe',
                    'representantes': rep_str_rev,
                    'representantes_list': format_reps(rep_str_rev),
                    'hora_inicio': prev_fim_dt.time(),
                    'hora_fim': revisao_fim_dt.time(),
                    'titulo': 'Revisão da Auditoria com Auditores',
                    'data': last_data
                })
                prev_fim_dt = revisao_fim_dt
            
            if not has_encerramento_in_list:
                encerramento_fim_dt = prev_fim_dt + datetime.timedelta(minutes=30)
                rep_str_enc = getattr(auditoria, 'encerramento_representantes', '') or 'Todos'
                result.append({
                    'is_gap': True,
                    'special_type': 'encerramento',
                    'auditores_nomes': getattr(auditoria, 'encerramento_auditores', '') or 'Equipe',
                    'representantes': rep_str_enc,
                    'representantes_list': format_reps(rep_str_enc),
                    'hora_inicio': prev_fim_dt.time(),
                    'hora_fim': encerramento_fim_dt.time(),
                    'titulo': 'Encerramento da auditoria',
                    'data': last_data
                })
            
        elif not is_last_day and prev_fim and last_data:
            result.append({
                'is_gap': True,
                'hora_inicio': prev_fim,
                'hora_fim': prev_fim,
                'titulo': 'Encerramento do Dia',
                'data': last_data
            })
            
        return result

    progresso_por_dia = {}
    planejado_com_gaps = {}
    datas_planejadas = sorted(cronograma_planejado.keys())
    primeira_data_planejada = datas_planejadas[0] if datas_planejadas else None
    ultima_data_planejada = datas_planejadas[-1] if datas_planejadas else None
    
    for data, agendas in cronograma_planejado.items():
        t = len(agendas)
        c = sum(1 for a in agendas if getattr(a, 'concluida', False))
        progresso_por_dia[data] = int((c / t) * 100) if t > 0 else 0
        is_first = (data == primeira_data_planejada)
        is_last = (data == ultima_data_planejada)
        planejado_com_gaps[data] = inject_gaps(agendas, is_ajustado=False, is_first_day=is_first, is_last_day=is_last)
        
    ajustado_com_gaps = {}
    datas_ajustadas = sorted(cronograma_ajustado.keys())
    primeira_data_ajustada = datas_ajustadas[0] if datas_ajustadas else None
    ultima_data_ajustada = datas_ajustadas[-1] if datas_ajustadas else None
    
    for data, agendas in sorted(cronograma_ajustado.items()):
        # Sort adjusted agendas by their actual start time
        agendas_sorted = sorted(agendas, key=lambda x: x.hora_inicio_real or x.hora_inicio or datetime.min.time())
        is_first = (data == primeira_data_ajustada)
        is_last = (data == ultima_data_ajustada)
        ajustado_com_gaps[data] = inject_gaps(agendas_sorted, is_ajustado=True, is_first_day=is_first, is_last_day=is_last)
        
    # Buscar todas as solicitações de evidências da auditoria
    sols_todas = SolicitacaoEvidenciaIso.objects.filter(
        resposta__auditoria=auditoria
    ).select_related(
        'resposta__pergunta', 'resposta__respondida_por'
    ).prefetch_related(
        'resposta__pergunta__itens_norma',
        'resposta__pergunta__agendas_vinculadas',
        'imagens'
    ).order_by('criado_em')

    # Filtrar solicitações em aberto (conclusão 'P' - Pendente)
    solicitacoes_abertas = []
    # Filtrar solicitações tratadas com desvios (conclusão NC, OM, OBS)
    solicitacoes_com_desvios = []
    # Filtrar solicitações resolvidas e atendidas (conclusão C, NA)
    solicitacoes_atendidas = []

    for s in sols_todas:
        agendas_vinculadas = list(s.resposta.pergunta.agendas_vinculadas.filter(auditoria=auditoria, arquivada=False))
        primeira_agenda = s.agenda if s.agenda else (agendas_vinculadas[0] if agendas_vinculadas else None)
        itens_sorted = sorted(s.resposta.pergunta.itens_norma.all(), key=lambda it: natural_sort_key(it.referencia))

        imagens_list = []
        for img in s.imagens.all():
            imagens_list.append({
                'id': img.id,
                'url': img.url_imagem,
                'nome': img.nome_arquivo,
                'legenda': img.legenda or '',
            })

        evidencias_capa_list = []
        for ev in s.evidencias_capa.all():
            evidencias_capa_list.append({
                'id': ev.id,
                'url': ev.url_arquivo,
                'nome': ev.nome_arquivo,
                'tipo': ev.tipo_arquivo,
                'criado_em': ev.criado_em.strftime('%d/%m/%Y %H:%M')
            })

        item_dict = {
            'id': s.id,
            'solicitacao': s.solicitacao,
            'evidencia': s.evidencia,
            'conclusao': s.conclusao,
            'grau_nc': s.grau_nc,
            'criado_em': s.criado_em,
            'pergunta_id': s.resposta.pergunta_id,
            'pergunta_texto': s.resposta.pergunta.texto_pergunta,
            'itens_norma': itens_sorted,
            'itens_str': ", ".join(it.referencia for it in itens_sorted),
            'agenda': primeira_agenda,
            'agendas_vinculadas': agendas_vinculadas,
            'imagens': imagens_list,
            'imagens_json': json.dumps(imagens_list),
            # Campos CAPA
            'capa_status': s.capa_status or 'PENDENTE',
            'capa_status_display': s.get_capa_status_display(),
            'capa_causa_raiz': s.capa_causa_raiz or '',
            'capa_acao_corretiva': s.capa_acao_corretiva or '',
            'capa_responsavel': s.capa_responsavel or '',
            'capa_prazo': s.capa_prazo.strftime('%Y-%m-%d') if s.capa_prazo else '',
            'capa_prazo_display': s.capa_prazo.strftime('%d/%m/%Y') if s.capa_prazo else '',
            'capa_respondido_em': s.capa_respondido_em.strftime('%d/%m/%Y %H:%M') if s.capa_respondido_em else '',
            'capa_respondido_por_nome': s.capa_respondido_por_nome or '',
            'capa_parecer_auditor': s.capa_parecer_auditor or '',
            'evidencias_capa': evidencias_capa_list,
        }

        if s.conclusao == 'P':
            solicitacoes_abertas.append(item_dict)
        elif s.conclusao in ['NC', 'OM', 'OBS']:
            solicitacoes_com_desvios.append(item_dict)
        elif s.conclusao in ['C', 'NA']:
            solicitacoes_atendidas.append(item_dict)

    total_solicitacoes_todas = sols_todas.count()
    total_solicitacoes_abertas = len(solicitacoes_abertas)
    total_solicitacoes_desvios = len(solicitacoes_com_desvios)
    total_desvios_nc = sum(1 for s in solicitacoes_com_desvios if s['conclusao'] == 'NC')
    total_desvios_om = sum(1 for s in solicitacoes_com_desvios if s['conclusao'] == 'OM')
    total_desvios_obs = sum(1 for s in solicitacoes_com_desvios if s['conclusao'] == 'OBS')

    # Métricas de CAPA
    total_capa_pendentes = sum(1 for s in solicitacoes_com_desvios if s['capa_status'] == 'PENDENTE')
    total_capa_aguardando = sum(1 for s in solicitacoes_com_desvios if s['capa_status'] == 'AGUARDANDO_REVISAO')
    total_capa_aprovados = sum(1 for s in solicitacoes_com_desvios if s['capa_status'] == 'APROVADO')
    total_capa_rejeitados = sum(1 for s in solicitacoes_com_desvios if s['capa_status'] == 'REJEITADO')

    total_solicitacoes_atendidas = len(solicitacoes_atendidas)
    total_atendidas_c = sum(1 for s in solicitacoes_atendidas if s['conclusao'] == 'C')
    total_atendidas_na = sum(1 for s in solicitacoes_atendidas if s['conclusao'] == 'NA')

    itens_norma_todos = ItemNorma.objects.filter(norma=auditoria.norma).order_by('referencia')
    if not itens_norma_todos.exists():
        itens_norma_todos = ItemNorma.objects.all().order_by('referencia')

    pontos_fortes_qs = list(auditoria.pontos_fortes.all().order_by('ordem', 'id'))
    agendas_auditoria_list = list(auditoria.agendas.filter(arquivada=False).order_by('titulo'))

    context = {
        'auditoria': auditoria,
        'agendas_auditoria': agendas_auditoria_list,
        'cronograma_planejado': planejado_com_gaps,
        'cronograma_ajustado': ajustado_com_gaps,
        'progresso_geral': progresso_geral,
        'progresso_por_dia': progresso_por_dia,
        'solicitacoes_abertas': solicitacoes_abertas,
        'total_solicitacoes_abertas': total_solicitacoes_abertas,
        'solicitacoes_com_desvios': solicitacoes_com_desvios,
        'total_solicitacoes_desvios': total_solicitacoes_desvios,
        'total_desvios_nc': total_desvios_nc,
        'total_desvios_om': total_desvios_om,
        'total_desvios_obs': total_desvios_obs,
        'total_capa_pendentes': total_capa_pendentes,
        'total_capa_aguardando': total_capa_aguardando,
        'total_capa_aprovados': total_capa_aprovados,
        'total_capa_rejeitados': total_capa_rejeitados,
        'solicitacoes_atendidas': solicitacoes_atendidas,
        'total_solicitacoes_atendidas': total_solicitacoes_atendidas,
        'total_atendidas_c': total_atendidas_c,
        'total_atendidas_na': total_atendidas_na,
        'total_solicitacoes_todas': total_solicitacoes_todas,
        'itens_norma_todos': itens_norma_todos,
        'pontos_fortes_catalogo': PONTOS_FORTES_CATALOGO,
        'pontos_fortes_todos': pontos_fortes_qs,
    }

    return render(request, 'auditoria/iso/setup/cronograma_impressao.html', context)

@login_required
@require_POST
def iso_agenda_toggle_conclusao(request, auditoria_id, pk):
    from .models import AgendaAuditoriaIso
    agenda = get_object_or_404(AgendaAuditoriaIso, auditoria_id=auditoria_id, pk=pk)
    agenda.concluida = not agenda.concluida
    agenda.save()
    messages.success(request, f"Status da etapa '{agenda.titulo}' atualizado.")
    return redirect('auditoria:iso_auditoria_cronograma', auditoria_id=auditoria_id)

@login_required
@require_POST
def iso_auditoria_toggle_conclusao(request, auditoria_id):
    from .models import AuditoriaIso
    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    if auditoria.status == "CONCLUIDA":
        auditoria.status = "EM_ANDAMENTO"
        messages.info(request, f"Status da auditoria '{auditoria.norma.codigo}' alterado para Em Andamento.")
    else:
        auditoria.status = "CONCLUIDA"
        messages.success(request, f"Auditoria '{auditoria.norma.codigo}' marcada como Concluída com sucesso!")
    auditoria.save()
    return redirect('auditoria:iso_auditoria_cronograma', auditoria_id=auditoria_id)

@login_required
@require_POST
def api_iso_agenda_quick_edit(request, auditoria_id):
    from .models import AgendaAuditoriaIso, AuditoriaIso
    from django.http import JsonResponse
    
    agenda_id = request.POST.get('agenda_id')
    aplicar_todos = request.POST.get('aplicar_todos') == 'true'
    tipo = request.POST.get('tipo')
    
    if agenda_id in ['abertura', 'revisao', 'encerramento']:
        auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
        if tipo == 'auditor':
            valor = request.POST.get('auditores_nomes', '')
            setattr(auditoria, f"{agenda_id}_auditores", valor)
            auditoria.save(update_fields=[f"{agenda_id}_auditores"])
        elif tipo == 'representante':
            valor = request.POST.get('representantes', '')
            setattr(auditoria, f"{agenda_id}_representantes", valor)
            auditoria.save(update_fields=[f"{agenda_id}_representantes"])
        return JsonResponse({'success': True, 'message': 'Preenchimento rápido salvo com sucesso.'})

    agendas_para_atualizar = []
    if aplicar_todos:
        agendas_para_atualizar = list(AgendaAuditoriaIso.objects.filter(auditoria_id=auditoria_id))
    else:
        agenda = get_object_or_404(AgendaAuditoriaIso, auditoria_id=auditoria_id, pk=agenda_id)
        agendas_para_atualizar = [agenda]
    
    if tipo == 'auditor':
        valor = request.POST.get('auditores_nomes', '')
        for ag in agendas_para_atualizar:
            ag.auditores_nomes = valor
            ag.save(update_fields=['auditores_nomes'])
    elif tipo == 'representante':
        valor = request.POST.get('representantes', '')
        for ag in agendas_para_atualizar:
            ag.representantes = valor
            ag.save(update_fields=['representantes'])
            
    return JsonResponse({'success': True, 'message': 'Preenchimento rápido salvo com sucesso.'})

@login_required
@require_POST
def api_iso_agenda_ajustar_horario(request, auditoria_id):
    """
    Salva o ajuste dinâmico de cronograma na Visão Real/Ajustada.
    Permite alterar data_real, hora_inicio_real, hora_fim_real ou restaurar ao planejado.
    """
    from .models import AgendaAuditoriaIso, AuditoriaIso
    from django.http import JsonResponse
    from datetime import datetime

    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    agenda_id = request.POST.get('agenda_id')
    restaurar_planejado = request.POST.get('restaurar_planejado') == 'true'

    if agenda_id in ['abertura', 'revisao', 'encerramento']:
        return JsonResponse({'success': True, 'message': 'Evento de cerimônia mantido.'})

    agenda = get_object_or_404(AgendaAuditoriaIso, auditoria=auditoria, pk=agenda_id)

    if restaurar_planejado:
        agenda.data_real = None
        agenda.hora_inicio_real = None
        agenda.hora_fim_real = None
        agenda.save(update_fields=['data_real', 'hora_inicio_real', 'hora_fim_real'])
        return JsonResponse({'success': True, 'message': 'Horário restaurado para a previsão planejada.'})

    data_real_str = request.POST.get('data_real', '').strip()
    hora_inicio_real_str = request.POST.get('hora_inicio_real', '').strip()
    hora_fim_real_str = request.POST.get('hora_fim_real', '').strip()
    marcar_concluida = request.POST.get('marcar_concluida') == 'true'

    if data_real_str:
        try:
            agenda.data_real = datetime.strptime(data_real_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    if hora_inicio_real_str:
        try:
            agenda.hora_inicio_real = datetime.strptime(hora_inicio_real_str, '%H:%M').time()
        except ValueError:
            pass
    elif hora_inicio_real_str == '':
        agenda.hora_inicio_real = None

    if hora_fim_real_str:
        try:
            agenda.hora_fim_real = datetime.strptime(hora_fim_real_str, '%H:%M').time()
        except ValueError:
            pass
    elif hora_fim_real_str == '':
        agenda.hora_fim_real = None

    if marcar_concluida:
        agenda.concluida = True

    agenda.save()
    return JsonResponse({'success': True, 'message': 'Horário ajustado com sucesso no cronograma real.'})

@login_required
@require_POST
def api_iso_agenda_criar_ajustada(request, auditoria_id):
    """
    Cria uma nova atividade/etapa dinâmica diretamente no cronograma ajustado.
    """
    from .models import AgendaAuditoriaIso, AuditoriaIso, ItemNorma
    from datetime import datetime

    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    titulo = request.POST.get('titulo', '').strip()
    if not titulo:
        messages.error(request, 'O título da atividade ajustada é obrigatório.')
        return redirect('auditoria:iso_auditoria_cronograma', auditoria_id=auditoria_id)

    data_str = request.POST.get('data_real', '').strip()
    hora_inicio_str = request.POST.get('hora_inicio_real', '').strip()
    hora_fim_str = request.POST.get('hora_fim_real', '').strip()
    auditores_nomes = request.POST.get('auditores_nomes', '').strip()
    representantes = request.POST.get('representantes', '').strip()
    itens_ids = request.POST.getlist('itens_norma')

    data_obj = None
    if data_str:
        try:
            data_obj = datetime.strptime(data_str, '%Y-%m-%d').date()
        except ValueError:
            data_obj = auditoria.data_inicio
    else:
        data_obj = auditoria.data_inicio

    hora_inicio_obj = None
    if hora_inicio_str:
        try:
            hora_inicio_obj = datetime.strptime(hora_inicio_str, '%H:%M').time()
        except ValueError:
            pass

    hora_fim_obj = None
    if hora_fim_str:
        try:
            hora_fim_obj = datetime.strptime(hora_fim_str, '%H:%M').time()
        except ValueError:
            pass

    nova_agenda = AgendaAuditoriaIso.objects.create(
        auditoria=auditoria,
        titulo=titulo,
        data=data_obj,
        data_real=data_obj,
        hora_inicio=hora_inicio_obj,
        hora_inicio_real=hora_inicio_obj,
        hora_fim=hora_fim_obj,
        hora_fim_real=hora_fim_obj,
        auditores_nomes=auditores_nomes,
        representantes=representantes,
    )

    if itens_ids:
        itens = ItemNorma.objects.filter(id__in=itens_ids, norma=auditoria.norma)
        nova_agenda.itens_norma.set(itens)

    messages.success(request, f"Atividade '{titulo}' adicionada ao cronograma ajustado.")
    return redirect('auditoria:iso_auditoria_cronograma', auditoria_id=auditoria_id)

@login_required
@require_POST
def api_iso_agenda_excluir_ajustada(request, auditoria_id, pk):
    """
    Remove uma atividade do cronograma.
    """
    from .models import AgendaAuditoriaIso, AuditoriaIso
    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    agenda = get_object_or_404(AgendaAuditoriaIso, auditoria=auditoria, pk=pk)
    titulo = agenda.titulo
    agenda.delete()
    messages.success(request, f"Atividade '{titulo}' removida do cronograma.")
    return redirect('auditoria:iso_auditoria_cronograma', auditoria_id=auditoria_id)

@login_required
@require_POST
def api_iso_agenda_create_gap(request, auditoria_id):
    from .models import AuditoriaIso, AgendaAuditoriaIso
    from datetime import datetime
    
    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    titulo = request.POST.get('titulo')
    data_str = request.POST.get('data')
    hora_inicio_str = request.POST.get('hora_inicio')
    hora_fim_str = request.POST.get('hora_fim')
    is_ajustado = request.POST.get('is_ajustado') == '1'
    
    data_obj = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else None
    hora_inicio_obj = datetime.strptime(hora_inicio_str, '%H:%M').time() if hora_inicio_str else None
    hora_fim_obj = datetime.strptime(hora_fim_str, '%H:%M').time() if hora_fim_str else None
    
    nova_agenda = AgendaAuditoriaIso(
        auditoria=auditoria,
        titulo=titulo,
    )
    
    if is_ajustado:
        nova_agenda.data = data_obj
        nova_agenda.data_real = data_obj
        nova_agenda.hora_inicio_real = hora_inicio_obj
        nova_agenda.hora_fim_real = hora_fim_obj
    else:
        nova_agenda.data = data_obj
        nova_agenda.hora_inicio = hora_inicio_obj
        nova_agenda.hora_fim = hora_fim_obj
        
    nova_agenda.save()
    
    messages.success(request, f'Bloco {titulo} criado com sucesso para o intervalo.')
    return redirect('auditoria:iso_auditoria_cronograma', auditoria_id=auditoria_id)


@login_required
@require_POST
def api_iso_agenda_salvar_intervalo_evento(request, auditoria_id):
    """
    Cria ou atualiza um Intervalo ou Evento Especial (Abertura, Revisão, Encerramento, Almoço, etc.)
    com suporte a:
    - Definição de duração (ex: 15, 30, 45, 60, 90 min)
    - Encaixe dinâmico após um bloco selecionado (ou antes do primeiro / após o último)
    - Deslocamento e reajuste automático dos blocos seguintes no mesmo dia (cascata inteligente)
    """
    from .models import AgendaAuditoriaIso, AuditoriaIso
    from django.http import JsonResponse
    from datetime import datetime, date, timedelta, time
    import json

    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)

    # Processa dados enviados via JSON ou FormData
    if request.content_type == 'application/json':
        try:
            data_body = json.loads(request.body.decode('utf-8'))
        except Exception:
            data_body = {}
    else:
        data_body = request.POST

    agenda_id = data_body.get('agenda_id')
    special_type = data_body.get('special_type')
    titulo = (data_body.get('titulo') or 'Intervalo').strip()
    data_str = data_body.get('data')
    hora_inicio_str = data_body.get('hora_inicio')
    hora_fim_str = data_body.get('hora_fim')
    duracao_minutos = data_body.get('duracao_minutos')
    is_ajustado = str(data_body.get('is_ajustado')).lower() in ['true', '1']
    reajustar_proximos = str(data_body.get('reajustar_proximos')).lower() in ['true', '1', 'on']
    auditores_nomes = data_body.get('auditores_nomes', '')
    representantes = data_body.get('representantes', '')

    if not data_str:
        return JsonResponse({'success': False, 'error': 'Data é obrigatória.'}, status=400)

    try:
        data_obj = datetime.strptime(data_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Formato de data inválido.'}, status=400)

    # Resolve horários de início e término
    hora_ini_obj = None
    hora_fim_obj = None
    if hora_inicio_str:
        try:
            hora_ini_obj = datetime.strptime(hora_inicio_str, '%H:%M').time()
        except ValueError:
            pass

    if hora_fim_str:
        try:
            hora_fim_obj = datetime.strptime(hora_fim_str, '%H:%M').time()
        except ValueError:
            pass

    if hora_ini_obj and not hora_fim_obj and duracao_minutos:
        try:
            dur_int = int(duracao_minutos)
            dt_ini = datetime.combine(data_obj, hora_ini_obj)
            dt_fim = dt_ini + timedelta(minutes=dur_int)
            hora_fim_obj = dt_fim.time()
        except (ValueError, TypeError):
            pass

    if not hora_ini_obj or not hora_fim_obj:
        return JsonResponse({'success': False, 'error': 'Horários de início e término são obrigatórios.'}, status=400)

    # Se for tipo especial de cerimônia, atualiza metadados da auditoria se aplicável
    if special_type == 'abertura' or 'abertura' in titulo.lower():
        if auditores_nomes:
            auditoria.abertura_auditores = auditores_nomes
        if representantes:
            auditoria.abertura_representantes = representantes
        auditoria.save(update_fields=['abertura_auditores', 'abertura_representantes'])
    elif special_type == 'revisao' or 'revisão' in titulo.lower() or 'revisao' in titulo.lower():
        if auditores_nomes:
            auditoria.revisao_auditores = auditores_nomes
        if representantes:
            auditoria.revisao_representantes = representantes
        auditoria.save(update_fields=['revisao_auditores', 'revisao_representantes'])
    elif special_type == 'encerramento' or 'encerramento' in titulo.lower():
        if auditores_nomes:
            auditoria.encerramento_auditores = auditores_nomes
        if representantes:
            auditoria.encerramento_representantes = representantes
        auditoria.save(update_fields=['encerramento_auditores', 'encerramento_representantes'])

    # Verifica se já existe uma agenda vinculada (seja por id ou por mesmo título/data)
    agenda = None
    if agenda_id and str(agenda_id).isdigit():
        agenda = AgendaAuditoriaIso.objects.filter(auditoria=auditoria, pk=agenda_id).first()

    if not agenda:
        # Se não informou ID, procura se já existe agenda para esse evento nesse dia
        agenda = AgendaAuditoriaIso.objects.filter(auditoria=auditoria, data=data_obj, titulo=titulo).first()

    if agenda:
        agenda.titulo = titulo
        if is_ajustado:
            agenda.data_real = data_obj
            agenda.hora_inicio_real = hora_ini_obj
            agenda.hora_fim_real = hora_fim_obj
        else:
            agenda.data = data_obj
            agenda.hora_inicio = hora_ini_obj
            agenda.hora_fim = hora_fim_obj
            agenda.data_real = data_obj
            agenda.hora_inicio_real = hora_ini_obj
            agenda.hora_fim_real = hora_fim_obj

        if auditores_nomes:
            agenda.auditores_nomes = auditores_nomes
        if representantes:
            agenda.representantes = representantes
        agenda.save()
    else:
        agenda = AgendaAuditoriaIso.objects.create(
            auditoria=auditoria,
            titulo=titulo,
            data=data_obj,
            data_real=data_obj,
            hora_inicio=hora_ini_obj,
            hora_inicio_real=hora_ini_obj,
            hora_fim=hora_fim_obj,
            hora_fim_real=hora_fim_obj,
            auditores_nomes=auditores_nomes,
            representantes=representantes
        )

    # Reajuste em cascata dos blocos subsequentes no mesmo dia (Smart Cascade)
    if reajustar_proximos:
        if is_ajustado:
            outras = list(AgendaAuditoriaIso.objects.filter(
                auditoria=auditoria,
                data_real=data_obj
            ).exclude(pk=agenda.pk).order_by('hora_inicio_real', 'hora_inicio', 'id'))
        else:
            outras = list(AgendaAuditoriaIso.objects.filter(
                auditoria=auditoria,
                data=data_obj
            ).exclude(pk=agenda.pk).order_by('hora_inicio', 'id'))

        cursor_fim_dt = datetime.combine(data_obj, hora_fim_obj)

        for ag in outras:
            ag_ini = (ag.hora_inicio_real if is_ajustado and ag.hora_inicio_real else ag.hora_inicio)
            ag_fim = (ag.hora_fim_real if is_ajustado and ag.hora_fim_real else ag.hora_fim)

            if not ag_ini or not ag_fim:
                continue

            ag_ini_dt = datetime.combine(data_obj, ag_ini)
            ag_fim_dt = datetime.combine(data_obj, ag_fim)
            duracao_bloco = ag_fim_dt - ag_ini_dt
            if duracao_bloco.total_seconds() <= 0:
                duracao_bloco = timedelta(minutes=60)

            # Se o bloco começa antes de onde o intervalo terminou e sua hora original é >= início do intervalo
            if ag_ini_dt < cursor_fim_dt and ag_ini_dt >= datetime.combine(data_obj, hora_ini_obj):
                novo_ini_dt = cursor_fim_dt
                novo_fim_dt = novo_ini_dt + duracao_bloco

                if is_ajustado:
                    ag.hora_inicio_real = novo_ini_dt.time()
                    ag.hora_fim_real = novo_fim_dt.time()
                    ag.save(update_fields=['hora_inicio_real', 'hora_fim_real'])
                else:
                    ag.hora_inicio = novo_ini_dt.time()
                    ag.hora_fim = novo_fim_dt.time()
                    ag.hora_inicio_real = novo_ini_dt.time()
                    ag.hora_fim_real = novo_fim_dt.time()
                    ag.save(update_fields=['hora_inicio', 'hora_fim', 'hora_inicio_real', 'hora_fim_real'])

                cursor_fim_dt = novo_fim_dt
            elif ag_ini_dt >= cursor_fim_dt:
                cursor_fim_dt = max(cursor_fim_dt, ag_fim_dt)

    return JsonResponse({
        'success': True,
        'message': f"'{titulo}' atualizado com sucesso no cronograma.",
        'agenda_id': agenda.id
    })







@login_required
def iso_revisao_dashboard(request, auditoria_id):
    from .models import AuditoriaIso, RespostaEntrevistaIso, AgendaAuditoriaIso, ItemNorma, AvaliacaoFinalRequisitoIso
    from collections import defaultdict
    
    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    
    respostas = RespostaEntrevistaIso.objects.filter(
        auditoria=auditoria
    ).exclude(
        classificacao='NA'
    ).select_related('pergunta').prefetch_related('solicitacoes', 'pergunta__itens_norma')
    
    agendas = AgendaAuditoriaIso.objects.filter(auditoria=auditoria).prefetch_related('perguntas')
    
    pergunta_agendas_map = defaultdict(list)
    for agenda in agendas:
        for p in agenda.perguntas.all():
            pergunta_agendas_map[p.id].append(agenda)
            
    avaliacoes_finais = {
        av.item_norma_id: av
        for av in AvaliacaoFinalRequisitoIso.objects.filter(auditoria=auditoria)
    }
                
    # Agrupamento por ItemNorma
    itens_map = {}
    
    for resp in respostas:
        resp.agendas_avaliadas = pergunta_agendas_map.get(resp.pergunta.id, [])
        
        # Uma resposta pode pertencer a vários itens da norma
        for item in resp.pergunta.itens_norma.all():
            if item.id not in itens_map:
                itens_map[item.id] = {
                    'item': item,
                    'respostas': [],
                    'pior_status': 'C',
                    'grau_nc_selecionado': None,
                    'justificativa_final': '',
                    'sugestao_ia': None,
                }
            itens_map[item.id]['respostas'].append(resp)
            
            # Atualiza o pior status bruto (P > NC > OM > OBS > C)
            peso = {'P': 5, 'NC': 4, 'OM': 3, 'OBS': 2, 'C': 1}
            status_atual = itens_map[item.id]['pior_status']
            
            # Status da resposta
            novo_status = resp.classificacao
            if peso.get(novo_status, 0) > peso.get(status_atual, 0):
                itens_map[item.id]['pior_status'] = novo_status
                status_atual = novo_status

            # Status das solicitações/amostragens vinculadas
            for sol in resp.solicitacoes.all():
                if peso.get(sol.conclusao, 0) > peso.get(status_atual, 0):
                    itens_map[item.id]['pior_status'] = sol.conclusao
                    status_atual = sol.conclusao

    # Sobrescreve com avaliação final e calcula Heurística de Risco (Motor de Sugestão de NC)
    for item_id, data in itens_map.items():
        if item_id in avaliacoes_finais:
            av = avaliacoes_finais[item_id]
            data['pior_status'] = av.classificacao
            data['grau_nc_selecionado'] = av.grau_nc
            data['justificativa_final'] = av.justificativa

        # Coleta todas as solicitações/amostragens deste requisito
        todas_solicitacoes = []
        for r in data['respostas']:
            todas_solicitacoes.extend(list(r.solicitacoes.all()))

        # Cálculo da Heurística de Sugestão Inteligente
        T = len(todas_solicitacoes)
        F = sum(1 for s in todas_solicitacoes if s.conclusao == 'NC')
        
        if T == 0:
            # Sem solicitações cadastradas, avalia pelas respostas brutas
            nc_resps = sum(1 for r in data['respostas'] if r.classificacao == 'NC')
            tot_resps = len(data['respostas'])
            if tot_resps <= 1 or (tot_resps > 0 and (nc_resps / tot_resps) >= 0.5):
                grau_sugestao = 'MAIOR'
                taxa_pct = round((nc_resps / max(tot_resps, 1)) * 100)
                justificativa = "A ausência de evidências ou reprovação na totalidade dos blocos indica ausência ou colapso sistêmico do controle normativo."
            else:
                grau_sugestao = 'MENOR'
                taxa_pct = round((nc_resps / max(tot_resps, 1)) * 100)
                justificativa = f"Apenas {nc_resps} de {tot_resps} blocos apresentaram apontamento ({taxa_pct}% de falha), caracterizando desvio pontual."
        else:
            taxa_falha = F / T
            taxa_pct = round(taxa_falha * 100)
            
            if (T == 1 and F == 1) or taxa_falha >= 0.5:
                grau_sugestao = 'MAIOR'
                justificativa = f"Foram avaliadas {T} amostra(s) neste requisito e {F} falharam ({taxa_pct}% de falha). A ausência da única evidência requerida ou taxa de reprovação ≥ 50% indica colapso sistêmico do controle e quebra de conformidade estrutural."
            else:
                grau_sugestao = 'MENOR'
                justificativa = f"Foram avaliadas {T} amostras neste requisito, e apenas {F} falhou ({taxa_pct}% de falha). O processo estrutural se mantém funcional na maioria dos registros, caracterizando desvio pontual."

        data['sugestao_ia'] = {
            'grau': grau_sugestao,
            'total_amostras': T,
            'total_falhas': F,
            'taxa_pct': taxa_pct,
            'justificativa': justificativa
        }

        # Se for NC e ainda não tiver grau selecionado, default para a sugestão
        if data['pior_status'] == 'NC' and not data['grau_nc_selecionado']:
            data['grau_nc_selecionado'] = grau_sugestao
                
    # Converte dicionário em lista ordenada
    blocos = []
    for item_id, data in sorted(itens_map.items(), key=lambda x: natural_sort_key(x[1]['item'].referencia)):
        blocos.append(data)

    todos_itens_norma = list(ItemNorma.objects.filter(norma=auditoria.norma).order_by('ordem', 'referencia'))
        
    context = {
        'auditoria': auditoria,
        'blocos': blocos,
        'agendas': agendas,
        'todos_itens_norma': todos_itens_norma,
    }
    
    return render(request, 'auditoria/iso/revisao_dashboard.html', context)


@login_required
@require_POST
def api_iso_revisao_criar_obs(request):
    """
    Registra uma nova Observação com Correção (Conselho/Recomendação Prática)
    a partir da Reunião de Fechamento / Revisão de Auditoria.
    """
    import json
    from django.http import JsonResponse
    from .models import ItemNorma, AuditoriaIso, SolicitacaoEvidenciaIso, RespostaEntrevistaIso, PerguntaIso, AgendaAuditoriaIso, AvaliacaoFinalRequisitoIso
    
    try:
        data = json.loads(request.body)
        auditoria_id = data.get('auditoria_id')
        item_norma_id = data.get('item_norma_id')
        solicitacao_txt = data.get('solicitacao', '').strip() or "Observação com Correção (Reunião de Auditores)"
        evidencia_txt = data.get('evidencia', '').strip()
        agenda_id = data.get('agenda_id')
        
        if not item_norma_id:
            return JsonResponse({'success': False, 'message': 'Selecione o Requisito / Item da Norma.'}, status=400)
        if not evidencia_txt:
            return JsonResponse({'success': False, 'message': 'Descreva o conteúdo da recomendação / observação com correção.'}, status=400)
            
        auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
        item_norma = get_object_or_404(ItemNorma, pk=item_norma_id)
        
        agenda = None
        if agenda_id and str(agenda_id).strip().isdigit():
            agenda = AgendaAuditoriaIso.objects.filter(pk=int(agenda_id), auditoria=auditoria).first()

        # Encontra ou cria uma resposta de entrevista para este item
        resp = RespostaEntrevistaIso.objects.filter(
            auditoria=auditoria,
            pergunta__itens_norma=item_norma
        ).first()

        if not resp:
            pergunta = PerguntaIso.objects.filter(itens_norma=item_norma).first()
            if not pergunta:
                pergunta = PerguntaIso.objects.create(
                    texto_pergunta=f"Avaliação do Requisito {item_norma.referencia}",
                    ordem=1
                )
                pergunta.itens_norma.add(item_norma)

            resp, _ = RespostaEntrevistaIso.objects.get_or_create(
                auditoria=auditoria,
                pergunta=pergunta,
                defaults={'classificacao': 'C'}
            )

        # Cria a solicitação como OBS
        sol = SolicitacaoEvidenciaIso.objects.create(
            resposta=resp,
            agenda=agenda,
            solicitacao=solicitacao_txt,
            evidencia=evidencia_txt,
            conclusao='OBS'
        )

        # Atualiza a avaliação final do requisito se ainda não tiver veredicto definido
        av_existente = AvaliacaoFinalRequisitoIso.objects.filter(auditoria=auditoria, item_norma=item_norma).first()
        if not av_existente:
            AvaliacaoFinalRequisitoIso.objects.create(
                auditoria=auditoria,
                item_norma=item_norma,
                classificacao='OBS',
                justificativa=f"Observação com Correção adicionada na reunião de revisão: {solicitacao_txt}",
                atualizado_por=request.user if request.user.is_authenticated else None
            )

        return JsonResponse({
            'success': True,
            'message': f'Observação com Correção registrada com sucesso para o Item {item_norma.referencia}.',
            'solicitacao_id': sol.id
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': str(e)}, status=400)


@login_required
@require_POST
def api_iso_revisao_reverter(request):
    import json
    from django.http import JsonResponse
    from .models import ItemNorma, AvaliacaoFinalRequisitoIso, AuditoriaIso
    
    try:
        data = json.loads(request.body)
        item_norma_id = data.get('item_norma_id')
        auditoria_id = data.get('auditoria_id')
        novo_status = data.get('novo_status')
        grau_nc = data.get('grau_nc')  # 'MENOR' | 'MAIOR' | None
        argumentacao = data.get('argumentacao', '').strip()
        
        item_norma = get_object_or_404(ItemNorma, pk=item_norma_id)
        auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
        
        avaliacao, created = AvaliacaoFinalRequisitoIso.objects.update_or_create(
            auditoria=auditoria,
            item_norma=item_norma,
            defaults={
                'classificacao': novo_status,
                'grau_nc': grau_nc if novo_status == 'NC' else None,
                'justificativa': argumentacao,
                'atualizado_por': request.user if request.user.is_authenticated else None
            }
        )
            
        return JsonResponse({
            'success': True, 
            'message': 'Status final e gravidade atualizados com sucesso.', 
            'novo_status': novo_status,
            'grau_nc': grau_nc
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': str(e)}, status=400)


@login_required
def iso_auditoria_sintese_wizard(request, auditoria_id):
    """
    TELA DE REPASSE E SÍNTESE (WIZARD DO AUDITOR)
    Permite ao auditor navegar pelas Seções da Norma, visualizar as falhas/gaps daquela seção
    e redigir Notas Livres / Síntese específica com editor WYSIWYG completo.
    """
    from collections import defaultdict
    from .models import (
        AuditoriaIso, ItemNorma, RespostaEntrevistaIso,
        AvaliacaoFinalRequisitoIso, SinteseSecaoAuditoriaIso
    )

    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    itens_escopo = list(auditoria.escopo_itens.all().order_by('referencia'))
    
    if not itens_escopo:
        itens_escopo = list(ItemNorma.objects.filter(norma=auditoria.norma).order_by('referencia'))

    respostas = RespostaEntrevistaIso.objects.filter(auditoria=auditoria).prefetch_related(
        'solicitacoes', 'solicitacoes__imagens', 'pergunta__itens_norma'
    )
    respostas_map = {r.pergunta_id: r for r in respostas}
    avaliacoes_finais = {av.item_norma_id: av for av in AvaliacaoFinalRequisitoIso.objects.filter(auditoria=auditoria)}

    pergunta_itens_map = {}
    for ag in auditoria.agendas.all():
        for p in ag.perguntas.all():
            if p.id not in pergunta_itens_map:
                pergunta_itens_map[p.id] = set(it.id for it in p.itens_norma.all())

    secoes_dict = {}
    all_root_items = {it.referencia: it for it in ItemNorma.objects.filter(norma=auditoria.norma)}
    sinteses_salvas = {s.secao_referencia: s for s in auditoria.sinteses_secao.all()}

    for item in itens_escopo:
        ref_parts = item.referencia.split('.')
        sec_ref = ref_parts[0] if ref_parts else item.referencia
        
        if sec_ref not in secoes_dict:
            root_item = all_root_items.get(sec_ref)
            sec_titulo = root_item.titulo if root_item else f"Requisitos da Seção {sec_ref}"
            secoes_dict[sec_ref] = {
                'referencia': sec_ref,
                'titulo': sec_titulo,
                'nome_completo': f"Seção {sec_ref} - {sec_titulo}",
                'itens': [],
                'count_nc_maior': 0,
                'count_nc_menor': 0,
                'count_om': 0,
                'count_c': 0,
                'count_na': 0,
                'total_avaliados': 0,
                'gaps': [],
                'sintese_obj': sinteses_salvas.get(sec_ref),
                'conteudo_html': sinteses_salvas[sec_ref].conteudo_html if sec_ref in sinteses_salvas else "",
                'has_sintese': bool(sinteses_salvas.get(sec_ref) and sinteses_salvas[sec_ref].conteudo_html.strip()),
                'atualizado_em': sinteses_salvas[sec_ref].atualizado_em if sec_ref in sinteses_salvas else None,
            }

        sec_data = secoes_dict[sec_ref]
        sec_data['itens'].append(item)

        av_final = avaliacoes_finais.get(item.id)
        perguntas_do_item = [p_id for p_id, ids in pergunta_itens_map.items() if item.id in ids]
        sols_do_item = []
        for p_id in perguntas_do_item:
            r = respostas_map.get(p_id)
            if r:
                for s in r.solicitacoes.all():
                    sols_do_item.append(s)

        if av_final and av_final.classificacao:
            status = av_final.classificacao
            grau = av_final.grau_nc
            justif = av_final.justificativa
        elif sols_do_item:
            conclusoes = [s.conclusao for s in sols_do_item]
            if 'NC' in conclusoes:
                status = 'NC'
                grau = 'MAIOR' if any(s.grau_nc == 'MAIOR' for s in sols_do_item if s.conclusao == 'NC') else 'MENOR'
            elif 'OM' in conclusoes:
                status = 'OM'
                grau = None
            elif any(c == 'C' for c in conclusoes):
                status = 'C'
                grau = None
            elif all(c == 'NA' for c in conclusoes):
                status = 'NA'
                grau = None
            else:
                status = 'P'
                grau = None
            justif = ""
        else:
            status = 'C'
            grau = None
            justif = ""

        if status == 'NC':
            if grau == 'MAIOR':
                sec_data['count_nc_maior'] += 1
            else:
                sec_data['count_nc_menor'] += 1
        elif status == 'OM':
            sec_data['count_om'] += 1
        elif status == 'C':
            sec_data['count_c'] += 1
        elif status == 'NA':
            sec_data['count_na'] += 1

        sec_data['total_avaliados'] += 1

        if status in ['NC', 'OM']:
            sec_data['gaps'].append({
                'item_referencia': item.referencia,
                'item_titulo': item.titulo,
                'status': status,
                'grau': grau,
                'grau_label': "NC Maior" if grau == 'MAIOR' else ("NC Menor" if status == 'NC' else "Oportunidade de Melhoria"),
                'justificativa': justif,
                'solicitacoes': sols_do_item,
            })

    secoes_lista = sorted(secoes_dict.values(), key=lambda s: natural_sort_key(s['referencia']))

    for s in secoes_lista:
        s['total_gaps'] = s['count_nc_maior'] + s['count_nc_menor'] + s['count_om']

    secao_ativa_ref = request.GET.get('secao')
    secao_ativa = None
    if secao_ativa_ref:
        secao_ativa = next((s for s in secoes_lista if s['referencia'] == secao_ativa_ref), None)
    if not secao_ativa and secoes_lista:
        secao_ativa = secoes_lista[0]

    context = {
        'auditoria': auditoria,
        'secoes': secoes_lista,
        'secao_ativa': secao_ativa,
    }
    return render(request, 'auditoria/iso/sintese_wizard.html', context)


@login_required
@require_POST
def api_iso_sintese_salvar_secao(request, auditoria_id):
    """
    Salva a síntese / notas livres de uma seção específica da auditoria via JSON.
    """
    import json
    from django.http import JsonResponse
    from .models import AuditoriaIso, SinteseSecaoAuditoriaIso

    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    try:
        data = json.loads(request.body)
        secao_referencia = str(data.get('secao_referencia', '')).strip()
        secao_titulo = str(data.get('secao_titulo', '')).strip()
        conteudo_html = str(data.get('conteudo_html', '')).strip()

        if not secao_referencia:
            return JsonResponse({'success': False, 'error': 'Referência da seção obrigatória.'}, status=400)

        sintese, created = SinteseSecaoAuditoriaIso.objects.update_or_create(
            auditoria=auditoria,
            secao_referencia=secao_referencia,
            defaults={
                'secao_titulo': secao_titulo,
                'conteudo_html': conteudo_html,
                'atualizado_por': request.user if request.user.is_authenticated else None,
            }
        )

        return JsonResponse({
            'success': True,
            'secao_referencia': secao_referencia,
            'atualizado_em': sintese.atualizado_em.strftime('%d/%m/%Y %H:%M'),
            'message': f'Síntese da Seção {secao_referencia} salva com sucesso!'
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=400)




@login_required
def iso_gestao_amostras_view(request, auditoria_id):
    from django.shortcuts import render, get_object_or_404, redirect
    from .models import AuditoriaIso, SolicitacaoEvidenciaIso, AgendaAuditoriaIso
    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    
    # Check permissions
    if not _auditoria_is_admin(request.user) and not request.user.is_superuser:
        if not auditoria.agendas.filter(auditores=request.user).exists():
            return redirect("auditoria:iso_auditoria_list")
            
    agendas = auditoria.agendas.all().order_by('titulo')
    
    # Get all solicitacoes for this auditoria
    solicitacoes = SolicitacaoEvidenciaIso.objects.filter(
        resposta__auditoria=auditoria
    ).select_related('agenda', 'resposta__pergunta').order_by('agenda__titulo', 'solicitacao')
    
    return render(request, "auditoria/iso/gestao_amostras.html", {
        "auditoria": auditoria,
        "agendas": agendas,
        "solicitacoes": solicitacoes
    })


# ==============================================================================
# VIEWS: CAPA - PLANO DE AÇÃO & MAGIC LINK PÚBLICO
# ==============================================================================

@login_required
@require_POST
def api_iso_capa_gerar_link(request, auditoria_id):
    """Gera um novo Magic Link público de Plano de Ação para a auditoria ou setor específico."""
    import json
    from django.http import JsonResponse
    from django.utils import timezone
    from .models import AuditoriaIso, AgendaAuditoriaIso, PlanoAcaoMagicLink

    try:
        auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
        data = json.loads(request.body) if request.body else {}
        
        agenda_id = data.get("agenda_id")
        dias_validade = int(data.get("dias_validade") or 15)
        incluir_om = bool(data.get("incluir_om", False))

        agenda = None
        if agenda_id and str(agenda_id).strip().isdigit():
            agenda = AgendaAuditoriaIso.objects.filter(pk=int(agenda_id), auditoria=auditoria).first()

        expira_em = timezone.now() + timezone.timedelta(days=dias_validade)

        magic_link = PlanoAcaoMagicLink.objects.create(
            auditoria=auditoria,
            agenda=agenda,
            dias_validade=dias_validade,
            expira_em=expira_em,
            incluir_om=incluir_om,
            criado_por=request.user
        )

        url_path = reverse("auditoria:capa_portal_publico", kwargs={"token": magic_link.token})
        url_completa = request.build_absolute_uri(url_path)

        return JsonResponse({
            "success": True,
            "link": {
                "id": magic_link.id,
                "token": magic_link.token,
                "url": url_completa,
                "setor_nome": agenda.titulo if agenda else "Global (Todas as Áreas)",
                "dias_validade": magic_link.dias_validade,
                "expira_em": magic_link.expira_em.strftime("%d/%m/%Y"),
                "incluir_om": magic_link.incluir_om,
                "criado_em": magic_link.criado_em.strftime("%d/%m/%Y %H:%M"),
                "ativo": magic_link.ativo
            },
            "message": "Magic Link gerado com sucesso!"
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
def api_iso_capa_listar_links(request, auditoria_id):
    """Lista todos os links de Plano de Ação gerados para a auditoria."""
    from django.http import JsonResponse
    from .models import AuditoriaIso, PlanoAcaoMagicLink

    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    links_qs = auditoria.magic_links_capa.select_related("agenda", "criado_por").all()

    links_data = []
    for l in links_qs:
        url_path = reverse("auditoria:capa_portal_publico", kwargs={"token": l.token})
        links_data.append({
            "id": l.id,
            "token": l.token,
            "url": request.build_absolute_uri(url_path),
            "setor_nome": l.agenda.titulo if l.agenda else "Global (Todas as Áreas)",
            "agenda_id": l.agenda_id,
            "dias_validade": l.dias_validade,
            "expira_em": l.expira_em.strftime("%d/%m/%Y"),
            "is_expired": l.is_expired,
            "is_valid": l.is_valid,
            "incluir_om": l.incluir_om,
            "criado_por": l.criado_por.get_full_name() if l.criado_por else "Sistema",
            "criado_em": l.criado_em.strftime("%d/%m/%Y %H:%M"),
            "ultimo_acesso_em": l.ultimo_acesso_em.strftime("%d/%m/%Y %H:%M") if l.ultimo_acesso_em else "Nunca",
            "ativo": l.ativo
        })

    return JsonResponse({"success": True, "links": links_data})


@login_required
@require_POST
def api_iso_capa_revogar_link(request, pk):
    """Revoga / Desativa um Magic Link de CAPA."""
    from django.http import JsonResponse
    from .models import PlanoAcaoMagicLink

    magic_link = get_object_or_404(PlanoAcaoMagicLink, pk=pk)
    magic_link.ativo = False
    magic_link.save()

    return JsonResponse({"success": True, "message": "Link revogado com sucesso."})


@login_required
@require_POST
def api_iso_capa_revisar_solicitacao(request, pk):
    """O Auditor Líder / Coordenador aprova ou rejeita o plano de ação submetido pelo gestor."""
    import json
    from django.http import JsonResponse
    from .models import SolicitacaoEvidenciaIso

    try:
        sol = get_object_or_404(SolicitacaoEvidenciaIso, pk=pk)
        data = json.loads(request.body) if request.body else {}
        
        status_acao = data.get("status") # 'APROVADO' ou 'REJEITADO'
        parecer = data.get("parecer", "").strip()

        if status_acao not in ["APROVADO", "REJEITADO"]:
            return JsonResponse({"success": False, "error": "Status de revisão inválido."}, status=400)

        sol.capa_status = status_acao
        if parecer:
            sol.capa_parecer_auditor = parecer
        sol.save()

        return JsonResponse({
            "success": True,
            "status": sol.capa_status,
            "status_display": sol.get_capa_status_display(),
            "parecer": sol.capa_parecer_auditor,
            "message": f"Plano de Ação atualizado para '{sol.get_capa_status_display()}' com sucesso!"
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


# ------------------------------------------------------------------------------
# ROTA PÚBLICA (SEM LOGIN) - PORTAL DO AUDITADO
# ------------------------------------------------------------------------------

def capa_portal_publico_view(request, token):
    """
    Renderiza o Portal Público de Resposta ao Plano de Ação (CAPA)
    sem requerer autenticação no Calibra WEB.
    """
    from django.shortcuts import render
    from django.utils import timezone
    from .models import PlanoAcaoMagicLink, SolicitacaoEvidenciaIso

    magic_link = PlanoAcaoMagicLink.objects.filter(token=token).select_related("auditoria", "auditoria__norma", "agenda").first()

    if not magic_link or not magic_link.ativo:
        return render(request, "auditoria/iso/capa/portal_publico.html", {
            "error_title": "Link Inválido ou Desativado",
            "error_message": "Este link de Plano de Ação não é mais válido ou foi revogado pela coordenação da qualidade."
        }, status=404)

    if magic_link.is_expired:
        return render(request, "auditoria/iso/capa/portal_publico.html", {
            "error_title": "Link Expirado",
            "error_message": f"O prazo de acesso deste link expirou em {magic_link.expira_em.strftime('%d/%m/%Y')}. Solicite um novo link ao Auditor Líder."
        }, status=403)

    # Registrar último acesso
    magic_link.ultimo_acesso_em = timezone.now()
    magic_link.save(update_fields=["ultimo_acesso_em"])

    auditoria = magic_link.auditoria
    setor_filtrado = magic_link.agenda

    # Buscar itens que necessitam de tratativa
    conclusoes_alvo = ["NC", "OBS"]
    if magic_link.incluir_om:
        conclusoes_alvo.append("OM")

    solicitacoes_qs = SolicitacaoEvidenciaIso.objects.filter(
        resposta__auditoria=auditoria,
        conclusao__in=conclusoes_alvo
    ).select_related(
        "resposta__pergunta", "agenda"
    ).prefetch_related(
        "resposta__pergunta__itens_norma",
        "imagens",
        "evidencias_capa"
    ).order_by("agenda__titulo", "criado_em")

    if setor_filtrado:
        solicitacoes_qs = solicitacoes_qs.filter(agenda=setor_filtrado)

    # Estruturar lista de pendências
    itens_capa = []
    total_pendentes = 0
    total_aguardando = 0
    total_aprovados = 0

    for s in solicitacoes_qs:
        if s.capa_status == "PENDENTE":
            total_pendentes += 1
        elif s.capa_status == "AGUARDANDO_REVISAO":
            total_aguardando += 1
        elif s.capa_status == "APROVADO":
            total_aprovados += 1

        itens_norma = list(s.resposta.pergunta.itens_norma.all()) if s.resposta and s.resposta.pergunta else []
        imagens_origem = [{
            "id": img.id,
            "url": img.url_imagem,
            "nome": img.nome_arquivo,
            "legenda": img.legenda or ""
        } for img in s.imagens.all()]

        evidencias_capa = [{
            "id": ev.id,
            "url": ev.url_arquivo,
            "nome": ev.nome_arquivo,
            "tipo": ev.tipo_arquivo,
            "criado_em": ev.criado_em.strftime("%d/%m/%Y %H:%M")
        } for ev in s.evidencias_capa.all()]

        itens_capa.append({
            "id": s.id,
            "solicitacao": s.solicitacao,
            "evidencia_auditor": s.evidencia,
            "conclusao": s.conclusao,
            "grau_nc": s.grau_nc,
            "bloco_nome": s.agenda.titulo if s.agenda else "Geral / Corporativo",
            "itens_norma": itens_norma,
            "itens_str": ", ".join(it.referencia for it in itens_norma) if itens_norma else "-",
            "pergunta_texto": s.resposta.pergunta.texto_pergunta if s.resposta and s.resposta.pergunta else "",
            "imagens_origem": imagens_origem,
            # Campos CAPA
            "capa_status": s.capa_status,
            "capa_status_display": s.get_capa_status_display(),
            "capa_causa_raiz": s.capa_causa_raiz or "",
            "capa_acao_corretiva": s.capa_acao_corretiva or "",
            "capa_responsavel": s.capa_responsavel or "",
            "capa_prazo": s.capa_prazo.strftime("%Y-%m-%d") if s.capa_prazo else "",
            "capa_prazo_display": s.capa_prazo.strftime("%d/%m/%Y") if s.capa_prazo else "",
            "capa_respondido_em": s.capa_respondido_em.strftime("%d/%m/%Y %H:%M") if s.capa_respondido_em else "",
            "capa_respondido_por_nome": s.capa_respondido_por_nome or "",
            "capa_parecer_auditor": s.capa_parecer_auditor or "",
            "evidencias_capa": evidencias_capa
        })

    context = {
        "magic_link": magic_link,
        "auditoria": auditoria,
        "setor_filtrado": setor_filtrado,
        "itens_capa": itens_capa,
        "total_itens": len(itens_capa),
        "total_pendentes": total_pendentes,
        "total_aguardando": total_aguardando,
        "total_aprovados": total_aprovados,
        "token": token
    }
    return render(request, "auditoria/iso/capa/portal_publico.html", context)


@require_POST
def api_capa_salvar_resposta_publica(request, token):
    """
    Endpoint público (validado por token UUID) para o gestor salvar rascunho
    ou enviar formalmente o Plano de Ação com upload de evidências.
    """
    import base64
    from django.http import JsonResponse
    from django.utils import timezone
    from .models import PlanoAcaoMagicLink, SolicitacaoEvidenciaIso, EvidenciaPlanoAcaoIso
    from datetime import datetime

    magic_link = PlanoAcaoMagicLink.objects.filter(token=token).select_related("auditoria", "agenda").first()

    if not magic_link or not magic_link.is_valid:
        return JsonResponse({"success": False, "error": "Link de acesso inválido ou expirado."}, status=403)

    try:
        solicitacao_id = request.POST.get("solicitacao_id")
        causa_raiz = request.POST.get("causa_raiz", "").strip()
        acao_corretiva = request.POST.get("acao_corretiva", "").strip()
        responsavel = request.POST.get("responsavel", "").strip()
        prazo_str = request.POST.get("prazo", "").strip()
        respondente_nome = request.POST.get("respondente_nome", "").strip()
        is_submissao = request.POST.get("is_submissao", "false").lower() == "true"

        sol = get_object_or_404(
            SolicitacaoEvidenciaIso,
            pk=solicitacao_id,
            resposta__auditoria=magic_link.auditoria
        )

        # Se o link for restrito por setor, validar se o item pertence a ele
        if magic_link.agenda and sol.agenda_id != magic_link.agenda_id:
            return JsonResponse({"success": False, "error": "Item fora do escopo do seu setor."}, status=403)

        # Atualizar dados
        sol.capa_causa_raiz = causa_raiz
        sol.capa_acao_corretiva = acao_corretiva
        sol.capa_responsavel = responsavel
        if respondente_nome:
            sol.capa_respondido_por_nome = respondente_nome

        if prazo_str:
            try:
                sol.capa_prazo = datetime.strptime(prazo_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        if is_submissao:
            # Validação para submissão final
            if not causa_raiz or not acao_corretiva or not responsavel or not sol.capa_prazo:
                return JsonResponse({
                    "success": False,
                    "error": "Para enviar o Plano de Ação, preencha Causa Raiz, Ação, Responsável e Prazo."
                }, status=400)

            sol.capa_status = "AGUARDANDO_REVISAO"
            sol.capa_respondido_em = timezone.now()
        else:
            # Se já estava rejeitado e o gestor editou, volta para pendente se não for submissão
            if sol.capa_status == "REJEITADO":
                sol.capa_status = "PENDENTE"

        sol.save()

        # Processar uploads de arquivos se houver
        novas_evidencias = []
        if request.FILES.getlist("arquivos_evidencia"):
            for f in request.FILES.getlist("arquivos_evidencia"):
                try:
                    f_bytes = f.read()
                    f_b64 = base64.b64encode(f_bytes).decode("utf-8")
                    ev_obj = EvidenciaPlanoAcaoIso.objects.create(
                        solicitacao=sol,
                        arquivo=f,
                        arquivo_base64=f_b64,
                        nome_arquivo=f.name,
                        tipo_arquivo=f.content_type or ""
                    )
                    novas_evidencias.append({
                        "id": ev_obj.id,
                        "url": ev_obj.url_arquivo,
                        "nome": ev_obj.nome_arquivo,
                        "tipo": ev_obj.tipo_arquivo,
                        "criado_em": ev_obj.criado_em.strftime("%d/%m/%Y %H:%M")
                    })
                except Exception as ex_file:
                    print(f"Erro ao salvar anexo CAPA: {ex_file}")

        return JsonResponse({
            "success": True,
            "solicitacao_id": sol.id,
            "status": sol.capa_status,
            "status_display": sol.get_capa_status_display(),
            "respondido_em": sol.capa_respondido_em.strftime("%d/%m/%Y %H:%M") if sol.capa_respondido_em else "",
            "novas_evidencias": novas_evidencias,
            "message": "Plano de Ação submetido com sucesso! O Auditor Líder foi notificado para revisão." if is_submissao else "Rascunho salvo com sucesso."
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@require_POST
def api_capa_remover_evidencia_publica(request, token, evidencia_id):
    """Remove uma evidência anexada pelo gestor."""
    from django.http import JsonResponse
    from .models import PlanoAcaoMagicLink, EvidenciaPlanoAcaoIso

    magic_link = PlanoAcaoMagicLink.objects.filter(token=token).first()
    if not magic_link or not magic_link.is_valid:
        return JsonResponse({"success": False, "error": "Link de acesso inválido ou expirado."}, status=403)

    try:
        ev = get_object_or_404(
            EvidenciaPlanoAcaoIso,
            pk=evidencia_id,
            solicitacao__resposta__auditoria=magic_link.auditoria
        )
        ev.delete()
        return JsonResponse({"success": True, "message": "Evidência removida com sucesso."})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


# ==============================================================================
# AVALIAÇÃO DO AUDITOR & FEEDBACK PÓS-AUDITORIA (MAGIC LINK)
# ==============================================================================

@login_required
@require_POST
def api_iso_avaliacao_gerar_link(request, auditoria_id):
    """
    Gera um novo Magic Link público com validade de 7 dias para avaliação do auditor.
    """
    from django.http import JsonResponse
    from .models import AuditoriaIso, TokenAvaliacaoIso

    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    dias_validade = 7
    expira_em = timezone.now() + timezone.timedelta(days=dias_validade)

    token_obj = TokenAvaliacaoIso.objects.create(
        auditoria=auditoria,
        dias_validade=dias_validade,
        expira_em=expira_em,
        criado_por=request.user if request.user.is_authenticated else None,
        ativo=True
    )

    url_publica = request.build_absolute_uri(
        reverse("auditoria:avaliacao_portal_publico", kwargs={"token": token_obj.token})
    )

    return JsonResponse({
        "success": True,
        "token": token_obj.token,
        "url": url_publica,
        "dias_validade": dias_validade,
        "expira_em": token_obj.expira_em.strftime("%d/%m/%Y"),
        "message": "Link de Avaliação gerado com sucesso!"
    })


@login_required
def api_iso_avaliacao_resumo(request, auditoria_id):
    """
    Retorna métricas consolidadas (médias de pontualidade, clareza, cordialidade e lista de feedbacks).
    """
    from django.http import JsonResponse
    from django.db.models import Avg, Count
    from .models import AuditoriaIso, AvaliacaoAuditorIso

    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    avaliacoes = AvaliacaoAuditorIso.objects.filter(auditoria=auditoria).order_by("-criado_em")

    total_avaliacoes = avaliacoes.count()
    if total_avaliacoes == 0:
        return JsonResponse({
            "success": True,
            "total_avaliacoes": 0,
            "media_geral": 0,
            "media_pontualidade": 0,
            "media_clareza": 0,
            "media_cordialidade": 0,
            "avaliacoes": []
        })

    stats = avaliacoes.aggregate(
        media_pontualidade=Avg("nota_pontualidade"),
        media_clareza=Avg("nota_clareza"),
        media_cordialidade=Avg("nota_cordialidade"),
    )

    m_pont = round(stats["media_pontualidade"] or 0, 1)
    m_clar = round(stats["media_clareza"] or 0, 1)
    m_cord = round(stats["media_cordialidade"] or 0, 1)
    m_geral = round((m_pont + m_clar + m_cord) / 3, 1)

    lista_avaliacoes = []
    for av in avaliacoes:
        lista_avaliacoes.append({
            "id": av.id,
            "nota_pontualidade": av.nota_pontualidade,
            "nota_clareza": av.nota_clareza,
            "nota_cordialidade": av.nota_cordialidade,
            "media_individual": av.media_individual,
            "pontos_fortes": av.pontos_fortes,
            "oportunidades_melhoria": av.oportunidades_melhoria,
            "setor_avaliador": av.setor_avaliador or "Não especificado",
            "nome_avaliador": av.nome_avaliador or "Anônimo",
            "criado_em": av.criado_em.strftime("%d/%m/%Y %H:%M"),
        })

    return JsonResponse({
        "success": True,
        "total_avaliacoes": total_avaliacoes,
        "media_geral": m_geral,
        "media_pontualidade": m_pont,
        "media_clareza": m_clar,
        "media_cordialidade": m_cord,
        "avaliacoes": lista_avaliacoes
    })


def avaliacao_portal_publico_view(request, token):
    """
    Portal público de feedback do auditor (sem necessidade de login).
    """
    from .models import TokenAvaliacaoIso
    token_obj = TokenAvaliacaoIso.objects.filter(token=token).first()

    if not token_obj or not token_obj.is_valid:
        return render(request, "auditoria/iso/avaliacao/portal_publico.html", {
            "erro": "Link de avaliação inválido, expirado ou revogado.",
            "token_invalido": True,
        })

    # Atualiza registro de último acesso
    token_obj.ultimo_acesso_em = timezone.now()
    token_obj.save(update_fields=["ultimo_acesso_em"])

    auditoria = token_obj.auditoria
    context = {
        "token_obj": token_obj,
        "auditoria": auditoria,
        "empresa_nome": auditoria.empresa_auditada or auditoria.unidade or "Unidade Auditada",
        "norma_codigo": auditoria.norma.codigo,
        "norma_nome": auditoria.norma.nome,
        "auditor_lider": auditoria.auditor_lider_nome or "Equipe Auditora",
        "data_inicio": auditoria.data_inicio,
        "data_fim": auditoria.data_fim,
    }
    return render(request, "auditoria/iso/avaliacao/portal_publico.html", context)


@require_POST
def api_avaliacao_salvar_resposta_publica(request, token):
    """
    Endpoint público para salvar a avaliação submetida pelo auditado.
    """
    from django.http import JsonResponse
    from .models import TokenAvaliacaoIso, AvaliacaoAuditorIso

    token_obj = TokenAvaliacaoIso.objects.filter(token=token).first()
    if not token_obj or not token_obj.is_valid:
        return JsonResponse({"success": False, "error": "Link de avaliação inválido ou expirado."}, status=403)

    try:
        data = json.loads(request.body.decode("utf-8")) if request.body else {}
        
        nota_pontualidade = int(data.get("nota_pontualidade", 0))
        nota_clareza = int(data.get("nota_clareza", 0))
        nota_cordialidade = int(data.get("nota_cordialidade", 0))

        if not (1 <= nota_pontualidade <= 5 and 1 <= nota_clareza <= 5 and 1 <= nota_cordialidade <= 5):
            return JsonResponse({"success": False, "error": "Por favor, avalie todas as 3 categorias com notas de 1 a 5 estrelas."}, status=400)

        pontos_fortes = data.get("pontos_fortes", "").strip()
        oportunidades_melhoria = data.get("oportunidades_melhoria", "").strip()
        setor_avaliador = data.get("setor_avaliador", "").strip()
        nome_avaliador = data.get("nome_avaliador", "").strip()

        av = AvaliacaoAuditorIso.objects.create(
            auditoria=token_obj.auditoria,
            token_origem=token_obj,
            nota_pontualidade=nota_pontualidade,
            nota_clareza=nota_clareza,
            nota_cordialidade=nota_cordialidade,
            pontos_fortes=pontos_fortes,
            oportunidades_melhoria=oportunidades_melhoria,
            setor_avaliador=setor_avaliador,
            nome_avaliador=nome_avaliador
        )

        token_obj.total_respostas = (token_obj.total_respostas or 0) + 1
        token_obj.save(update_fields=["total_respostas"])

        return JsonResponse({
            "success": True,
            "avaliacao_id": av.id,
            "message": "Avaliação enviada com sucesso! Muito obrigado pelo seu feedback."
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)



