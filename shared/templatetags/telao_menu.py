from django import template

from shared.telao import providers

register = template.Library()


@register.inclusion_tag("shared/_telao_menu.html", takes_context=True)
def telao_menu(context):
    """Itens do menu ▶: padrões fixos + modelos de apresentação personalizados que o usuário pode rodar."""
    user = context.get("user") or getattr(context.get("request"), "user", None)
    try:
        personalizados = list(providers.modelos_visiveis(user)) if user is not None else []
    except Exception:
        personalizados = []
    return {"personalizados": personalizados}
