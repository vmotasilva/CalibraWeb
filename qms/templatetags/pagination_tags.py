"""
Django template tags for pagination controls.

Usage in templates:
    {% load pagination_tags %}
    {% render_pagination pagination %}
    {% pagination_links pagination url_name %}
"""

from django import template
from django.utils.html import format_html
from django.urls import reverse
from urllib.parse import urlencode

register = template.Library()


@register.inclusion_tag('qms/partials/pagination.html')
def render_pagination(pagination, query_params=None):
    """Render pagination controls."""
    if query_params is None:
        query_params = {}
    
    return {
        'pagination': pagination,
        'query_params': query_params,
    }


@register.simple_tag
def pagination_url(current_page, query_dict, page_number=None):
    """Generate pagination URL with query parameters preserved."""
    params = query_dict.copy()
    
    if page_number:
        params['page'] = page_number
    elif 'page' in params:
        del params['page']
    
    if params:
        return f"?{urlencode(params)}"
    return "?"


@register.filter
def page_range(pagination, window=5):
    """
    Return a range of page numbers with a sliding window around current page.
    
    Example: If showing pages 1-100 and current page is 50, shows 45-55.
    """
    current = pagination['current_page']
    total = pagination['total_pages']
    
    # Calculate range
    start = max(1, current - window)
    end = min(total, current + window)
    
    # Expand to full window if near boundaries
    if start == 1:
        end = min(total, end + (window - (current - start)))
    if end == total:
        start = max(1, start - (window - (end - current)))
    
    return range(start, end + 1)


@register.filter
def has_prev_page(pagination):
    """Check if there is a previous page."""
    return pagination.get('has_previous', False)


@register.filter
def has_next_page(pagination):
    """Check if there is a next page."""
    return pagination.get('has_next', False)


@register.filter
def prev_page_number(pagination):
    """Get previous page number."""
    return pagination.get('previous_page')


@register.filter
def next_page_number(pagination):
    """Get next page number."""
    return pagination.get('next_page')


@register.simple_tag
def pagination_summary(pagination):
    """Generate pagination summary text."""
    current = pagination.get('current_page', 1)
    total_pages = pagination.get('total_pages', 1)
    total_items = pagination.get('total_items', 0)
    page_size = pagination.get('page_size', 0)
    
    start_item = (current - 1) * page_size + 1
    end_item = min(current * page_size, total_items)
    
    return f"Exibindo {start_item}-{end_item} de {total_items} itens (Página {current} de {total_pages})"


@register.inclusion_tag('qms/partials/pagination_buttons.html')
def pagination_buttons(pagination, query_params=None):
    """Render pagination navigation buttons."""
    if query_params is None:
        query_params = {}
    
    return {
        'pagination': pagination,
        'query_params': query_params,
        'prev_page': pagination.get('previous_page'),
        'next_page': pagination.get('next_page'),
        'current_page': pagination.get('current_page'),
        'total_pages': pagination.get('total_pages'),
    }


@register.simple_tag
def page_link_class(page_number, current_page):
    """Return CSS class for page link."""
    if page_number == current_page:
        return 'active'
    return ''
