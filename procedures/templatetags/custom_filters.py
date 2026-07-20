from django import template

register = template.Library()


@register.filter
def get_from_dict(dictionary, key):
    """
    Retorna o valor de uma chave em um dicionário
    Uso: {{ dict|get_from_dict:key }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None


@register.filter
def get_attr(obj, attr):
    """
    Retorna um atributo de um objeto
    Uso: {{ obj|get_attr:'atributo' }}
    """
    try:
        return getattr(obj, attr, None)
    except Exception:
        return None


@register.filter
def add_class(field, css_class):
    """
    Adiciona classe CSS a um campo de formulário
    Uso: {{ form.field|add_class:"css-class" }}
    """
    return field.as_widget(attrs={"class": css_class})


@register.filter
def dict_get(dictionary, key):
    """
    Obtém um item de um dicionário usando um filtro no template.
    Uso: {{ dict|dict_get:key }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter
def get_dict_key(dictionary, key):
    """Alias para dict_get - compatibilidade backwards."""
    return dict_get(dictionary, key)


@register.filter
def get_nested_item(data, keys):
    """
    Obtém um item aninhado de um dicionário.
    Uso: {{ data|get_nested_item:"key1.key2" }}
    """
    if data is None:
        return None
    
    key_list = str(keys).split('.')
    value = data
    
    for key in key_list:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None
    
    return value

