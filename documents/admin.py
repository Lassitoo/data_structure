from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
import json

from .models import (
    Document, AnnotationSchema, AnnotationField,
    Annotation, AnnotationHistory
)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    """Administration des documents"""

    list_display = [
        'title', 'filename_display', 'file_type', 'status_display',
        'uploaded_by', 'file_size_display', 'created_at'
    ]
    list_filter = [
        'status', 'file_type', 'created_at', 'uploaded_by'
    ]
    search_fields = [
        'title', 'description', 'file__name'
    ]
    readonly_fields = [
        'id', 'filename', 'file_size', 'created_at', 'updated_at',
        'annotated_at', 'validated_at', 'metadata_display'
    ]
    ordering = ['-created_at']

    fieldsets = (
        ('Informations générales', {
            'fields': ('id', 'title', 'description', 'file')
        }),
        ('Détails du fichier', {
            'fields': ('filename', 'file_type', 'file_size', 'status')
        }),
        ('Utilisateurs', {
            'fields': ('uploaded_by', 'annotated_by', 'validated_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'annotated_at', 'validated_at')
        }),
        ('Métadonnées', {
            'fields': ('metadata_display',),
            'classes': ('collapse',)
        })
    )

    class Media:
        css = {
            'all': ('admin/css/custom_admin.css',)
        }

    def filename_display(self, obj):
        return obj.filename

    filename_display.short_description = 'Nom de fichier'

    def status_display(self, obj):
        colors = {
            'uploaded': '#17a2b8',
            'metadata_extracted': '#007bff',
            'schema_proposed': '#ffc107',
            'schema_validated': '#28a745',
            'pre_annotated': '#fd7e14',
            'annotated': '#6f42c1',
            'validated': '#28a745'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )

    status_display.short_description = 'Statut'

    def file_size_display(self, obj):
        if obj.file_size:
            if obj.file_size < 1024:
                return f"{obj.file_size} B"
            elif obj.file_size < 1024 * 1024:
                return f"{obj.file_size / 1024:.1f} KB"
            else:
                return f"{obj.file_size / (1024 * 1024):.1f} MB"
        return "N/A"

    file_size_display.short_description = 'Taille'

    def metadata_display(self, obj):
        if obj.metadata:
            formatted_json = json.dumps(obj.metadata, indent=2, ensure_ascii=False)
            return format_html('<pre class="json-display">{}</pre>', formatted_json)
        return "Aucune métadonnée"

    metadata_display.short_description = 'Métadonnées (JSON)'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'uploaded_by', 'annotated_by', 'validated_by'
        )


class AnnotationFieldInline(admin.TabularInline):
    """Inline pour les champs d'annotation"""
    model = AnnotationField
    extra = 0
    fields = ['name', 'label', 'field_type', 'is_required', 'order']
    ordering = ['order']


@admin.register(AnnotationSchema)
class AnnotationSchemaAdmin(admin.ModelAdmin):
    """Administration des schémas d'annotation"""

    list_display = [
        'name', 'document_link', 'is_validated', 'created_by',
        'fields_count', 'created_at'
    ]
    list_filter = [
        'is_validated', 'created_at', 'created_by'
    ]
    search_fields = [
        'name', 'description', 'document__title'
    ]
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'validated_at',
        'ai_generated_schema_display', 'final_schema_display'
    ]

    fieldsets = (
        ('Informations générales', {
            'fields': ('id', 'name', 'description', 'document', 'created_by')
        }),
        ('Validation', {
            'fields': ('is_validated', 'validated_at')
        }),
        ('Schémas', {
            'fields': ('ai_generated_schema_display', 'final_schema_display'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        })
    )

    inlines = [AnnotationFieldInline]

    class Media:
        css = {
            'all': ('admin/css/custom_admin.css',)
        }

    def document_link(self, obj):
        url = reverse('admin:documents_document_change', args=[obj.document.pk])
        return format_html('<a href="{}">{}</a>', url, obj.document.title)

    document_link.short_description = 'Document'

    def fields_count(self, obj):
        return obj.fields.count()

    fields_count.short_description = 'Nb champs'

    def ai_generated_schema_display(self, obj):
        if obj.ai_generated_schema:
            formatted_json = json.dumps(obj.ai_generated_schema, indent=2, ensure_ascii=False)
            return format_html('<pre class="json-display">{}</pre>', formatted_json)
        return "Aucun schéma IA"

    ai_generated_schema_display.short_description = 'Schéma généré par IA'

    def final_schema_display(self, obj):
        if obj.final_schema:
            formatted_json = json.dumps(obj.final_schema, indent=2, ensure_ascii=False)
            return format_html('<pre class="json-display">{}</pre>', formatted_json)
        return "Aucun schéma final"

    final_schema_display.short_description = 'Schéma final'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'document', 'created_by'
        ).prefetch_related('fields')


@admin.register(AnnotationField)
class AnnotationFieldAdmin(admin.ModelAdmin):
    """Administration des champs d'annotation"""

    list_display = [
        'label', 'name', 'field_type', 'schema_link',
        'is_required', 'order', 'created_at'
    ]
    list_filter = [
        'field_type', 'is_required', 'created_at'
    ]
    search_fields = [
        'name', 'label', 'description', 'schema__name'
    ]
    ordering = ['schema', 'order', 'name']

    def schema_link(self, obj):
        url = reverse('admin:documents_annotationschema_change', args=[obj.schema.pk])
        return format_html('<a href="{}">{}</a>', url, obj.schema.name)

    schema_link.short_description = 'Schéma'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('schema')


