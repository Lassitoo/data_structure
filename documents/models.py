# documents/models.py
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator
import uuid
import os


class Document(models.Model):
    """Modèle pour les documents téléversés"""

    STATUS_CHOICES = [
        ('uploaded', 'Téléversé'),
        ('metadata_extracted', 'Métadonnées extraites'),
        ('schema_proposed', 'Schéma proposé'),
        ('schema_validated', 'Schéma validé'),
        ('pre_annotated', 'Pré-annoté'),
        ('annotated', 'Annoté'),
        ('validated', 'Validé'),
    ]

    DOCUMENT_TYPES = [
        ('pdf', 'PDF'),
        ('docx', 'Word Document'),
        ('doc', 'Word Document (ancien)'),
        ('txt', 'Texte'),
        ('xlsx', 'Excel'),
        ('xls', 'Excel (ancien)'),
        ('image', 'Image'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, verbose_name="Titre")
    description = models.TextField(blank=True, verbose_name="Description")
    file = models.FileField(
        upload_to='documents/%Y/%m/%d/',
        validators=[FileExtensionValidator(
            allowed_extensions=['pdf', 'docx', 'doc', 'txt', 'xlsx', 'xls', 'jpg', 'jpeg', 'png'])],
        verbose_name="Fichier"
    )
    file_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES, verbose_name="Type de fichier")
    file_size = models.BigIntegerField(verbose_name="Taille du fichier (bytes)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded', verbose_name="Statut")

    # Métadonnées extraites automatiquement
    metadata = models.JSONField(default=dict, blank=True, verbose_name="Métadonnées")

    # Utilisateurs
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_documents',
                                    verbose_name="Téléversé par")
    annotated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='annotated_documents', verbose_name="Annoté par")
    validated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='validated_documents', verbose_name="Validé par")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifié le")
    annotated_at = models.DateTimeField(null=True, blank=True, verbose_name="Annoté le")
    validated_at = models.DateTimeField(null=True, blank=True, verbose_name="Validé le")

    class Meta:
        verbose_name = "Document"
        verbose_name_plural = "Documents"
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def filename(self):
        return os.path.basename(self.file.name)

    @property
    def file_extension(self):
        return os.path.splitext(self.file.name)[1].lower()


