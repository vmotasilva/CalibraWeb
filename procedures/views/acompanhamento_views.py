from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from procedures.models import PlanejamentoTreinamento


@dataclass(frozen=True)
class CalendarDay:
    day: int
    date: date | None
    planejamentos: list[PlanejamentoTreinamento]


@login_required
def calendario_treinamentos_view(request):
    """Calendário simples (mês) com planejamentos por data prevista."""

    today = timezone.localdate()

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

    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])

    planejamentos_qs = (
        PlanejamentoTreinamento.objects.select_related("instrutor")
        .prefetch_related("colaboradores")
        .filter(data_prevista__range=(first_day, last_day))
        .order_by("data_prevista", "horario_previsto", "titulo")
    )

    by_date: dict[date, list[PlanejamentoTreinamento]] = {}
    for planejamento in planejamentos_qs:
        by_date.setdefault(planejamento.data_prevista, []).append(planejamento)

    cal = calendar.Calendar(firstweekday=6)  # domingo
    weeks: list[list[CalendarDay]] = []
    for week in cal.monthdayscalendar(year, month):
        week_days: list[CalendarDay] = []
        for day_num in week:
            if day_num == 0:
                week_days.append(CalendarDay(day=0, date=None, planejamentos=[]))
                continue

            day_date = date(year, month, day_num)
            week_days.append(
                CalendarDay(
                    day=day_num,
                    date=day_date,
                    planejamentos=by_date.get(day_date, []),
                )
            )
        weeks.append(week_days)

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

    context = {
        "year": year,
        "month": month,
        "current_month": first_day,
        "weeks": weeks,
        "today": today,
        "prev_year": prev_year,
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,
    }

    return render(request, "procedures/calendario_treinamentos.html", context)
