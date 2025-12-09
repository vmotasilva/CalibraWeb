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
