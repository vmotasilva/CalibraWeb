from __future__ import annotations

from typing import Any

from .notifications import get_user_cobrancas_counts


def _is_mobile_user_agent(user_agent: str) -> bool:
    """Heurística simples para identificar celular/tablet via User-Agent.

    Objetivo: escolher um template otimizado para telas menores sem depender
    de libs externas. Tablets são tratados como "mobile" (layout compacto).
    """

    if not user_agent:
        return False

    ua = user_agent.lower()

    # Tablets
    if "ipad" in ua or "tablet" in ua or "kindle" in ua or "silk/" in ua:
        return True

    # Celulares (e também muitos tablets Android)
    mobile_tokens = [
        "mobi",
        "mobile",
        "iphone",
        "ipod",
        "android",
        "windows phone",
        "iemobile",
        "blackberry",
        "bb10",
        "opera mini",
        "opera mobi",
        "fennec",
    ]
    return any(token in ua for token in mobile_tokens)


def template_variants(request: Any) -> dict[str, Any]:
    """Context processor: escolhe templates base por tipo de dispositivo."""

    user_agent = ""
    try:
        user_agent = request.META.get("HTTP_USER_AGENT", "")
    except Exception:
        user_agent = ""

    is_mobile = _is_mobile_user_agent(user_agent)
    return {
        "is_mobile": is_mobile,
        "base_template": "base_mobile.html" if is_mobile else "base_desktop.html",
        "base_auth_template": "base_auth_mobile.html" if is_mobile else "base_auth_desktop.html",
    }


def nav_notifications(request: Any) -> dict[str, Any]:
    """Context processor para navbar.

    Exponibiliza um total de notificações de cobranças (itens que pedem mudança de status/atenção).
    """

    user = getattr(request, "user", None)
    
    # We use the new Inbox items instead of just raw counts
    from shared.inbox import get_user_inbox_items
    inbox_items = get_user_inbox_items(user)
    
    total = len(inbox_items)
    
    # Optional: fetch old counts just in case it's used elsewhere, but total comes from inbox now.
    counts = get_user_cobrancas_counts(user)
    
    unread_board_mentions_count = 0
    if user and user.is_authenticated:
        try:
            from boards.models import BoardMention
            from rh.models import Colaborador
            colab = Colaborador.objects.filter(usuario=user).first()
            if colab:
                unread_board_mentions_count = BoardMention.objects.filter(mencionado=colab, visualizada=False).count()
        except Exception:
            pass
            
    return {
        "nav_notifications_total": total,
        "nav_inbox_items": inbox_items[:5], # Take top 5 most urgent
        "unread_board_mentions_count": unread_board_mentions_count,
    }


def system_version(request: Any) -> dict[str, str]:
    """Context processor: disponibiliza a versão do sistema globalmente."""
    from django.conf import settings
    return {
        "system_version": getattr(settings, "SYSTEM_VERSION", "1.0.0"),
    }
