from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Allows dict[key] lookups in Django templates: {{ mydict|get_item:key }}"""
    return dictionary.get(key)


@register.filter
def pc(valor, casas=2):
    """Percentual ou '–' quando não há base de cálculo (None): {{ linha.rend|pc }}"""
    if valor is None or valor == "":
        return "–"
    return f"{float(valor):.{int(casas)}f}%".replace(".", ",")


@register.filter
def milhar(valor):
    """Inteiro com separador de milhar (pt-BR)."""
    try:
        return f"{int(valor):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "–"


@register.filter
def cor_meta(valor, meta):
    """Classe de cor do rendimento frente à meta: verde (>= meta), amarelo (até 3 pontos abaixo), vermelho."""
    try:
        v, m = float(valor), float(meta)
    except (TypeError, ValueError):
        return "text-muted"
    return "text-success" if v >= m else ("text-warning" if v >= m - 3 else "text-danger")
