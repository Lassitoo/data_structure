from django import forms
from django.core.validators import FileExtensionValidator
from django.conf import settings
import json

from .models import Document, AnnotationSchema, Annotation


class DocumentUploadForm(forms.ModelForm):
    """Formulaire pour le téléversement de documents"""

    class Meta:
        model = Document
        fields = ['title', 'description', 'file']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Titre du document'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description du document (optionnel)'
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.docx,.doc,.txt,.xlsx,.xls,.jpg,.jpeg,.png'
            })
        }
        labels = {
            'title': 'Titre du document',
            'description': 'Description',
            'file': 'Fichier'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].required = True
        self.fields['description'].required = False

        # Configuration de la validation de fichier
        supported_extensions = [
            'pdf', 'docx', 'doc', 'txt', 'xlsx', 'xls',
            'jpg', 'jpeg', 'png'
        ]

        self.fields['file'].validators = [
            FileExtensionValidator(allowed_extensions=supported_extensions)
        ]

    def clean_file(self):
        file = self.cleaned_data.get('file')

        if file:
            # Vérification de la taille
            max_size = getattr(settings, 'MAX_FILE_SIZE', 10 * 1024 * 1024)  # 10MB par défaut
            if file.size > max_size:
                raise forms.ValidationError(
                    f'Le fichier est trop volumineux. Taille maximale: {max_size // (1024 * 1024)}MB'
                )

            # Détermination du type de fichier
            file_extension = file.name.lower().split('.')[-1]
            type_mapping = {
                'pdf': 'pdf',
                'docx': 'docx',
                'doc': 'doc',
                'txt': 'txt',
                'xlsx': 'xlsx',
                'xls': 'xls',
                'jpg': 'image',
                'jpeg': 'image',
                'png': 'image'
            }

            file_type = type_mapping.get(file_extension, 'unknown')
            if file_type == 'unknown':
                raise forms.ValidationError('Type de fichier non supporté')

        return file

    def save(self, commit=True):
        document = super().save(commit=False)

        if self.cleaned_data.get('file'):
            file = self.cleaned_data['file']

            # Détermination du type de fichier
            file_extension = file.name.lower().split('.')[-1]
            type_mapping = {
                'pdf': 'pdf',
                'docx': 'docx',
                'doc': 'doc',
                'txt': 'txt',
                'xlsx': 'xlsx',
                'xls': 'xls',
                'jpg': 'image',
                'jpeg': 'image',
                'png': 'image'
            }

            document.file_type = type_mapping.get(file_extension, 'unknown')
            document.file_size = file.size

        if commit:
            document.save()

        return document


class AnnotationSchemaForm(forms.ModelForm):
    """Formulaire pour l'édition des schémas d'annotation"""

    schema_json = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 20,
            'placeholder': 'Schéma JSON...'
        }),
        label='Schéma d\'annotation (JSON)'
    )

    class Meta:
        model = AnnotationSchema
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom du schéma'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description du schéma'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Pré-remplir le JSON si on édite un schéma existant
        if self.instance and self.instance.pk:
            self.fields['schema_json'].initial = json.dumps(
                self.instance.final_schema,
                indent=2,
                ensure_ascii=False
            )

    def clean_schema_json(self):
        schema_json = self.cleaned_data.get('schema_json')

        try:
            schema_data = json.loads(schema_json)
        except json.JSONDecodeError as e:
            raise forms.ValidationError(f'JSON invalide: {str(e)}')

        # Validation de la structure
        if not isinstance(schema_data, dict):
            raise forms.ValidationError('Le schéma doit être un objet JSON')

        if 'fields' not in schema_data:
            raise forms.ValidationError('Le schéma doit contenir une clé "fields"')

        if not isinstance(schema_data['fields'], list):
            raise forms.ValidationError('La clé "fields" doit être une liste')

        # Validation des champs
        valid_field_types = [
            'text', 'number', 'date', 'boolean',
            'choice', 'multiple_choice', 'entity', 'classification'
        ]

        for i, field in enumerate(schema_data['fields']):
            if not isinstance(field, dict):
                raise forms.ValidationError(f'Le champ {i + 1} doit être un objet')

            if 'name' not in field:
                raise forms.ValidationError(f'Le champ {i + 1} doit avoir un nom')

            if 'type' not in field:
                raise forms.ValidationError(f'Le champ {i + 1} doit avoir un type')

            if field['type'] not in valid_field_types:
                raise forms.ValidationError(
                    f'Type invalide pour le champ {i + 1}: {field["type"]}. '
                    f'Types valides: {", ".join(valid_field_types)}'
                )

            # Validation des choix pour les champs choice/multiple_choice
            if field['type'] in ['choice', 'multiple_choice']:
                if 'choices' not in field or not isinstance(field['choices'], list):
                    raise forms.ValidationError(
                        f'Le champ {i + 1} de type {field["type"]} doit avoir une liste de choix'
                    )

        return schema_data

    def save(self, commit=True):
        schema = super().save(commit=False)

        if 'schema_json' in self.cleaned_data:
            schema.final_schema = self.cleaned_data['schema_json']

        if commit:
            schema.save()

        return schema


