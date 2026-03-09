from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from procedures.models import ListaPresenca, PlanejamentoTreinamento


@dataclass(frozen=True)
class CalendarEvent:
    kind: str  # "planned" | "registered"
    title: str
    start_time: str
    badge_class: str
    badge_label: str
    url: str


@dataclass(frozen=True)
class CalendarDay:
    day: int
    date: date | None
    events: list[CalendarEvent]


def _parse_iso_date(value: str | None, default: date) -> date:
    if not value:
        return default
    try:
        return date.fromisoformat(value)
    except ValueError:
        return default


def _format_time(value) -> str:
    if not value:
        return ""
    try:
        return value.strftime("%H:%M")
    except Exception:
        return ""


def _week_start_sunday(d: date) -> date:
    # weekday(): Monday=0 .. Sunday=6 -> want Sunday as first day
    delta = (d.weekday() + 1) % 7
    return d - timedelta(days=delta)


def _planejamento_badge(status: str) -> tuple[str, str]:
    status_to_badge = {
        "PLANEJADO": "text-bg-secondary",
        "CONFIRMADO": "text-bg-primary",
        "REALIZADO": "text-bg-success",
        "CANCELADO": "text-bg-dark",
        "ATRASADO": "text-bg-warning",
    }
    badge_class = status_to_badge.get(status, "text-bg-secondary")
    label_map = {
        "PLANEJADO": "Planejado",
        "CONFIRMADO": "Confirmado",
        "REALIZADO": "Realizado",
        "CANCELADO": "Cancelado",
        "ATRASADO": "Atrasado",
    }
    return badge_class, label_map.get(status, status)


@login_required
def calendario_treinamentos_view(request):
    """Calendário de treinamentos.

    - Planejados: PlanejamentoTreinamento (data_prevista)
    - Registrados: ListaPresenca (data_sessao)
    Suporta view=month|week|day.
    """

    today = timezone.localdate()

    view_mode = (request.GET.get("view") or "month").lower().strip()
    if view_mode not in {"month", "week", "day"}:
        view_mode = "month"

    ref_date = today

    year = today.year
    month = today.month

    if view_mode == "month":
        try:
            year = int(request.GET.get("year") or today.year)
        except (TypeError, ValueError):
            year = today.year

        try:
            month = int(request.GET.get("month") or today.month)
        except (TypeError, ValueError):
            month = today.month

        if month < 1 or month > 12:
            month = today.month

        ref_date = date(year, month, 1)
        start_date = ref_date
        end_date = date(year, month, calendar.monthrange(year, month)[1])
    else:
        ref_date = _parse_iso_date(request.GET.get("date"), default=today)
        year = ref_date.year
        month = ref_date.month

        if view_mode == "week":
            start_date = _week_start_sunday(ref_date)
            end_date = start_date + timedelta(days=6)
        else:
            start_date = ref_date
            end_date = ref_date

    planejamentos_qs = (
        PlanejamentoTreinamento.objects.select_related("instrutor")
        .prefetch_related("colaboradores")
        .filter(data_prevista__range=(start_date, end_date))
        .order_by("data_prevista", "horario_previsto", "titulo")
    )

    listas_qs = (
        ListaPresenca.objects.select_related("instrutor")
        .filter(data_sessao__range=(start_date, end_date))
        .order_by("data_sessao", "hora_inicio", "titulo")
    )

    by_date: dict[date, list[CalendarEvent]] = {}

    for planejamento in planejamentos_qs:
        badge_class, badge_label = _planejamento_badge(planejamento.status)
        by_date.setdefault(planejamento.data_prevista, []).append(
            CalendarEvent(
                kind="planned",
                title=planejamento.titulo,
                start_time=_format_time(planejamento.horario_previsto),
                badge_class=badge_class,
                badge_label=badge_label,
                url=reverse(
                    "procedures:detalhe_planejamento",
                    kwargs={"planejamento_id": planejamento.id},
                ),
            )
        )

    for lista in listas_qs:
        by_date.setdefault(lista.data_sessao, []).append(
            CalendarEvent(
                kind="registered",
                title=lista.titulo,
                start_time=_format_time(lista.hora_inicio),
                badge_class="text-bg-info",
                badge_label="Registrado",
                url=reverse("procedures:lista_presenca_detail", kwargs={"pk": lista.pk}),
            )
        )

    for events in by_date.values():
        events.sort(key=lambda e: (e.start_time or "99:99", e.title.lower()))

    weeks: list[list[CalendarDay]] = []

    if view_mode == "day":
        weeks = [[CalendarDay(day=ref_date.day, date=ref_date, events=by_date.get(ref_date, []))]]
    elif view_mode == "week":
        start = start_date
        week_days: list[CalendarDay] = []
        for offset in range(7):
            d = start + timedelta(days=offset)
            week_days.append(CalendarDay(day=d.day, date=d, events=by_date.get(d, [])))
        weeks = [week_days]
    else:
        cal = calendar.Calendar(firstweekday=6)  # domingo
        for week in cal.monthdayscalendar(year, month):
            week_days: list[CalendarDay] = []
            for day_num in week:
                if day_num == 0:
                    week_days.append(CalendarDay(day=0, date=None, events=[]))
                    continue
                day_date = date(year, month, day_num)
                week_days.append(
                    CalendarDay(
                        day=day_num,
                        date=day_date,
                        events=by_date.get(day_date, []),
                    )
                )
            weeks.append(week_days)

    if view_mode == "month":
        prev_month = month - 1
        prev_year = year
        if prev_month == 0:
            prev_month = 12
            prev_year -= 1

        next_month = month + 1
        next_year = year
        if next_month == 13:
            next_month = 1
            next_year += 1

        prev_url = f"?view=month&year={prev_year}&month={prev_month}"
        next_url = f"?view=month&year={next_year}&month={next_month}"
        today_url = f"?view=month&year={today.year}&month={today.month}"
    elif view_mode == "week":
        prev_url = f"?view=week&date={(ref_date - timedelta(days=7)).isoformat()}"
        next_url = f"?view=week&date={(ref_date + timedelta(days=7)).isoformat()}"
        today_url = f"?view=week&date={today.isoformat()}"
    else:
        prev_url = f"?view=day&date={(ref_date - timedelta(days=1)).isoformat()}"
        next_url = f"?view=day&date={(ref_date + timedelta(days=1)).isoformat()}"
        today_url = f"?view=day&date={today.isoformat()}"

    month_url = f"?view=month&year={ref_date.year}&month={ref_date.month}"
    week_url = f"?view=week&date={ref_date.isoformat()}"
    day_url = f"?view=day&date={ref_date.isoformat()}"

    context = {
        "view_mode": view_mode,
        "year": year,
        "month": month,
        "current_month": date(year, month, 1),
        "weeks": weeks,
        "today": today,
        "ref_date": ref_date,
        "start_date": start_date,
        "end_date": end_date,
        "prev_url": prev_url,
        "next_url": next_url,
        "today_url": today_url,
        "month_url": month_url,
        "week_url": week_url,
        "day_url": day_url,
    }

    return render(request, "procedures/calendario_treinamentos.html", context)
