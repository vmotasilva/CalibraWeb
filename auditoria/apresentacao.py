"""Modo apresentação do relatório de auditoria (deck 16:9), inspirado na apresentação de encerramento ISO."""

from __future__ import annotations

from collections import OrderedDict

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.cache import never_cache

from .models import (
    ComentarioRespostaAuditoria,
    ModeloAuditoria,
    RegistroAuditoria,
    RelatorioCompartilhadoAuditoria,
    RespostaAuditoria,
)

_NA_TOKENS = {"na", "n/a", "n.a", "n a", "nao aplicavel", "nao se aplica"}
_TIPOS_CONFORMIDADE = ("SIM_NAO", "LISTA")
OCORRENCIAS_POR_SLIDE = 4
TOPICOS_POR_SLIDE = 7


def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def _classificar(valor: str) -> str | None:
    from .views import _VALORES_NAO_CONFORME, _normalize_text_token

    token = _normalize_text_token(valor)
    if not token:
        return None
    if token in _NA_TOKENS:
        return "na"
    if token in _VALORES_NAO_CONFORME:
        return "nc"
    return "c"


def _pct(conformes: int, ncs: int):
    total = conformes + ncs
    return round(conformes * 100 / total, 1) if total else None


def _faixa(pct):
    if pct is None:
        return "sem"
    if pct >= 95:
        return "ok"
    if pct >= 80:
        return "alerta"
    return "critico"


ITENS_POR_SLIDE = 4


def _fmt_pct(pct, casas=0):
    if pct is None:
        return "—"
    return (f"{pct:.{casas}f}%").replace(".", ",")


