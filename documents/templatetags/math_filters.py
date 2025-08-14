from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    """Multiplie deux valeurs"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def divide(value, arg):
    """Divise deux valeurs"""
    try:
        if float(arg) == 0:
            return 0
        return float(value) / float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def subtract(value, arg):
    """Soustrait deux valeurs"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def add_filter(value, arg):
    """Additionne deux valeurs"""
    try:
        return float(value) + float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def percentage(value, total):
    """Calcule un pourcentage"""
    try:
        if float(total) == 0:
            return 0
        return round((float(value) * 100) / float(total), 1)
    except (ValueError, TypeError):
        return 0