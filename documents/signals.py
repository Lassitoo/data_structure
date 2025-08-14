# documents/signals.py
"""
Signaux Django pour la synchronisation automatique en temps réel avec MongoDB
"""

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from documents.models import Document, AnnotationSchema, Annotation, AnnotationHistory
from documents.services.mongodb_service import get_mongodb_service
import logging

logger = logging.getLogger(__name__)


# ==================== SIGNAUX POUR DOCUMENT ====================

@receiver(post_save, sender=Document)
def sync_document_to_mongodb(sender, instance, created, **kwargs):
    """
    Synchronise automatiquement les documents avec MongoDB
    """
    try:
        mongodb_service = get_mongodb_service()
        
        if created:
            # Nouveau document créé
            logger.info(f"Nouveau document créé: {instance.title} (ID: {instance.id})")
            
            # Créer les métadonnées dans MongoDB
            mongodb_service.create_document_metadata(
                document_id=str(instance.id),
                title=instance.title,
                description=instance.description,
                file_type=instance.file_type,
                file_size=instance.file_size,
                status=instance.status,
                metadata=instance.metadata,
                uploaded_by=instance.uploaded_by.username,
                created_at=instance.created_at
            )
            logger.info(f"Document {instance.id} synchronisé avec MongoDB")
            
        else:
            # Document mis à jour
            logger.info(f"Document mis à jour: {instance.title} (ID: {instance.id})")
            
            # Mettre à jour dans MongoDB
            mongodb_service.update_document_metadata(
                document_id=str(instance.id),
                title=instance.title,
                description=instance.description,
                status=instance.status,
                metadata=instance.metadata,
                updated_at=instance.updated_at
            )
            logger.info(f"Document {instance.id} mis à jour dans MongoDB")
            
    except Exception as e:
        logger.error(f"Erreur synchronisation document {instance.id} avec MongoDB: {e}")


@receiver(post_delete, sender=Document)
def delete_document_from_mongodb(sender, instance, **kwargs):
    """
    Supprime automatiquement les documents de MongoDB
    """
    try:
        mongodb_service = get_mongodb_service()
        
        # Supprimer de MongoDB
        mongodb_service.delete_document_metadata(str(instance.id))
        logger.info(f"Document {instance.id} supprimé de MongoDB")
        
    except Exception as e:
        logger.error(f"Erreur suppression document {instance.id} de MongoDB: {e}")


# ==================== SIGNAUX POUR ANNOTATION SCHEMA ====================

@receiver(post_save, sender=AnnotationSchema)
def sync_annotation_schema_to_mongodb(sender, instance, created, **kwargs):
    """
    Synchronise automatiquement les schémas d'annotation avec MongoDB
    """
    try:
        mongodb_service = get_mongodb_service()
        
        # Préparer les données du schéma
        schema_data = {
            'name': instance.name,
            'description': instance.description,
            'ai_generated_schema': instance.ai_generated_schema,
            'final_schema': instance.final_schema,
            'is_validated': instance.is_validated,
            'fields': []
        }
        
        # Ajouter les champs
        for field in instance.fields.all():
            field_data = {
                'name': field.name,
                'label': field.label,
                'field_type': field.field_type,
                'description': field.description,
                'is_required': field.is_required,
                'is_multiple': field.is_multiple,
                'choices': field.choices,
                'order': field.order
            }
            schema_data['fields'].append(field_data)
        
        if created:
            # Nouveau schéma créé
            logger.info(f"Nouveau schéma créé: {instance.name} (ID: {instance.id})")
            
            mongodb_service.create_annotation_schema(
                document=instance.document,
                schema_data=schema_data,
                user=instance.created_by
            )
            logger.info(f"Schéma {instance.id} synchronisé avec MongoDB")
            
        else:
            # Schéma mis à jour
            logger.info(f"Schéma mis à jour: {instance.name} (ID: {instance.id})")
            
            mongodb_service.update_annotation_schema(
                document_id=str(instance.document.id),
                schema_data=schema_data
            )
            logger.info(f"Schéma {instance.id} mis à jour dans MongoDB")
            
    except Exception as e:
        logger.error(f"Erreur synchronisation schéma {instance.id} avec MongoDB: {e}")


@receiver(post_delete, sender=AnnotationSchema)
def delete_annotation_schema_from_mongodb(sender, instance, **kwargs):
    """
    Supprime automatiquement les schémas d'annotation de MongoDB
    """
    try:
        mongodb_service = get_mongodb_service()
        
        mongodb_service.delete_annotation_schema(str(instance.document.id))
        logger.info(f"Schéma {instance.id} supprimé de MongoDB")
        
    except Exception as e:
        logger.error(f"Erreur suppression schéma {instance.id} de MongoDB: {e}")


# ==================== SIGNAUX POUR ANNOTATION ====================

