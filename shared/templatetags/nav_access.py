from __future__ import annotations

from django import template

from shared.permissions import (
    has_block_nav_flag,
    has_module_access,
    has_view_access,
    user_has_any_nav_perm_for_module,
)

register = template.Library()


@register.simple_tag
def can_nav_module(user, module_key: str) -> bool:
    """True se o módulo deve aparecer no navbar para o usuário."""
    return bool(has_module_access(user, module_key))


@register.simple_tag
def can_nav_block(user, module_key: str, block_key: str) -> bool:
    """True se o bloco deve aparecer no navbar.

    Compatibilidade:
    - Se o usuário está no modo legado (sem nenhum nav_* do módulo), não esconde blocos.
    """
    if not has_module_access(user, module_key):
        return False

    if not user_has_any_nav_perm_for_module(user, module_key):
        return True

    return bool(has_block_nav_flag(user, module_key, block_key))


@register.simple_tag
def can_nav_view(user, view_name: str, module_key: str | None = None) -> bool:
    """True se o item/função deve aparecer no navbar.

    Se module_key for informado, aplica fallback legado (grupo do módulo) quando
    o usuário ainda não tem nenhum nav_* configurado.
    """
    if module_key and (not has_module_access(user, module_key)):
        return False

    return bool(has_view_access(user, view_name))
