from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from django.core.cache import cache
from django.urls import reverse
from urllib.parse import quote_plus
from shared.permissions import has_module_access, has_view_access


SPECIAL_VIEW_ALL_COLABORADORES_PERM = 'core.nav_pessoas_ver_todos_colaboradores'


@dataclass(frozen=True)
class CobrancaItem:
    key: str
    label: str
    count: int
    url: str
    section: str = "Outros"


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


def _is_global_viewer(user: Any) -> bool:
    try:
        return bool(
            getattr(user, "is_staff", False)
            or getattr(user, "is_superuser", False)
            or user.has_perm(SPECIAL_VIEW_ALL_COLABORADORES_PERM)
        )
    except Exception:
        return bool(getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))


def get_user_cobrancas_counts(user: Any) -> dict[str, int]:
    """Retorna contagens de cobranças por módulo para o usuário ativo.

    Observação: as regras aqui são intencionalmente simples e orientadas a "itens que exigem atenção/mudança de status".
    """

    if not getattr(user, "is_authenticated", False):
        return {"total": 0}

    cache_key = f"nav_cobrancas_counts:v5:user:{getattr(user, 'pk', 'anon')}"
    cached = cache.get(cache_key)
    if isinstance(cached, dict):
        return cached

    hoje = date.today()
    counts: dict[str, int] = {}

    is_global_viewer = _is_global_viewer(user)

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
        from django.db.models import Q
        from auditoria.utils_periodos import calcular_periodos_pendentes

        modelos = ModeloAuditoria.objects.filter(ativo=True)
        if not is_global_viewer:
            modelos = modelos.filter(Q(responsavel=user) | Q(responsaveis=user)).distinct()

        pendencias_count = 0
        for modelo in modelos:
            periodos = calcular_periodos_pendentes(modelo, limit=1)
            if periodos:
                pendencias_count += 1
                
        counts["auditoria"] = pendencias_count
    except Exception:
        counts["auditoria"] = 0

    # Treinamentos: Matriz de Habilidade, Demanda de Treinamento, Planejamentos (prazos)
    try:
        from django.db.models import F, Q
        from rh.models import Colaborador
        from procedures.models import PlanejamentoTreinamento, RegistroTreinamento, SolicitacaoValidacaoMatriz

        if colaborador:
            scope_colabs = Colaborador.objects.filter(
                Q(pk=colaborador.pk) | Q(lider=colaborador) | Q(supervisor=colaborador) | Q(gerente=colaborador),
                is_active=True,
            )

            # Matriz de Habilidade: pendências de validação designadas ao líder/validador
            counts["trein_matriz"] = SolicitacaoValidacaoMatriz.objects.filter(
                status="pendente",
                validador=colaborador,
            ).count()

            # Demanda de Treinamento: registros pendentes (não iniciado / revisão desatualizada / anterior à data de aprovação)
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
                            Q(procedimento__data_aprovacao__isnull=False)
                            & Q(data_treinamento__lt=F("procedimento__data_aprovacao"))
                        )
                    )
                )
                | (
                    Q(lista_presenca__isnull=False)
                    & Q(procedimento__data_aprovacao__isnull=False)
                    & Q(data_treinamento__lt=F("procedimento__data_aprovacao"))
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
            planejamento_base = PlanejamentoTreinamento.objects.filter(
                status__in=["PLANEJADO", "CONFIRMADO", "ATRASADO"],
            )
            if is_global_viewer:
                counts["trein_planejamentos"] = planejamento_base.count()
            else:
                counts["trein_planejamentos"] = planejamento_base.filter(instrutor=colaborador).count()
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
    is_global_viewer = _is_global_viewer(user)
    colaborador = _get_colaborador_for_user(user)

    def with_qs(base: str, qs: str) -> str:
        if is_global_viewer or not qs:
            return base
        joiner = "&" if "?" in base else "?"
        return base + joiner + qs

    acoes_responsavel = ""
    try:
        if colaborador and getattr(colaborador, "nome_completo", ""):
            acoes_responsavel = str(colaborador.nome_completo)
        elif getattr(user, "get_full_name", None):
            acoes_responsavel = user.get_full_name() or ""
        else:
            acoes_responsavel = getattr(user, "username", "") or ""
    except Exception:
        acoes_responsavel = ""

    def qs_param(key: str, value: str) -> str:
        if not value:
            return ""
        return f"{key}={quote_plus(str(value))}"

    # Dashboard de Treinamentos: priorizar o escopo do usuário conforme hierarquia.
    treinamentos_scope_qs = ""
    try:
        if not is_global_viewer and colaborador:
            from rh.models import Colaborador as RhColaborador

            if RhColaborador.objects.filter(lider=colaborador, is_active=True).exists():
                treinamentos_scope_qs = f"lider={colaborador.pk}"
            elif RhColaborador.objects.filter(supervisor=colaborador, is_active=True).exists():
                treinamentos_scope_qs = f"supervisor={colaborador.pk}"
            elif RhColaborador.objects.filter(gerente=colaborador, is_active=True).exists():
                treinamentos_scope_qs = f"gerente={colaborador.pk}"
            else:
                treinamentos_scope_qs = f"colaborador_id={colaborador.pk}"
    except Exception:
        treinamentos_scope_qs = ""

    planejamentos_qs = ""
    if not is_global_viewer and colaborador:
        planejamentos_qs = f"instrutor={colaborador.pk}&status=pendentes"

    def can_show(module_key: str, view_name: str) -> bool:
        try:
            return bool(has_module_access(user, module_key) and has_view_access(user, view_name))
        except Exception:
            return False

    items: list[CobrancaItem] = []

    if can_show("metrologia", "modulo_metrologia"):
        items.append(
            CobrancaItem(
                key="metrologia",
                label="Metrologia (calibrações vencidas)",
                count=int(counts.get("metrologia", 0) or 0),
                url=with_qs(_safe_reverse("modulo_metrologia"), "status=vencidos"),
                section="Metrologia",
            )
        )

    if can_show("metrologia", "metrologia:solicitacao_list"):
        items.append(
            CobrancaItem(
                key="cotacoes",
                label="Cotações (prazo vencido)",
                count=int(counts.get("cotacoes", 0) or 0),
                url=with_qs(_safe_reverse("metrologia:solicitacao_list"), "cobranca=prazo_vencido"),
                section="Metrologia",
            )
        )

    if can_show("auditoria", "auditoria:selecionar_modelo_preenchimento"):
        items.append(
            CobrancaItem(
                key="auditoria",
                label="Auditoria (a realizar)",
                count=int(counts.get("auditoria", 0) or 0),
                url=with_qs(_safe_reverse("auditoria:selecionar_modelo_preenchimento"), "pendentes=mes"),
                section="Auditoria",
            )
        )

    if can_show("procedures", "procedures:validacoes_pendentes"):
        items.append(
            CobrancaItem(
                key="trein_matriz",
                label="Matriz de Habilidade (Cobrança ao líder mensalmente)",
                count=int(counts.get("trein_matriz", 0) or 0),
                url=_safe_reverse("procedures:validacoes_pendentes"),
                section="Treinamentos",
            )
        )

    if can_show("procedures", "procedures:dashboard_treinamentos"):
        items.append(
            CobrancaItem(
                key="trein_demanda",
                label="Demanda de Treinamento (Cobrar as pendências de treinamento)",
                count=int(counts.get("trein_demanda", 0) or 0),
                url=with_qs(_safe_reverse("procedures:dashboard_treinamentos"), treinamentos_scope_qs),
                section="Treinamentos",
            )
        )

    if can_show("procedures", "procedures:planejamentos_list"):
        items.append(
            CobrancaItem(
                key="trein_planejamentos",
                label="Planejamentos (Notificações sobre os prazos dos treinamentos planejados)",
                count=int(counts.get("trein_planejamentos", 0) or 0),
                url=with_qs(_safe_reverse("procedures:planejamentos_list"), planejamentos_qs),
                section="Treinamentos",
            )
        )

    return items