class AnnotationSchema(models.Model):
    """Modèle pour les schémas d'annotation"""

    FIELD_TYPES = [
        ('text', 'Texte'),
        ('number', 'Nombre'),
        ('date', 'Date'),
        ('boolean', 'Booléen'),
        ('choice', 'Choix unique'),
        ('multiple_choice', 'Choix multiple'),
        ('entity', 'Entité nommée'),
        ('classification', 'Classification'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.OneToOneField(Document, on_delete=models.CASCADE, related_name='annotation_schema',
                                    verbose_name="Document")
    name = models.CharField(max_length=255, verbose_name="Nom du schéma")
    description = models.TextField(blank=True, verbose_name="Description")

    # Schéma généré par l'IA
    ai_generated_schema = models.JSONField(default=dict, blank=True, verbose_name="Schéma généré par l'IA")

    # Schéma final validé par l'annotateur
    final_schema = models.JSONField(default=dict, blank=True, verbose_name="Schéma final")

    is_validated = models.BooleanField(default=False, verbose_name="Schéma validé")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Créé par")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifié le")
    validated_at = models.DateTimeField(null=True, blank=True, verbose_name="Validé le")

    class Meta:
        verbose_name = "Schéma d'annotation"
        verbose_name_plural = "Schémas d'annotation"

    def __str__(self):
        return f"Schéma pour {self.document.title}"


class AnnotationField(models.Model):
    """Modèle pour les champs d'annotation individuels"""

    FIELD_TYPES = [
        ('text', 'Texte'),
        ('number', 'Nombre'),
        ('date', 'Date'),
        ('boolean', 'Booléen'),
        ('choice', 'Choix unique'),
        ('multiple_choice', 'Choix multiple'),
        ('entity', 'Entité nommée'),
        ('classification', 'Classification'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    schema = models.ForeignKey(AnnotationSchema, on_delete=models.CASCADE, related_name='fields', verbose_name="Schéma")

    name = models.CharField(max_length=255, verbose_name="Nom du champ")
    label = models.CharField(max_length=255, verbose_name="Label")
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES, verbose_name="Type de champ")
    description = models.TextField(blank=True, verbose_name="Description")

    # Configuration du champ
    is_required = models.BooleanField(default=False, verbose_name="Obligatoire")
    is_multiple = models.BooleanField(default=False, verbose_name="Valeurs multiples")

    # Pour les champs de type choix
    choices = models.JSONField(default=list, blank=True, verbose_name="Choix disponibles")

    # Configuration d'affichage
    order = models.PositiveIntegerField(default=0, verbose_name="Ordre d'affichage")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifié le")

    class Meta:
        verbose_name = "Champ d'annotation"
        verbose_name_plural = "Champs d'annotation"
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.label} ({self.field_type})"


class Annotation(models.Model):
    """Modèle pour les annotations finales"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.OneToOneField(Document, on_delete=models.CASCADE, related_name='annotation',
                                    verbose_name="Document")
    schema = models.ForeignKey(AnnotationSchema, on_delete=models.CASCADE, verbose_name="Schéma utilisé")

    # Pré-annotations générées par l'IA
    ai_pre_annotations = models.JSONField(default=dict, blank=True, verbose_name="Pré-annotations IA")

    # Annotations finales validées
    final_annotations = models.JSONField(default=dict, blank=True, verbose_name="Annotations finales")

    # Statut et validations
    is_complete = models.BooleanField(default=False, verbose_name="Annotation complète")
    is_validated = models.BooleanField(default=False, verbose_name="Annotation validée")

    # Métriques de qualité
    confidence_score = models.FloatField(null=True, blank=True, verbose_name="Score de confiance")
    validation_notes = models.TextField(blank=True, verbose_name="Notes de validation")

    # Utilisateurs
    annotated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='annotations',
                                     verbose_name="Annoté par")
    validated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='validated_annotations', verbose_name="Validé par")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifié le")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Complété le")
    validated_at = models.DateTimeField(null=True, blank=True, verbose_name="Validé le")

    class Meta:
        verbose_name = "Annotation"
        verbose_name_plural = "Annotations"

    def __str__(self):
        return f"Annotation de {self.document.title}"

    @property
    def completion_percentage(self):
        """Calcule le pourcentage de completion de l'annotation"""
        if not self.final_annotations:
            return 0

        total_fields = self.schema.fields.filter(is_required=True).count()
        if total_fields == 0:
            return 100

        completed_fields = sum(1 for field in self.schema.fields.filter(is_required=True)
                               if field.name in self.final_annotations and self.final_annotations[field.name])

        return (completed_fields / total_fields) * 100


class AnnotationHistory(models.Model):
    """Modèle pour l'historique des modifications d'annotations"""

    ACTION_TYPES = [
        ('created', 'Créé'),
        ('updated', 'Modifié'),
        ('validated', 'Validé'),
        ('rejected', 'Rejeté'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    annotation = models.ForeignKey(Annotation, on_delete=models.CASCADE, related_name='history',
                                   verbose_name="Annotation")

    action_type = models.CharField(max_length=20, choices=ACTION_TYPES, verbose_name="Type d'action")
    field_name = models.CharField(max_length=255, blank=True, verbose_name="Nom du champ modifié")
    old_value = models.JSONField(null=True, blank=True, verbose_name="Ancienne valeur")
    new_value = models.JSONField(null=True, blank=True, verbose_name="Nouvelle valeur")

    comment = models.TextField(blank=True, verbose_name="Commentaire")

    performed_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Effectué par")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")

    class Meta:
        verbose_name = "Historique d'annotation"
        verbose_name_plural = "Historiques d'annotation"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action_type} - {self.annotation.document.title} le {self.created_at}"