from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from django.core.cache import cache
from django.urls import reverse
from urllib.parse import quote_plus


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
        from auditoria.models import ModeloAuditoria, RegistroAuditoria
        from django.db.models import Exists, OuterRef, Q

        month_start = _first_day_of_month(hoje)
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)

        modelos = ModeloAuditoria.objects.filter(ativo=True)
        if not is_global_viewer:
            modelos = modelos.filter(Q(responsavel=user) | Q(responsaveis=user)).distinct()

        registro_mes_qs = RegistroAuditoria.objects.filter(
            modelo_id=OuterRef("pk"),
            data_auditoria__gte=month_start,
            data_auditoria__lt=next_month,
        )
        registro_algum_qs = RegistroAuditoria.objects.filter(modelo_id=OuterRef("pk"))

        modelos = modelos.annotate(
            _tem_registro_mes=Exists(registro_mes_qs),
            _tem_registro_algum=Exists(registro_algum_qs),
        )

        counts["auditoria"] = modelos.filter(
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
        ).count()
    except Exception:
        counts["auditoria"] = 0

    # Insumos: modelos atribuídos ao usuário que estão "em atraso" pela periodicidade
    try:
        from insumos.models import ModeloAuditoria as ModeloInsumos, RegistroAuditoria as RegistroInsumos
        from django.db.models import Exists, OuterRef, Q

        month_start = _first_day_of_month(hoje)
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)

        modelos = ModeloInsumos.objects.filter(ativo=True)
        if not is_global_viewer:
            modelos = modelos.filter(Q(responsavel=user) | Q(responsaveis=user)).distinct()

        registro_mes_qs = RegistroInsumos.objects.filter(
            modelo_id=OuterRef("pk"),
            data_auditoria__gte=month_start,
            data_auditoria__lt=next_month,
        )
        registro_algum_qs = RegistroInsumos.objects.filter(modelo_id=OuterRef("pk"))

        modelos = modelos.annotate(
            _tem_registro_mes=Exists(registro_mes_qs),
            _tem_registro_algum=Exists(registro_algum_qs),
        )

        counts["insumos"] = modelos.filter(
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
        ).count()
    except Exception:
        counts["insumos"] = 0

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

    return [
        CobrancaItem(
            key="metrologia",
            label="Metrologia (calibrações vencidas)",
            count=int(counts.get("metrologia", 0) or 0),
            url=with_qs(_safe_reverse("modulo_metrologia"), "status=vencidos"),
            section="Metrologia",
        ),
        CobrancaItem(
            key="cotacoes",
            label="Cotações (prazo vencido)",
            count=int(counts.get("cotacoes", 0) or 0),
            url=with_qs(_safe_reverse("metrologia:solicitacao_list"), "cobranca=prazo_vencido"),
            section="Metrologia",
        ),
        CobrancaItem(
            key="acoes",
            label="Ações (vencidas)",
            count=int(counts.get("acoes", 0) or 0),
            url=with_qs(
                _safe_reverse("acoes:acoes_registradas"),
                "&".join(
                    [p for p in [
                        "status=pendentes",
                        qs_param("responsavel", acoes_responsavel),
                        "ordenar=deadline",
                    ] if p]
                ),
            ),
            section="Ações",
        ),
        CobrancaItem(
            key="auditoria",
            label="Auditoria (a realizar)",
            count=int(counts.get("auditoria", 0) or 0),
            url=with_qs(_safe_reverse("auditoria:selecionar_modelo_preenchimento"), "pendentes=mes"),
            section="Auditoria e Insumos",
        ),
        CobrancaItem(
            key="insumos",
            label="Insumos (a realizar)",
            count=int(counts.get("insumos", 0) or 0),
            url=with_qs(_safe_reverse("insumos:selecionar_modelo_preenchimento"), "pendentes=mes"),
            section="Auditoria e Insumos",
        ),
        CobrancaItem(
            key="trein_matriz",
            label="Matriz de Habilidade (Cobrança ao líder mensalmente)",
            count=int(counts.get("trein_matriz", 0) or 0),
            url=_safe_reverse("procedures:validacoes_pendentes"),
            section="Treinamentos",
        ),
        CobrancaItem(
            key="trein_demanda",
            label="Demanda de Treinamento (Cobrar as pendências de treinamento)",
            count=int(counts.get("trein_demanda", 0) or 0),
            url=with_qs(_safe_reverse("procedures:dashboard_treinamentos"), treinamentos_scope_qs),
            section="Treinamentos",
        ),
        CobrancaItem(
            key="trein_planejamentos",
            label="Planejamentos (Notificações sobre os prazos dos treinamentos planejados)",
            count=int(counts.get("trein_planejamentos", 0) or 0),
            url=with_qs(_safe_reverse("procedures:planejamentos_list"), planejamentos_qs),
            section="Treinamentos",
        ),
    ]
