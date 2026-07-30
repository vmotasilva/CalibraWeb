from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Allows dict[key] lookups in Django templates: {{ mydict|get_item:key }}"""
    return dictionary.get(key)
