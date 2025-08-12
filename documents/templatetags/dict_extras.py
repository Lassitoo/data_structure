from django import template

register = template.Library()

@register.filter(name="lookup")
def lookup(dictionary, key):
    """
    dict lookup dynamique: {{ my_dict|lookup:my_key }}
    """
    try:
        if isinstance(dictionary, dict):
            return dictionary.get(key, None)
    except Exception:
        pass
    return None

@register.filter(name="get_item")
def get_item(dictionary, key):
    """
    alias de lookup
    """
    return lookup(dictionary, key)