@receiver(post_save, sender=Annotation)
def sync_annotation_to_mongodb(sender, instance, created, **kwargs):
    """
    Synchronise automatiquement les annotations avec MongoDB
    """
    try:
        mongodb_service = get_mongodb_service()
        
        if created:
            # Nouvelle annotation créée
            logger.info(f"Nouvelle annotation créée pour document {instance.document.id}")
            
            mongodb_service.create_annotation(
                document=instance.document,
                schema_id=str(instance.schema.id),
                user=instance.annotated_by,
                ai_pre_annotations=instance.ai_pre_annotations
            )
            logger.info(f"Annotation {instance.id} synchronisée avec MongoDB")
            
        else:
            # Annotation mise à jour
            logger.info(f"Annotation mise à jour pour document {instance.document.id}")
            
            # Mettre à jour dans MongoDB
            mongodb_service.update_annotation(
                document_id=str(instance.document.id),
                annotations=instance.final_annotations,
                user=instance.annotated_by
            )
            
            # Mettre à jour le statut de validation si nécessaire
            if instance.is_validated and instance.validated_by:
                mongodb_service.validate_annotation(
                    document_id=str(instance.document.id),
                    user=instance.validated_by,
                    validation_notes=instance.validation_notes
                )
            
            logger.info(f"Annotation {instance.id} mise à jour dans MongoDB")
            
    except Exception as e:
        logger.error(f"Erreur synchronisation annotation {instance.id} avec MongoDB: {e}")


@receiver(post_delete, sender=Annotation)
def delete_annotation_from_mongodb(sender, instance, **kwargs):
    """
    Supprime automatiquement les annotations de MongoDB
    """
    try:
        mongodb_service = get_mongodb_service()
        
        mongodb_service.delete_annotation(str(instance.document.id))
        logger.info(f"Annotation {instance.id} supprimée de MongoDB")
        
    except Exception as e:
        logger.error(f"Erreur suppression annotation {instance.id} de MongoDB: {e}")


# ==================== SIGNAUX POUR ANNOTATION HISTORY ====================

@receiver(post_save, sender=AnnotationHistory)
def sync_annotation_history_to_mongodb(sender, instance, created, **kwargs):
    """
    Synchronise automatiquement l'historique des annotations avec MongoDB
    """
    if not created:
        return  # On ne synchronise que les nouvelles entrées d'historique
    
    try:
        mongodb_service = get_mongodb_service()
        
        logger.info(f"Nouvelle entrée d'historique créée pour annotation {instance.annotation.id}")
        
        # Créer l'entrée d'historique dans MongoDB
        mongodb_service.create_annotation_history(
            document_id=str(instance.annotation.document.id),
            action_type=instance.action_type,
            field_name=instance.field_name,
            old_value=instance.old_value,
            new_value=instance.new_value,
            comment=instance.comment,
            user=instance.performed_by
        )
        
        logger.info(f"Historique {instance.id} synchronisé avec MongoDB")
        
    except Exception as e:
        logger.error(f"Erreur synchronisation historique {instance.id} avec MongoDB: {e}")


# ==================== SIGNAUX POUR GESTION DES ERREURS ====================

@receiver(post_save, sender=Document)
def update_document_status_on_error(sender, instance, created, **kwargs):
    """
    Met à jour le statut du document en cas d'erreur de synchronisation
    """
    if created:
        return
    
    try:
        # Vérifier si MongoDB est disponible
        mongodb_service = get_mongodb_service()
        if not mongodb_service.is_connected():
            logger.warning(f"MongoDB indisponible - document {instance.id} en mode dégradé")
            
            # Optionnel: marquer le document comme nécessitant une synchronisation
            if not hasattr(instance, '_sync_pending'):
                instance._sync_pending = True
                
    except Exception as e:
        logger.error(f"Erreur vérification statut MongoDB pour document {instance.id}: {e}")


# ==================== UTILITAIRES ====================

def force_sync_document_to_mongodb(document_id):
    """
    Force la synchronisation d'un document spécifique avec MongoDB
    Utile pour la récupération après une panne
    """
    try:
        from documents.models import Document
        document = Document.objects.get(id=document_id)
        
        # Déclencher manuellement la synchronisation
        sync_document_to_mongodb(Document, document, created=False)
        
        # Synchroniser le schéma si il existe
        if hasattr(document, 'annotation_schema'):
            sync_annotation_schema_to_mongodb(
                AnnotationSchema, 
                document.annotation_schema, 
                created=False
            )
        
        # Synchroniser l'annotation si elle existe
        if hasattr(document, 'annotation'):
            sync_annotation_to_mongodb(
                Annotation, 
                document.annotation, 
                created=False
            )
        
        logger.info(f"Synchronisation forcée terminée pour document {document_id}")
        return True
        
    except Exception as e:
        logger.error(f"Erreur synchronisation forcée pour document {document_id}: {e}")
        return False


def sync_all_pending_documents():
    """
    Synchronise tous les documents en attente avec MongoDB
    Utile après une reconnexion MongoDB
    """
    try:
        from documents.models import Document
        
        # Récupérer tous les documents
        documents = Document.objects.all()
        synced_count = 0
        error_count = 0
        
        for document in documents:
            try:
                force_sync_document_to_mongodb(document.id)
                synced_count += 1
            except Exception as e:
                logger.error(f"Erreur sync document {document.id}: {e}")
                error_count += 1
        
        logger.info(f"Synchronisation globale terminée: {synced_count} réussies, {error_count} erreurs")
        return {'synced': synced_count, 'errors': error_count}
        
    except Exception as e:
        logger.error(f"Erreur synchronisation globale: {e}")
        return {'synced': 0, 'errors': -1}