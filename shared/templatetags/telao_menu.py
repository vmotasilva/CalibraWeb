from django import template

from shared.models import FavoritoApresentacao
from shared.telao import providers

register = template.Library()


@register.inclusion_tag("shared/_telao_menu.html", takes_context=True)
def telao_menu(context):
    """Itens do menu ▶: acesso rápido (favoritos do usuário), Apresentação Geral e gerenciamento."""
    user = context.get("user") or getattr(context.get("request"), "user", None)
    try:
        ids = list(FavoritoApresentacao.objects.filter(usuario=user).values_list("modelo_id", flat=True)) if user is not None else []
        visiveis = {m.pk: m for m in providers.modelos_visiveis(user)} if ids else {}
        favoritos = [visiveis[i] for i in ids if i in visiveis]
    except Exception:
        favoritos = []
    return {"favoritos": favoritos}
