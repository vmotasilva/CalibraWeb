from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from django.core.cache import cache
from django.urls import reverse


@dataclass(frozen=True)
class CobrancaItem:
    key: str
    label: str
    count: int
    url: str


def _first_day_of_month(d: date) -> date:
    return d.replace(day=1)


def _first_day_of_quarter(d: date) -> date:
    quarter = ((d.month - 1) // 3) + 1
    first_month = (quarter - 1) * 3 + 1
    return d.replace(month=first_month, day=1)


def _first_day_of_semester(d: date) -> date:
    first_month = 1 if d.month <= 6 else 7
    return d.replace(month=first_month, day=1)


def _monday_of_week(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _safe_reverse(name: str) -> str:
    try:
        return reverse(name)
    except Exception:
        return "#"


def _get_colaborador_for_user(user: Any):
    try:
        from qms.views_helpers import get_colaborador_for_user

        return get_colaborador_for_user(user)
    except Exception:
        return None


def get_user_cobrancas_counts(user: Any) -> dict[str, int]:
    """Retorna contagens de cobranças por módulo para o usuário ativo.

    Observação: as regras aqui são intencionalmente simples e orientadas a "itens que exigem atenção/mudança de status".
    """

    if not getattr(user, "is_authenticated", False):
        return {"total": 0}

    cache_key = f"nav_cobrancas_counts:v1:user:{getattr(user, 'pk', 'anon')}"
    cached = cache.get(cache_key)
    if isinstance(cached, dict):
        return cached

    hoje = date.today()
    counts: dict[str, int] = {}

    colaborador = _get_colaborador_for_user(user)

    # Metrologia: instrumentos vencidos para o responsável
    try:
        from metrologia.models import Instrumento

        if colaborador:
            counts["metrologia"] = Instrumento.objects.filter(
                ativo=True,
                responsavel=colaborador,
                data_proxima_calibracao__lt=hoje,
            ).count()
        else:
            counts["metrologia"] = 0
    except Exception:
        counts["metrologia"] = 0

    # Ações: ações vencidas para o responsável (não concluídas/canceladas)
    try:
        from acoes.models import AcaoCorretiva

        if colaborador:
            counts["acoes"] = (
                AcaoCorretiva.objects.filter(
                    ativo=True,
                    responsavel=colaborador,
                    data_vencimento__lt=hoje,
                )
                .exclude(status__in=["concluida", "cancelada"])
                .count()
            )
        else:
            counts["acoes"] = 0
    except Exception:
        counts["acoes"] = 0

    # Cotações: processos abertos vencidos para o responsável
    try:
        from procedures.models import ProcessoCotacao

        if colaborador:
            counts["cotacoes"] = ProcessoCotacao.objects.filter(
                status="ABERTO",
                responsavel=colaborador,
                prazo_limite__lt=hoje,
            ).count()
        else:
            counts["cotacoes"] = 0
    except Exception:
        counts["cotacoes"] = 0

    # Auditoria: modelos atribuídos ao usuário que estão "em atraso" pela periodicidade
    try:
        from auditoria.models import ModeloAuditoria
        from django.db.models import Max

        modelos = (
            ModeloAuditoria.objects.filter(ativo=True, responsavel=user)
            .annotate(ultima_data=Max("registros__data_auditoria"))
            .only("id", "periodicidade")
        )

        due = 0
        monday = _monday_of_week(hoje)
        month_start = _first_day_of_month(hoje)
        quarter_start = _first_day_of_quarter(hoje)
        semester_start = _first_day_of_semester(hoje)
        year_start = hoje.replace(month=1, day=1)

        for m in modelos:
            last = getattr(m, "ultima_data", None)
            p = getattr(m, "periodicidade", None)

            if p == "UNICA":
                if last is None:
                    due += 1
                continue

            if last is None:
                due += 1
                continue

            if p == "DIARIA" and last < hoje:
                due += 1
            elif p == "SEMANAL" and last < monday:
                due += 1
            elif p == "QUINZENAL" and last < (hoje - timedelta(days=14)):
                due += 1
            elif p == "MENSAL" and last < month_start:
                due += 1
            elif p == "TRIMESTRAL" and last < quarter_start:
                due += 1
            elif p == "SEMESTRAL" and last < semester_start:
                due += 1
            elif p == "ANUAL" and last < year_start:
                due += 1

        counts["auditoria"] = due
    except Exception:
        counts["auditoria"] = 0

    counts["total"] = sum(v for k, v in counts.items() if k != "total")

    cache.set(cache_key, counts, timeout=60)
    return counts


def get_user_cobrancas_items(user: Any) -> list[CobrancaItem]:
    counts = get_user_cobrancas_counts(user)
    return [
        CobrancaItem(
            key="metrologia",
            label="Metrologia (calibrações vencidas)",
            count=int(counts.get("metrologia", 0) or 0),
            url=_safe_reverse("modulo_metrologia"),
        ),
        CobrancaItem(
            key="acoes",
            label="Ações (vencidas)",
            count=int(counts.get("acoes", 0) or 0),
            url=_safe_reverse("acoes:acoes_registradas"),
        ),
        CobrancaItem(
            key="cotacoes",
            label="Cotações (prazo vencido)",
            count=int(counts.get("cotacoes", 0) or 0),
            url=_safe_reverse("procedures:cotacoes_list"),
        ),
        CobrancaItem(
            key="auditoria",
            label="Auditoria (a realizar)",
            count=int(counts.get("auditoria", 0) or 0),
            url=_safe_reverse("auditoria:selecionar_modelo_preenchimento"),
        ),
    ]
