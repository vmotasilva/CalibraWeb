from django import template

register = template.Library()

@register.filter
def get_dict_key(dictionary, key):
    """Retorna o valor de uma chave do dicionário, ou None se não existir."""
    if dictionary is None:
        return None
    return dictionary.get(key)
