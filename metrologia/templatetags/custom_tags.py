from django import template
from datetime import timedelta

register = template.Library()

@register.filter
def add_days(date_value, days):
    """Add days to a date"""
    if not date_value:
        return None
    try:
        return date_value + timedelta(days=int(days))
    except (TypeError, ValueError):
        return None

@register.filter
def get_ponto(faixa_item, index):
    """Get point value from ItemSolicitacaoFaixa"""
    if not faixa_item:
        return None
    try:
        ponto_attr = f'ponto_{index}'
        value = getattr(faixa_item, ponto_attr, None)
        if value:
            return f"{float(value):.4f}"
        return None
    except (AttributeError, ValueError, TypeError):
        return None
