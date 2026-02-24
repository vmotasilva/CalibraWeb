from __future__ import annotations

from typing import Any

from .notifications import get_user_cobrancas_counts


def nav_notifications(request: Any) -> dict[str, int]:
    """Context processor para navbar.

    Exponibiliza um total de notificações de cobranças (itens que pedem mudança de status/atenção).
    """

    user = getattr(request, "user", None)
    counts = get_user_cobrancas_counts(user)
    total = int(counts.get("total", 0) or 0)
    return {
        "nav_notifications_total": total,
    }
