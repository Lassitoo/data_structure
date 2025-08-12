# crée le dossier documents/templatetags/ avec un __init__.py vide si besoin
from django import template

register = template.Library()

@register.filter
def classname(obj):
    """Retourne le nom de classe Python de l'objet (ex: 'TextInput')."""
    try:
        return obj.__class__.__name__
    except Exception:
        return ""
