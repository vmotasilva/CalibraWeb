from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Case, DateField, F, QuerySet, When
from django.db.models.functions import Greatest
from django.utils import timezone


@dataclass(frozen=True)
class OverdueUpdateResult:
    updated_count: int


def _effective_deadline_expr(*, d1_field: str, d2_field: str):
    """Compute effective deadline as the most recent (max) of two date fields.

    Handles nulls by falling back to whichever field is set.
    """

    return Case(
        When(
            **{f"{d1_field}__isnull": False, f"{d2_field}__isnull": False},
            then=Greatest(F(d1_field), F(d2_field)),
        ),
        When(**{f"{d2_field}__isnull": False}, then=F(d2_field)),
        When(**{f"{d1_field}__isnull": False}, then=F(d1_field)),
        default=None,
        output_field=DateField(),
    )


def bulk_mark_overdue_as_retardo(
    queryset: QuerySet,
    *,
    status_field: str = "status",
    allowed_statuses=("planejada", "em_curso"),
    overdue_status: str = "retardo",
    d1_field: str = "data_primeira_deadline",
    d2_field: str = "data_deadline",
    today=None,
) -> OverdueUpdateResult:
    """Bulk update: set status to `retardo` when deadline has passed.

    Rule:
    - only records with status in allowed_statuses
    - effective deadline = max(d1, d2) with null fallback
    - if effective deadline < today => set to overdue_status

    Notes:
    - This is intentionally one-way (does not revert from retardo automatically).
    """

    if today is None:
        today = timezone.localdate()

    effective_deadline = _effective_deadline_expr(d1_field=d1_field, d2_field=d2_field)

    status_filter = {f"{status_field}__in": allowed_statuses}
    overdue_filter = {"effective_deadline__lt": today}

    qs = queryset.annotate(effective_deadline=effective_deadline).filter(**status_filter).filter(**overdue_filter)
    updated = qs.update(**{status_field: overdue_status})

    return OverdueUpdateResult(updated_count=updated)
