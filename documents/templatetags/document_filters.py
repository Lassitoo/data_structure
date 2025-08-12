from django import template
from django.utils.safestring import mark_safe
from django.utils.html import format_html
import json
import re

register = template.Library()


@register.filter
def lookup(dictionary, key):
    """
    Template filter pour accéder aux valeurs d'un dictionnaire avec une clé dynamique
    Usage: {{ my_dict|lookup:key_variable }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key, '')
    return ''


@register.filter
def multiply(value, factor):
    """
    Multiplie une valeur par un facteur
    Usage: {{ value|multiply:10 }}
    """
    try:
        return float(value) * float(factor)
    except (ValueError, TypeError):
        return 0


@register.filter
def divide(value, divisor):
    """
    Divise une valeur par un diviseur
    Usage: {{ value|divide:10 }}
    """
    try:
        return float(value) / float(divisor)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0


@register.filter
def percentage(value, total):
    """
    Calcule un pourcentage
    Usage: {{ value|percentage:total }}
    """
    try:
        return (float(value) / float(total)) * 100
    except (ValueError, TypeError, ZeroDivisionError):
        return 0


@register.filter
def status_color(status):
    """
    Retourne la couleur Bootstrap appropriée pour un statut
    Usage: {{ document.status|status_color }}
    """
    colors = {
        'uploaded': 'info',
        'metadata_extracted': 'primary',
        'schema_proposed': 'warning',
        'schema_validated': 'success',
        'pre_annotated': 'warning',
        'annotated': 'primary',
        'validated': 'success',
    }
    return colors.get(status, 'secondary')


@register.filter
def file_icon(file_type):
    """
    Retourne l'icône Font Awesome appropriée pour un type de fichier
    Usage: {{ document.file_type|file_icon }}
    """
    icons = {
        'pdf': 'fas fa-file-pdf text-danger',
        'docx': 'fas fa-file-word text-primary',
        'doc': 'fas fa-file-word text-primary',
        'xlsx': 'fas fa-file-excel text-success',
        'xls': 'fas fa-file-excel text-success',
        'txt': 'fas fa-file-alt text-secondary',
        'image': 'fas fa-file-image text-warning',
    }
    return icons.get(file_type, 'fas fa-file text-secondary')


@register.filter
def format_duration(seconds):
    """
    Formate une durée en secondes en format lisible
    Usage: {{ duration_seconds|format_duration }}
    """
    try:
        seconds = int(seconds)
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes}m {seconds % 60}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"
    except (ValueError, TypeError):
        return "0s"


@register.filter
def highlight_search(text, search_term):
    """
    Met en surbrillance les termes de recherche dans un texte
    Usage: {{ text|highlight_search:query }}
    """
    if not search_term or not text:
        return text

    # Échapper les caractères spéciaux regex
    escaped_term = re.escape(search_term)
    pattern = re.compile(f'({escaped_term})', re.IGNORECASE)

    highlighted = pattern.sub(r'<mark class="bg-warning">\1</mark>', str(text))
    return mark_safe(highlighted)


@register.filter
def progress_color(percentage):
    """
    Retourne la couleur de barre de progression selon le pourcentage
    Usage: {{ completion_percentage|progress_color }}
    """
    try:
        pct = float(percentage)
        if pct >= 80:
            return 'success'
        elif pct >= 60:
            return 'info'
        elif pct >= 40:
            return 'warning'
        else:
            return 'danger'
    except (ValueError, TypeError):
        return 'secondary'


@register.filter
def json_pretty(value):
    """
    Formate un dictionnaire/objet JSON de manière lisible
    Usage: {{ data|json_pretty }}
    """
    try:
        if isinstance(value, str):
            value = json.loads(value)
        return json.dumps(value, indent=2, ensure_ascii=False)
    except (json.JSONDecodeError, TypeError):
        return str(value)


@register.filter
def truncate_middle(value, length=50):
    """
    Tronque une chaîne au milieu en gardant le début et la fin
    Usage: {{ long_text|truncate_middle:30 }}
    """
    try:
        length = int(length)
        if len(str(value)) <= length:
            return value

        half = (length - 3) // 2
        return f"{str(value)[:half]}...{str(value)[-half:]}"
    except (ValueError, TypeError):
        return value


@register.filter
def field_type_icon(field_type):
    """
    Retourne l'icône appropriée pour un type de champ d'annotation
    Usage: {{ field.field_type|field_type_icon }}
    """
    icons = {
        'text': 'fas fa-font',
        'number': 'fas fa-hashtag',
        'date': 'fas fa-calendar',
        'boolean': 'fas fa-toggle-on',
        'choice': 'fas fa-list',
        'multiple_choice': 'fas fa-check-square',
        'entity': 'fas fa-tag',
        'classification': 'fas fa-tags',
    }
    return icons.get(field_type, 'fas fa-question')


@register.filter
def format_file_size(bytes_size):
    """
    Formate une taille de fichier en bytes en format lisible
    Usage: {{ file_size|format_file_size }}
    """
    try:
        bytes_size = int(bytes_size)
        if bytes_size == 0:
            return "0 B"

        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while bytes_size >= 1024 and i < len(size_names) - 1:
            bytes_size /= 1024
            i += 1

        return f"{bytes_size:.1f} {size_names[i]}"
    except (ValueError, TypeError):
        return "0 B"


@register.filter
def confidence_color(score):
    """
    Retourne la couleur appropriée pour un score de confiance
    Usage: {{ confidence_score|confidence_color }}
    """
    try:
        score = float(score)
        if score >= 8:
            return 'success'
        elif score >= 6:
            return 'warning'
        else:
            return 'danger'
    except (ValueError, TypeError):
        return 'secondary'


@register.filter
def action_icon(action_type):
    """
    Retourne l'icône appropriée pour un type d'action d'historique
    Usage: {{ history.action_type|action_icon }}
    """
    icons = {
        'created': 'fas fa-plus text-success',
        'updated': 'fas fa-edit text-primary',
        'validated': 'fas fa-check text-success',
        'rejected': 'fas fa-times text-danger',
    }
    return icons.get(action_type, 'fas fa-circle text-secondary')


@register.filter
def smart_truncate(text, max_length=100):
    """
    Tronque intelligemment un texte en évitant de couper au milieu d'un mot
    Usage: {{ text|smart_truncate:50 }}
    """
    try:
        max_length = int(max_length)
        if len(str(text)) <= max_length:
            return text

        truncated = str(text)[:max_length]
        last_space = truncated.rfind(' ')

        if last_space > max_length * 0.8:  # Si l'espace est proche de la fin
            truncated = truncated[:last_space]

        return truncated + '...'
    except (ValueError, TypeError):
        return text


@register.simple_tag
def progress_bar(value, total, css_class="", show_percentage=True):
    """
    Génère une barre de progression HTML
    Usage: {% progress_bar current total "custom-class" True %}
    """
    try:
        percentage = (float(value) / float(total)) * 100 if total > 0 else 0
        color_class = progress_color(percentage)

        html = f'''
        <div class="progress {css_class}">
            <div class="progress-bar bg-{color_class}" 
                 style="width: {percentage}%" 
                 role="progressbar" 
                 aria-valuenow="{value}" 
                 aria-valuemin="0" 
                 aria-valuemax="{total}">
                {f"{percentage:.0f}%" if show_percentage else ""}
            </div>
        </div>
        '''
        return mark_safe(html)
    except (ValueError, TypeError):
        return mark_safe('<div class="progress"><div class="progress-bar" style="width: 0%"></div></div>')


@register.simple_tag
def status_badge(status, size=""):
    """
    Génère un badge pour un statut
    Usage: {% status_badge document.status "small" %}
    """
    color = status_color(status)
    size_class = f"badge-{size}" if size else ""

    status_labels = {
        'uploaded': 'Téléversé',
        'metadata_extracted': 'Métadonnées extraites',
        'schema_proposed': 'Schéma proposé',
        'schema_validated': 'Schéma validé',
        'pre_annotated': 'Pré-annoté',
        'annotated': 'Annoté',
        'validated': 'Validé',
    }

    label = status_labels.get(status, status.title())

    html = f'<span class="badge bg-{color} {size_class}">{label}</span>'
    return mark_safe(html)


@register.simple_tag
def user_avatar(user, size=32):
    """
    Génère un avatar pour un utilisateur
    Usage: {% user_avatar user 48 %}
    """
    initials = ""
    if user.first_name and user.last_name:
        initials = f"{user.first_name[0]}{user.last_name[0]}"
    elif user.username:
        initials = user.username[:2]

    # Couleur basée sur le hash du nom d'utilisateur
    colors = ['primary', 'secondary', 'success', 'danger', 'warning', 'info']
    color_index = hash(user.username) % len(colors)
    color = colors[color_index]

    html = f'''
    <div class="user-avatar bg-{color} text-white d-inline-flex align-items-center justify-content-center rounded-circle" 
         style="width: {size}px; height: {size}px; font-size: {size // 2.5}px; font-weight: bold;"
         title="{user.get_full_name() or user.username}">
        {initials.upper()}
    </div>
    '''
    return mark_safe(html)


@register.simple_tag
def field_value_display(field, value):
    """
    Affiche la valeur d'un champ selon son type
    Usage: {% field_value_display field annotation_value %}
    """
    if not value:
        return mark_safe('<em class="text-muted">Non renseigné</em>')

    if field.field_type == 'boolean':
        icon = 'fa-check text-success' if value else 'fa-times text-danger'
        text = 'Oui' if value else 'Non'
        return mark_safe(f'<i class="fas {icon} me-1"></i>{text}')

    elif field.field_type == 'multiple_choice':
        if isinstance(value, list):
            badges = ' '.join([f'<span class="badge bg-secondary me-1">{v}</span>' for v in value])
            return mark_safe(badges)
        return value

    elif field.field_type == 'date':
        return mark_safe(f'<i class="fas fa-calendar me-1"></i>{value}')

    elif field.field_type == 'number':
        return mark_safe(f'<i class="fas fa-hashtag me-1"></i>{value}')

    elif field.field_type in ['choice', 'entity', 'classification']:
        return mark_safe(f'<span class="badge bg-light text-dark">{value}</span>')

    else:  # text
        return smart_truncate(value, 100)


@register.inclusion_tag('documents/snippets/loading_spinner.html')
def loading_spinner(size="sm", text="Chargement..."):
    """
    Affiche un spinner de chargement
    Usage: {% loading_spinner "lg" "Traitement en cours..." %}
    """
    return {
        'size': size,
        'text': text
    }


@register.inclusion_tag('documents/snippets/tooltip.html')
def tooltip(content, text, placement="top"):
    """
    Génère un tooltip Bootstrap
    Usage: {% tooltip "Texte d'aide" "?" "bottom" %}
    """
    return {
        'content': content,
        'text': text,
        'placement': placement
    }


# Snippets templates pour les inclusion tags
@register.simple_tag
def create_loading_spinner_template():
    """Crée le template pour le spinner de chargement"""
    return '''
    <!-- documents/templates/documents/snippets/loading_spinner.html -->
    <div class="d-flex align-items-center">
        <div class="spinner-border spinner-border-{{ size }} me-2" role="status">
            <span class="visually-hidden">{{ text }}</span>
        </div>
        <span>{{ text }}</span>
    </div>
    '''


@register.simple_tag
def create_tooltip_template():
    """Crée le template pour les tooltips"""
    return '''
    <!-- documents/templates/documents/snippets/tooltip.html -->
    <span data-bs-toggle="tooltip" 
          data-bs-placement="{{ placement }}" 
          title="{{ content }}"
          style="cursor: help; text-decoration: underline dotted;">
        {{ text }}
    </span>
    '''