class AnnotationHistoryInline(admin.TabularInline):
    """Inline pour l'historique des annotations"""
    model = AnnotationHistory
    extra = 0
    fields = ['action_type', 'field_name', 'performed_by', 'created_at']
    readonly_fields = ['created_at']
    ordering = ['-created_at']


@admin.register(Annotation)
class AnnotationAdmin(admin.ModelAdmin):
    """Administration des annotations"""

    list_display = [
        'document_link', 'schema_link', 'annotated_by',
        'completion_percentage_display', 'is_complete', 'is_validated',
        'confidence_score', 'created_at'
    ]
    list_filter = [
        'is_complete', 'is_validated', 'created_at',
        'annotated_by', 'validated_by'
    ]
    search_fields = [
        'document__title', 'schema__name', 'validation_notes'
    ]
    readonly_fields = [
        'id', 'completion_percentage', 'created_at', 'updated_at',
        'completed_at', 'validated_at', 'ai_pre_annotations_display',
        'final_annotations_display'
    ]

    fieldsets = (
        ('Informations générales', {
            'fields': ('id', 'document', 'schema')
        }),
        ('Statut', {
            'fields': ('is_complete', 'is_validated', 'completion_percentage')
        }),
        ('Utilisateurs', {
            'fields': ('annotated_by', 'validated_by')
        }),
        ('Qualité', {
            'fields': ('confidence_score', 'validation_notes')
        }),
        ('Annotations', {
            'fields': ('ai_pre_annotations_display', 'final_annotations_display'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'completed_at', 'validated_at')
        })
    )

    inlines = [AnnotationHistoryInline]

    class Media:
        css = {
            'all': ('admin/css/custom_admin.css',)
        }

    def document_link(self, obj):
        url = reverse('admin:documents_document_change', args=[obj.document.pk])
        return format_html('<a href="{}">{}</a>', url, obj.document.title)

    document_link.short_description = 'Document'

    def schema_link(self, obj):
        url = reverse('admin:documents_annotationschema_change', args=[obj.schema.pk])
        return format_html('<a href="{}">{}</a>', url, obj.schema.name)

    schema_link.short_description = 'Schéma'

    def completion_percentage_display(self, obj):
        percentage = obj.completion_percentage
        if percentage >= 80:
            color = '#28a745'  # Vert
        elif percentage >= 50:
            color = '#ffc107'  # Jaune
        else:
            color = '#dc3545'  # Rouge

        return format_html(
            '<div class="completion-bar">'
            '<div class="completion-fill" style="width: {}%; background-color: {};">'
            '{}%</div></div>',
            percentage, color, int(percentage)
        )

    completion_percentage_display.short_description = 'Completion'

    def ai_pre_annotations_display(self, obj):
        if obj.ai_pre_annotations:
            formatted_json = json.dumps(obj.ai_pre_annotations, indent=2, ensure_ascii=False)
            return format_html('<pre class="json-display">{}</pre>', formatted_json)
        return "Aucune pré-annotation"

    ai_pre_annotations_display.short_description = 'Pré-annotations IA'

    def final_annotations_display(self, obj):
        if obj.final_annotations:
            formatted_json = json.dumps(obj.final_annotations, indent=2, ensure_ascii=False)
            return format_html('<pre class="json-display">{}</pre>', formatted_json)
        return "Aucune annotation finale"

    final_annotations_display.short_description = 'Annotations finales'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'document', 'schema', 'annotated_by', 'validated_by'
        )


@admin.register(AnnotationHistory)
class AnnotationHistoryAdmin(admin.ModelAdmin):
    """Administration de l'historique des annotations"""

    list_display = [
        'annotation_link', 'action_type', 'field_name',
        'performed_by', 'created_at'
    ]
    list_filter = [
        'action_type', 'created_at', 'performed_by'
    ]
    search_fields = [
        'annotation__document__title', 'field_name', 'comment'
    ]
    readonly_fields = [
        'id', 'created_at', 'old_value_display', 'new_value_display'
    ]
    ordering = ['-created_at']

    fieldsets = (
        ('Informations générales', {
            'fields': ('id', 'annotation', 'action_type', 'field_name', 'performed_by')
        }),
        ('Modifications', {
            'fields': ('old_value_display', 'new_value_display', 'comment')
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        })
    )

    class Media:
        css = {
            'all': ('admin/css/custom_admin.css',)
        }

    def annotation_link(self, obj):
        url = reverse('admin:documents_annotation_change', args=[obj.annotation.pk])
        return format_html('<a href="{}">{}</a>', url, str(obj.annotation))

    annotation_link.short_description = 'Annotation'

    def old_value_display(self, obj):
        if obj.old_value:
            formatted_json = json.dumps(obj.old_value, indent=2, ensure_ascii=False)
            return format_html('<pre class="json-display">{}</pre>', formatted_json)
        return "Aucune valeur"

    old_value_display.short_description = 'Ancienne valeur'

    def new_value_display(self, obj):
        if obj.new_value:
            formatted_json = json.dumps(obj.new_value, indent=2, ensure_ascii=False)
            return format_html('<pre class="json-display">{}</pre>', formatted_json)
        return "Aucune valeur"

    new_value_display.short_description = 'Nouvelle valeur'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'annotation', 'annotation__document', 'performed_by'
        )


# Configuration de l'admin
admin.site.site_header = "Data Structure - Administration"
admin.site.site_title = "Data Structure Admin"
admin.site.index_title = "Gestion du système d'annotation"