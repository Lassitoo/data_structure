# documents/mongo_models.py
"""
Modèles MongoDB pour stocker les données JSON d'annotations
Utilise MongoEngine pour une meilleure intégration avec MongoDB
"""

from mongoengine import Document as MongoDocument, EmbeddedDocument
from mongoengine import StringField, DictField, ListField, DateTimeField, BooleanField
from mongoengine import FloatField, IntField, UUIDField, EmbeddedDocumentField
from datetime import datetime
import uuid


class AnnotationFieldMongo(EmbeddedDocument):
    """Champ d'annotation stocké dans MongoDB"""
    name = StringField(required=True)
    label = StringField(required=True)
    field_type = StringField(required=True, choices=[
        'text', 'number', 'date', 'boolean', 'choice', 
        'multiple_choice', 'entity', 'classification'
    ])
    description = StringField()
    is_required = BooleanField(default=False)
    is_multiple = BooleanField(default=False)
    choices = ListField(StringField())
    order = IntField(default=0)


class AnnotationSchemaMongo(MongoDocument):
    """Schéma d'annotation stocké dans MongoDB"""
    
    # Référence vers le document Django (UUID)
    document_id = UUIDField(required=True, unique=True)
    
    # Informations du schéma
    name = StringField(required=True, max_length=255)
    description = StringField()
    
    # Schémas JSON
    ai_generated_schema = DictField()
    final_schema = DictField()
    
    # Champs structurés
    fields = ListField(EmbeddedDocumentField(AnnotationFieldMongo))
    
    # Statut
    is_validated = BooleanField(default=False)
    
    # Métadonnées
    created_by_id = IntField(required=True)  # ID de l'utilisateur Django
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)
    validated_at = DateTimeField()
    
    meta = {
        'collection': 'annotation_schemas',
        'indexes': ['document_id', 'created_by_id', 'created_at']
    }
    
    def save(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)


class AnnotationMongo(MongoDocument):
    """Annotation complète stockée dans MongoDB"""
    
    # Référence vers le document Django (UUID)
    document_id = UUIDField(required=True, unique=True)
    schema_id = UUIDField(required=True)  # Référence vers AnnotationSchemaMongo
    
    # Données d'annotation
    ai_pre_annotations = DictField()
    final_annotations = DictField()
    
    # Métadonnées d'annotation
    confidence_scores = DictField()  # Score par champ
    validation_notes = StringField()
    
    # Statut
    is_complete = BooleanField(default=False)
    is_validated = BooleanField(default=False)
    
    # Métriques
    completion_percentage = FloatField(default=0.0)
    average_confidence = FloatField()
    
    # Utilisateurs (IDs Django)
    annotated_by_id = IntField(required=True)
    validated_by_id = IntField()
    
    # Timestamps
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)
    completed_at = DateTimeField()
    validated_at = DateTimeField()
    
    meta = {
        'collection': 'annotations',
        'indexes': [
            'document_id', 'schema_id', 'annotated_by_id', 
            'is_complete', 'is_validated', 'created_at'
        ]
    }
    
    def save(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        # Calculer le pourcentage de completion
        if self.final_annotations:
            total_fields = len(self.final_annotations)
            completed_fields = sum(1 for value in self.final_annotations.values() if value)
            self.completion_percentage = (completed_fields / total_fields * 100) if total_fields > 0 else 0
        
        return super().save(*args, **kwargs)


class AnnotationHistoryMongo(MongoDocument):
    """Historique des modifications d'annotations dans MongoDB"""
    
    # Référence vers l'annotation
    annotation_id = UUIDField(required=True)
    document_id = UUIDField(required=True)
    
    # Détails de l'action
    action_type = StringField(required=True, choices=[
        'created', 'updated', 'validated', 'rejected', 'field_updated'
    ])
    field_name = StringField()
    old_value = DictField()
    new_value = DictField()
    
    # Commentaires et notes
    comment = StringField()
    
    # Métadonnées
    performed_by_id = IntField(required=True)
    performed_by_username = StringField(required=True)
    created_at = DateTimeField(default=datetime.utcnow)
    
    # Informations contextuelles
    user_agent = StringField()
    ip_address = StringField()
    
    meta = {
        'collection': 'annotation_history',
        'indexes': [
            'annotation_id', 'document_id', 'performed_by_id', 
            'action_type', 'created_at'
        ]
    }


class DocumentMetadataMongo(MongoDocument):
    """Métadonnées étendues des documents dans MongoDB"""
    
    # Référence vers le document Django
    document_id = UUIDField(required=True, unique=True)
    
    # Informations de base du document (synchronisées depuis Django)
    title = StringField(required=True, max_length=255)
    description = StringField()
    file_type = StringField(required=True, max_length=20)
    file_size = IntField(required=True)
    status = StringField(required=True, max_length=20)
    metadata = DictField()  # Métadonnées JSON du document Django
    uploaded_by = StringField(required=True)  # Username de l'utilisateur
    
    # Métadonnées extraites (étendues)
    extracted_text = StringField()
    extracted_entities = ListField(DictField())
    extracted_keywords = ListField(StringField())
    
    # Analyse IA
    ai_analysis = DictField()
    language_detected = StringField()
    document_type_detected = StringField()
    
    # Statistiques
    word_count = IntField()
    page_count = IntField()
    character_count = IntField()
    
    # Timestamps
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)
    
    meta = {
        'collection': 'document_metadata',
        'indexes': [
            'document_id', 'title', 'status', 'file_type', 
            'uploaded_by', 'language_detected', 'document_type_detected',
            'created_at'
        ]
    }
    
    def save(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)


# Fonctions utilitaires pour la connexion MongoDB

def connect_mongodb():
    """Établit la connexion à MongoDB"""
    from mongoengine import connect, disconnect
    from django.conf import settings
    
    try:
        # Déconnecter les connexions existantes pour éviter les conflits
        try:
            disconnect()
        except:
            pass
        
        # Utiliser la configuration depuis Django settings
        mongodb_settings = getattr(settings, 'MONGODB_SETTINGS', {
            'db': 'data_structure_db',
            'host': 'mongodb://localhost:27017/data_structure_db',
            'connect': False
        })
        
        connect(**mongodb_settings)
        print("[OK] Connexion MongoDB etablie avec succes")
        return True
    except Exception as e:
        print(f"[ERROR] Erreur de connexion MongoDB: {e}")
        return False


def init_mongodb_indexes():
    """Initialise les index MongoDB pour optimiser les performances"""
    try:
        # Créer les index pour chaque collection
        AnnotationSchemaMongo.ensure_indexes()
        AnnotationMongo.ensure_indexes()
        AnnotationHistoryMongo.ensure_indexes()
        DocumentMetadataMongo.ensure_indexes()
        
        print("[OK] Index MongoDB crees avec succes")
        return True
    except Exception as e:
        print(f"[ERROR] Erreur lors de la creation des index: {e}")
        return False