class AnnotationForm(forms.Form):
    """Formulaire dynamique pour les annotations"""

    def __init__(self, annotation_schema, initial_data=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.annotation_schema = annotation_schema

        # Génération dynamique des champs
        for field_config in annotation_schema.fields.all().order_by('order'):
            field_name = field_config.name
            field_type = field_config.field_type
            field_label = field_config.label
            field_required = field_config.is_required
            field_description = field_config.description

            # Valeur initiale
            initial_value = None
            if initial_data and field_name in initial_data:
                initial_value = initial_data[field_name]

            # Création du champ selon le type
            field_kwargs = {
                'label': field_label,
                'required': field_required,
                'help_text': field_description,
                'initial': initial_value
            }

            if field_type == 'text':
                self.fields[field_name] = forms.CharField(
                    widget=forms.Textarea(attrs={
                        'class': 'form-control',
                        'rows': 3
                    }),
                    **field_kwargs
                )

            elif field_type == 'number':
                self.fields[field_name] = forms.FloatField(
                    widget=forms.NumberInput(attrs={'class': 'form-control'}),
                    **field_kwargs
                )

            elif field_type == 'date':
                self.fields[field_name] = forms.DateField(
                    widget=forms.DateInput(attrs={
                        'class': 'form-control',
                        'type': 'date'
                    }),
                    **field_kwargs
                )

            elif field_type == 'boolean':
                self.fields[field_name] = forms.BooleanField(
                    widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
                    **field_kwargs
                )

            elif field_type == 'choice':
                choices = [(choice, choice) for choice in field_config.choices]
                choices.insert(0, ('', '-- Sélectionner --'))

                self.fields[field_name] = forms.ChoiceField(
                    choices=choices,
                    widget=forms.Select(attrs={'class': 'form-control'}),
                    **field_kwargs
                )

            elif field_type == 'multiple_choice':
                choices = [(choice, choice) for choice in field_config.choices]

                self.fields[field_name] = forms.MultipleChoiceField(
                    choices=choices,
                    widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
                    **field_kwargs
                )

            elif field_type in ['entity', 'classification']:
                self.fields[field_name] = forms.CharField(
                    widget=forms.TextInput(attrs={
                        'class': 'form-control',
                        'placeholder': f'Entrez {field_label.lower()}'
                    }),
                    **field_kwargs
                )

            else:
                # Type par défaut: text
                self.fields[field_name] = forms.CharField(
                    widget=forms.TextInput(attrs={'class': 'form-control'}),
                    **field_kwargs
                )

    def get_annotation_data(self):
        """Retourne les données d'annotation nettoyées"""
        if not self.is_valid():
            return None

        annotation_data = {}

        for field_name, value in self.cleaned_data.items():
            # Traitement spécial pour les champs multiple_choice
            field_config = self.annotation_schema.fields.get(name=field_name)

            if field_config.field_type == 'multiple_choice' and isinstance(value, list):
                annotation_data[field_name] = value
            elif field_config.field_type == 'date' and value:
                annotation_data[field_name] = value.isoformat()
            else:
                annotation_data[field_name] = value

        return annotation_data

    # À ajouter dans votre classe AnnotationForm dans documents/forms.py

    def get_widget_type(self, field_name):
        """Retourne le type de widget pour un champ donné de manière sécurisée"""
        field = self.fields.get(field_name)
        if field and hasattr(field, 'widget'):
            widget_class = field.widget.__class__
            return widget_class.__name__
        return 'Inconnu'

    def get_widget_info(self, field_name):
        """Retourne des informations détaillées sur le widget"""
        field = self.fields.get(field_name)
        if field and hasattr(field, 'widget'):
            widget_class = field.widget.__class__
            widget_name = widget_class.__name__

            # Mapping des noms de widgets vers des noms plus lisibles
            widget_mapping = {
                'TextInput': 'Texte',
                'Textarea': 'Zone de texte',
                'Select': 'Liste déroulante',
                'SelectMultiple': 'Sélection multiple',
                'CheckboxInput': 'Case à cocher',
                'RadioSelect': 'Boutons radio',
                'DateInput': 'Date',
                'TimeInput': 'Heure',
                'DateTimeInput': 'Date et heure',
                'NumberInput': 'Nombre',
                'EmailInput': 'Email',
                'URLInput': 'URL',
                'FileInput': 'Fichier',
            }

            return widget_mapping.get(widget_name, widget_name)
        return 'Inconnu'


class ValidationForm(forms.Form):
    """Formulaire pour la validation des annotations"""

    STATUS_CHOICES = [
        ('approved', 'Approuvé'),
        ('rejected', 'Rejeté'),
        ('needs_revision', 'Nécessite des révisions')
    ]

    validation_status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        label='Statut de validation'
    )

    validation_notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Notes de validation, commentaires, suggestions...'
        }),
        label='Notes de validation',
        required=False
    )

    confidence_score = forms.FloatField(
        min_value=0.0,
        max_value=10.0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.1',
            'min': '0',
            'max': '10'
        }),
        label='Score de confiance (0-10)',
        required=False
    )


class SearchForm(forms.Form):
    """Formulaire de recherche de documents"""

    query = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Rechercher dans les documents...'
        }),
        label='Recherche',
        required=False
    )

    file_type = forms.ChoiceField(
        choices=[('', 'Tous les types')] + Document.DOCUMENT_TYPES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Type de fichier',
        required=False
    )

    status = forms.ChoiceField(
        choices=[('', 'Tous les statuts')] + Document.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Statut',
        required=False
    )

    date_from = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label='Date de début',
        required=False
    )

    date_to = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label='Date de fin',
        required=False
    )