def montar_apresentacao(modelo: ModeloAuditoria, inicio=None, fim=None, max_ciclos: int = 12) -> dict:
    """Compõe a apresentação a partir do último ciclo fechado (CONCLUIDO), com seus comentários e ocorrências."""
    from .views import _build_ocorrencias_por_pergunta, _calcular_semanas_consecutivas_nc

    fechados_qs = RegistroAuditoria.objects.filter(modelo=modelo, status="CONCLUIDO")
    if inicio:
        fechados_qs = fechados_qs.filter(periodo_inicio__gte=inicio)
    if fim:
        fechados_qs = fechados_qs.filter(periodo_inicio__lte=fim)
    total_fechados = fechados_qs.count()
    historico = list(fechados_qs.order_by("-periodo_inicio", "-id")[:max_ciclos])
    base = historico[0] if historico else None
    historico.reverse()  # cronológico

    respostas = (
        RespostaAuditoria.objects.filter(
            registro__in=historico,
            pergunta__ativo=True,
            pergunta__tipo_resposta__in=_TIPOS_CONFORMIDADE,
        )
        .exclude(valor="")
        .select_related("pergunta", "pergunta__topico")
    )

    por_registro: dict[int, dict] = {r.id: {"c": 0, "nc": 0} for r in historico}
    por_topico: "OrderedDict[str, dict]" = OrderedDict()
    por_pergunta: dict[int, dict] = {}
    for resp in respostas:
        classe = _classificar(resp.valor)
        if classe not in ("c", "nc"):
            continue
        por_registro[resp.registro_id][classe] += 1
        if base is not None and resp.registro_id == base.id:
            nome_topico = resp.pergunta.topico.get_full_name() if resp.pergunta.topico_id else "Geral"
            por_topico.setdefault(nome_topico, {"c": 0, "nc": 0})[classe] += 1
            info = por_pergunta.setdefault(
                resp.pergunta_id, {"pergunta": resp.pergunta.pergunta, "topico": nome_topico, "c": 0, "nc": 0}
            )
            info[classe] += 1

    ciclos = []
    for r in historico:
        c, nc = por_registro[r.id]["c"], por_registro[r.id]["nc"]
        pct = _pct(c, nc)
        periodo = f"{r.periodo_inicio:%d/%m}"
        if r.periodo_fim:
            periodo += f" a {r.periodo_fim:%d/%m}"
        ciclos.append(
            {
                "id": r.id,
                "nome": r.nome,
                "label": f"{r.periodo_inicio:%d/%m}",
                "periodo": periodo,
                "conformes": c,
                "ncs": nc,
                "pct": pct,
                "pct_txt": _fmt_pct(pct),
                "altura": max(pct, 4) if pct is not None else 4,
                "faixa": _faixa(pct),
                "atual": base is not None and r.id == base.id,
            }
        )

    ciclo_base = ciclos[-1] if ciclos else None
    pct_geral = ciclo_base["pct"] if ciclo_base else None
    total_c = ciclo_base["conformes"] if ciclo_base else 0
    total_nc = ciclo_base["ncs"] if ciclo_base else 0
    variacao = None
    anterior = next((c for c in reversed(ciclos[:-1]) if c["pct"] is not None), None)
    if ciclo_base and ciclo_base["pct"] is not None and anterior:
        variacao = round(ciclo_base["pct"] - anterior["pct"], 1)

    topicos = []
    for nome, v in por_topico.items():
        pct = _pct(v["c"], v["nc"])
        topicos.append(
            {
                "nome": nome,
                "conformes": v["c"],
                "ncs": v["nc"],
                "pct": pct,
                "pct_txt": _fmt_pct(pct),
                "largura": pct if pct is not None else 0,
                "faixa": _faixa(pct),
            }
        )
    topicos.sort(key=lambda t: (t["pct"] is None, t["pct"] if t["pct"] is not None else 0))

    criticas = []
    semanas = _calcular_semanas_consecutivas_nc(base, list(por_pergunta.keys())) if base else {}
    for pid, info in por_pergunta.items():
        if info["nc"] == 0:
            continue
        criticas.append(
            {
                "pergunta": info["pergunta"],
                "topico": info["topico"],
                "ncs": info["nc"],
                "total": info["c"] + info["nc"],
                "semanas": semanas.get(pid, 0),
            }
        )
    criticas.sort(key=lambda x: (-x["semanas"], -x["ncs"], x["pergunta"]))
    criticas = criticas[:8]

    # Comentários e ocorrências do ciclo base (próprios + associados)
    itens_ciclo: list[dict] = []
    ids_ciclo: set[int] = set()
    if base is not None:
        nomes_perguntas = {
            str(p.id): p.pergunta for p in modelo.perguntas.filter(ativo=True).only("id", "pergunta")
        }
        for pid, itens in _build_ocorrencias_por_pergunta(base).items():
            for it in itens:
                ids_ciclo.add(it["id"])
                itens_ciclo.append(
                    {
                        "pergunta": nomes_perguntas.get(pid, ""),
                        "texto": it["texto"],
                        "acao": (it.get("acao") or "").strip(),
                        "requer": bool(it["requer_tratativa"]),
                        "aberta": bool(it["em_aberto"]),
                        "resolucao": (it.get("resolucao") or "").strip(),
                        "prazo": it.get("prazo") or "",
                        "responsaveis": [r["nome"] for r in it.get("responsaveis_info", [])],
                        "recorrente": bool(it["associada"]),
                        "dias": it["dias_aberta"],
                    }
                )
    # ocorrências primeiro (em aberto, depois resolvidas), depois comentários simples
    itens_ciclo.sort(key=lambda x: (0 if (x["requer"] and x["aberta"]) else 1 if x["requer"] else 2))
    total_ocorrencias_ciclo = sum(1 for x in itens_ciclo if x["requer"])
    total_comentarios_ciclo = len(itens_ciclo) - total_ocorrencias_ciclo

    hoje = timezone.localdate()
    ocorrencias_qs = (
        ComentarioRespostaAuditoria.objects.filter(
            pergunta__modelo=modelo,
            requer_tratativa=True,
            unificada_em__isnull=True,
            status=ComentarioRespostaAuditoria.STATUS_ABERTA,
        )
        .select_related("pergunta", "autor")
        .prefetch_related("responsaveis")
        .order_by("prazo", "-criado_em", "-id")
    )
    total_ocorrencias_abertas = ocorrencias_qs.count()
    outras = []
    vencidas = 0
    for oc in ocorrencias_qs[:60]:
        vencida = bool(oc.prazo and oc.prazo < hoje)
        vencidas += 1 if vencida else 0
        if oc.id in ids_ciclo:
            continue
        outras.append(
            {
                "pergunta": oc.pergunta.pergunta,
                "texto": (oc.texto or "").strip(),
                "acao": (oc.acao or "").strip(),
                "prazo": oc.prazo,
                "vencida": vencida,
                "dias": max((hoje - timezone.localtime(oc.criado_em).date()).days, 0),
                "responsaveis": [c.nome_completo for c in oc.responsaveis.all()],
            }
        )

    if base is not None:
        auditores = [c.nome_completo for c in base.auditores.all()]
        if not auditores and base.avaliador_id:
            auditores = [base.avaliador.get_full_name() or base.avaliador.get_username()]
        periodo_base = f"{base.periodo_inicio:%d/%m/%Y} a {(base.periodo_fim or base.periodo_inicio):%d/%m/%Y}"
    else:
        auditores = []
        periodo_base = ""
    auditados = [c.nome_completo for c in modelo.auditados.all()]
    responsaveis = [u.get_full_name() or u.get_username() for u in modelo.responsaveis.all()]

    slides: list[dict] = [{"kind": "capa", "titulo": "Capa"}]
    if base is None:
        slides.append({"kind": "vazio", "titulo": "Sem ciclo fechado"})
    else:
        slides.append({"kind": "resumo", "titulo": "Resumo executivo"})
        if len(ciclos) > 1:
            slides.append({"kind": "evolucao", "titulo": "Evolução por ciclo"})
        for i, lote in enumerate(_chunks(topicos, TOPICOS_POR_SLIDE), start=1):
            slides.append({"kind": "topicos", "titulo": "Conformidade por tópico", "itens": lote, "parte": i})
        slides.append({"kind": "criticas", "titulo": "Pontos de atenção"})
        lotes_itens = list(_chunks(itens_ciclo, ITENS_POR_SLIDE)) or [[]]
        for i, lote in enumerate(lotes_itens, start=1):
            slides.append(
                {"kind": "itens", "titulo": "Comentários e ocorrências do ciclo", "itens": lote, "parte": i, "partes": len(lotes_itens)}
            )
        lotes_outras = list(_chunks(outras, OCORRENCIAS_POR_SLIDE))
        for i, lote in enumerate(lotes_outras, start=1):
            slides.append(
                {"kind": "ocorrencias", "titulo": "Plano de ação", "itens": lote, "parte": i, "partes": len(lotes_outras)}
            )
    slides.append({"kind": "encerramento", "titulo": "Encerramento"})
    for n, sl in enumerate(slides, start=1):
        sl["numero"] = n

    return {
        "modelo": modelo,
        "base": base,
        "slides": slides,
        "total_slides": len(slides),
        "ciclos": ciclos,
        "ultimo_ciclo": ciclo_base,
        "total_fechados": total_fechados,
        "ciclos_analisados": len(ciclos),
        "pct_geral": pct_geral,
        "pct_geral_txt": _fmt_pct(pct_geral, 1),
        "faixa_geral": _faixa(pct_geral),
        "variacao": variacao,
        "total_nc": total_nc,
        "total_c": total_c,
        "topicos": topicos,
        "criticas": criticas,
        "itens_ciclo": itens_ciclo,
        "total_ocorrencias_ciclo": total_ocorrencias_ciclo,
        "total_comentarios_ciclo": total_comentarios_ciclo,
        "total_ocorrencias_abertas": total_ocorrencias_abertas,
        "ocorrencias_vencidas": vencidas,
        "periodo_txt": periodo_base,
        "auditores": auditores,
        "auditados": auditados,
        "responsaveis": responsaveis,
        "gerado_em": timezone.localtime(),
    }


