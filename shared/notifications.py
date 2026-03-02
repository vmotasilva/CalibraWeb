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

    cache_key = f"nav_cobrancas_counts:v4:user:{getattr(user, 'pk', 'anon')}"
    cached = cache.get(cache_key)
    if isinstance(cached, dict):
        return cached

    hoje = date.today()
    counts: dict[str, int] = {}

    is_global_viewer = bool(getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))

    colaborador = _get_colaborador_for_user(user)

    # Metrologia: instrumentos vencidos
    try:
        from metrologia.models import Instrumento
        from django.db.models import Q

        global_vencidos = Instrumento.objects.filter(
            ativo=True,
            data_proxima_calibracao__lt=hoje,
        )

        if not is_global_viewer and colaborador:
            scoped_vencidos = global_vencidos.filter(
                Q(responsavel=colaborador) | Q(responsavel__isnull=True)
            )

            # Fallback: se não há nada atribuído (ou sem responsável), mostrar o global
            # para evitar “0” enganoso no home quando o módulo tem vencidos.
            counts["metrologia"] = scoped_vencidos.count() or global_vencidos.count()
        else:
            counts["metrologia"] = global_vencidos.count()
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

    # Cotações (novo fluxo Metrologia): solicitações com prazo vencido
    try:
        from metrologia.models import SolicitacaoCotacao

        global_solicitacoes = SolicitacaoCotacao.objects.exclude(status__in=["CONCLUIDA", "CANCELADA"]).filter(
            data_solicitacao_orcamento__isnull=False,
            data_solicitacao_orcamento__lte=hoje,
        )

        # No modelo novo, o responsável é um auth.User.
        if not is_global_viewer:
            scoped_solicitacoes = global_solicitacoes.filter(responsavel=user)
            counts["cotacoes"] = scoped_solicitacoes.count() or global_solicitacoes.count()
        else:
            counts["cotacoes"] = global_solicitacoes.count()
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

    # Treinamentos: Matriz de Habilidade, Demanda de Treinamento, Planejamentos (prazos)
    try:
        from django.db.models import F, Q
        from rh.models import Colaborador
        from procedures.models import PlanejamentoTreinamento, RegistroTreinamento, SolicitacaoValidacaoMatriz

        if colaborador:
            scope_colabs = Colaborador.objects.filter(
                Q(pk=colaborador.pk) | Q(lider=colaborador),
                is_active=True,
            )

            # Matriz de Habilidade: pendências de validação designadas ao líder/validador
            counts["trein_matriz"] = SolicitacaoValidacaoMatriz.objects.filter(
                status="pendente",
                validador=colaborador,
            ).count()

            # Demanda de Treinamento: registros pendentes (não iniciado / revisão desatualizada / anterior à última revisão)
            pendencias_q = (
                Q(data_treinamento__isnull=True)
                | (
                    Q(lista_presenca__isnull=True)
                    & (
                        (
                            Q(procedimento__numero_revisao__isnull=False)
                            & ~Q(revisao_treinada=F("procedimento__numero_revisao"))
                        )
                        | (
                            Q(procedimento__ultima_revisao__isnull=False)
                            & Q(data_treinamento__lt=F("procedimento__ultima_revisao"))
                        )
                    )
                )
                | (
                    Q(lista_presenca__isnull=False)
                    & Q(procedimento__ultima_revisao__isnull=False)
                    & Q(data_treinamento__lt=F("procedimento__ultima_revisao"))
                )
            )

            counts["trein_demanda"] = (
                RegistroTreinamento.objects.filter(
                    ativo=True,
                    tipo="PROCEDIMENTO",
                    procedimento__isnull=False,
                    colaborador__in=scope_colabs,
                )
                .filter(pendencias_q)
                .count()
            )

            # Planejamentos: prazos vencidos para treinamentos do escopo (instrutor ou participantes)
            counts["trein_planejamentos"] = (
                PlanejamentoTreinamento.objects.filter(
                    status__in=["PLANEJADO", "CONFIRMADO", "ATRASADO"],
                    data_prevista__lt=hoje,
                )
                .filter(Q(instrutor=colaborador) | Q(colaboradores__in=scope_colabs))
                .distinct()
                .count()
            )
        else:
            counts["trein_matriz"] = 0
            counts["trein_demanda"] = 0
            counts["trein_planejamentos"] = 0
    except Exception:
        counts["trein_matriz"] = 0
        counts["trein_demanda"] = 0
        counts["trein_planejamentos"] = 0

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
            url=_safe_reverse("modulo_metrologia") + "?status=vencidos",
        ),
        CobrancaItem(
            key="cotacoes",
            label="Cotações (prazo vencido)",
            count=int(counts.get("cotacoes", 0) or 0),
            url=_safe_reverse("metrologia:solicitacao_list"),
        ),
        CobrancaItem(
            key="acoes",
            label="Ações (vencidas)",
            count=int(counts.get("acoes", 0) or 0),
            url=_safe_reverse("acoes:acoes_registradas"),
        ),
        CobrancaItem(
            key="auditoria",
            label="Auditoria (a realizar)",
            count=int(counts.get("auditoria", 0) or 0),
            url=_safe_reverse("auditoria:selecionar_modelo_preenchimento"),
        ),
        CobrancaItem(
            key="trein_matriz",
            label="Matriz de Habilidade (Cobrança ao líder mensalmente)",
            count=int(counts.get("trein_matriz", 0) or 0),
            url=_safe_reverse("procedures:validacoes_pendentes"),
        ),
        CobrancaItem(
            key="trein_demanda",
            label="Demanda de Treinamento (Cobrar as pendências de treinamento)",
            count=int(counts.get("trein_demanda", 0) or 0),
            url=_safe_reverse("procedures:dashboard_treinamentos"),
        ),
        CobrancaItem(
            key="trein_planejamentos",
            label="Planejamentos (Notificações sobre os prazos dos treinamentos planejados)",
            count=int(counts.get("trein_planejamentos", 0) or 0),
            url=_safe_reverse("procedures:planejamentos_list"),
        ),
    ]
