from django.urls import path
from . import views

app_name = 'documents'

urlpatterns = [
    # Dashboard et liste
    path('', views.dashboard, name='dashboard'),
    path('list/', views.document_list, name='document_list'),
    path('statistics/', views.statistics, name='statistics'),

    # Gestion des documents
    path('upload/', views.upload_document, name='upload_document'),
    path('document/<uuid:pk>/', views.document_detail, name='document_detail'),
    path('document/<uuid:document_pk>/export/', views.export_annotations, name='export_annotations'),

    # Schémas d'annotation
    path('document/<uuid:document_pk>/schema/edit/', views.edit_schema, name='edit_schema'),
    path('document/<uuid:document_pk>/schema/form-editor/', views.schema_form_editor, name='schema_form_editor'),
    path('document/<uuid:document_pk>/schema/regenerate/', views.regenerate_schema, name='regenerate_schema'),

    # Annotations
    path('document/<uuid:document_pk>/annotate/', views.annotate_document, name='annotate_document'),
    path('document/<uuid:document_pk>/validate/', views.validate_annotation, name='validate_annotation'),
    path('document/<uuid:document_pk>/annotations/regenerate/', views.regenerate_annotations,
         name='regenerate_annotations'),
    path('document/<uuid:document_pk>/annotations/history/', views.annotation_history, name='annotation_history'),
]