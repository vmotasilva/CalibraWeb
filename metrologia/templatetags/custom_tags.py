from django import template
from datetime import timedelta
from django.utils.html import format_html

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

@register.filter
def safe_filesize(file_field):
    """Get file size safely, handling missing files - returns formatted size or error message"""
    if not file_field:
        return "-"
    try:
        # Check if file exists
        if file_field.storage.exists(file_field.name):
            size = file_field.size
            # Format bytes to human readable
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    return format_html("{:.1f} {}", size, unit)
                size /= 1024.0
            return format_html("{:.1f} TB", size)
        else:
            return format_html('<span class="text-danger"><i class="bi bi-exclamation-circle"></i> Arquivo não encontrado</span>')
    except Exception:
        return format_html('<span class="text-warning"><i class="bi bi-question-circle"></i> Tamanho indisponível</span>')
