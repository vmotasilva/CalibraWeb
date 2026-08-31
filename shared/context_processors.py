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

    Exponibiliza contagem total e agrupamento por origem/módulo para o dropdown do sino.
    """
    user = getattr(request, "user", None)
    
    from shared.inbox import get_user_inbox_items
    from django.utils.text import slugify
    from collections import OrderedDict
    
    inbox_items = get_user_inbox_items(user)
    total = len(inbox_items)
    
    # Agrupar itens por origem / módulo para o dropdown do sino
    module_icons = {
        "auditoria": "bi-clipboard-check",
        "quadros": "bi-kanban",
        "metrologia": "bi-tools",
        "treinamentos": "bi-mortarboard",
        "fornecedores": "bi-truck",
        "laboratorio": "bi-droplet-half",
        "pessoas": "bi-people",
    }

    origins_map: dict[str, dict[str, Any]] = OrderedDict()
    for item in inbox_items:
        mod_name = (item.module or "Outros").strip().capitalize()
        mod_key = mod_name.lower()
        if mod_key not in origins_map:
            icon = module_icons.get(mod_key, item.icon or "bi-bell")
            origins_map[mod_key] = {
                "name": mod_name,
                "slug": slugify(mod_name),
                "count": 0,
                "icon": icon,
                "sub_origins": OrderedDict(),
            }
        origins_map[mod_key]["count"] += 1

        sub_name = (item.sub_type or "Geral").strip()
        sub_slug = slugify(sub_name)
        if sub_slug not in origins_map[mod_key]["sub_origins"]:
            origins_map[mod_key]["sub_origins"][sub_slug] = {
                "name": sub_name,
                "slug": sub_slug,
                "count": 0,
            }
        origins_map[mod_key]["sub_origins"][sub_slug]["count"] += 1

    # Converter sub_origins em lista para iteração nos templates
    for mod_data in origins_map.values():
        mod_data["sub_origins_list"] = list(mod_data["sub_origins"].values())

    nav_inbox_origins = list(origins_map.values())

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
        "nav_inbox_origins": nav_inbox_origins,
        "nav_inbox_items": inbox_items[:5],
        "unread_board_mentions_count": unread_board_mentions_count,
    }


def system_version(request: Any) -> dict[str, Any]:
    """Provide system version to all templates."""
    
    changelog = []
    try:
        import json
        from django.conf import settings
        import os
        
        changelog_path = os.path.join(settings.BASE_DIR, 'changelog.json')
        with open(changelog_path, 'r', encoding='utf-8') as f:
            changelog = json.load(f)
    except Exception:
        pass

    return {
        "system_version": getattr(settings, "SYSTEM_VERSION", "1.0.0"),
        "system_changelog": changelog
    }
