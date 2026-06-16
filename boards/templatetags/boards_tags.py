from django import template

register = template.Library()

@register.filter
def filter_concluido(queryset):
    """Filtra os itens de checklist que estão concluídos"""
    if hasattr(queryset, 'filter'):
        return queryset.filter(concluido=True)
    # Se for uma lista comum (ex: prefetch list)
    return [item for item in queryset if getattr(item, 'concluido', False)]

@register.filter
def percent(value, total):
    """Calcula a porcentagem concluída de subtarefas"""
    try:
        val = int(value)
        tot = int(total)
        if tot > 0:
            return int((val / tot) * 100)
    except (ValueError, TypeError, ZeroDivisionError):
        pass
    return 0