@login_required
@never_cache
def modelo_apresentacao(request, modelo_id):
    """Apresentação em slides do relatório do modelo. Disponível a quem tem acesso de visualização."""
    from .views import (
        _filter_modelos_para_usuario,
        _modelos_como_auditado,
        _read_registro_report_share_token,
    )

    share_token = (request.GET.get("share_token") or "").strip()
    inicio_raw = (request.GET.get("inicio") or "").strip()
    fim_raw = (request.GET.get("fim") or "").strip()

    if share_token:
        share = (
            RelatorioCompartilhadoAuditoria.objects.filter(token=share_token, ativo=True).first()
        )
        if share:
            if share.modelo_id != int(modelo_id):
                return HttpResponseForbidden("Link de compartilhamento inválido para este relatório.")
            if share.destinatario_id != request.user.id:
                return HttpResponseForbidden("Este compartilhamento é direcionado a outro usuário.")
            if share.is_expired:
                return HttpResponseForbidden("Este compartilhamento expirou.")
            inicio_raw = share.inicio.isoformat() if share.inicio else ""
            fim_raw = share.fim.isoformat() if share.fim else ""
        else:
            data = _read_registro_report_share_token(share_token)
            if not data or int(data.get("modelo_id", 0)) != int(modelo_id):
                return HttpResponseForbidden("Link de compartilhamento inválido ou expirado.")
            inicio_raw = data.get("inicio") or ""
            fim_raw = data.get("fim") or ""
        modelo = get_object_or_404(ModeloAuditoria.objects.all(), pk=modelo_id)
    else:
        modelo = _filter_modelos_para_usuario(request.user, ModeloAuditoria.objects.all()).filter(pk=modelo_id).first()
        if modelo is None:
            modelo = get_object_or_404(_modelos_como_auditado(request.user), pk=modelo_id)

    inicio = parse_date(inicio_raw) if inicio_raw else None
    fim = parse_date(fim_raw) if fim_raw else None
    try:
        max_ciclos = int(request.GET.get("ciclos") or 12)
    except (TypeError, ValueError):
        max_ciclos = 12
    max_ciclos = min(max(max_ciclos, 2), 24)

    context = montar_apresentacao(modelo, inicio, fim, max_ciclos)
    context["max_ciclos"] = max_ciclos
    context["opcoes_ciclos"] = [6, 12, 24]
    context["share_token"] = share_token
    context["voltar_url"] = request.META.get("HTTP_REFERER") or ""
    return render(request, "auditoria/modelo_apresentacao.html", context)
