# documents/services/mongodb_service.py
"""
Service pour gérer l'intégration entre Django et MongoDB
Fournit une interface unifiée pour les opérations sur les annotations JSON
"""

from typing import Dict, List, Optional, Any
from django.contrib.auth.models import User
from documents.models import Document
from documents.mongo_models import (
    AnnotationSchemaMongo, AnnotationMongo, AnnotationHistoryMongo,
    DocumentMetadataMongo, connect_mongodb
)
import uuid
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MongoDBService:
    """Service principal pour les opérations MongoDB"""
    
    def __init__(self):
        self._connection_tested = False
    
    def ensure_connection(self):
        """S'assure que la connexion MongoDB est établie"""
        if not self._connection_tested:
            try:
                if not connect_mongodb():
                    logger.warning("Impossible de se connecter à MongoDB - mode dégradé")
                    return False
                self._connection_tested = True
                return True
            except Exception as e:
                logger.warning(f"Erreur connexion MongoDB: {e} - mode dégradé")
                return False
        return True
    
    # ==================== SCHÉMAS D'ANNOTATION ====================
    
    def create_annotation_schema(self, document: Document, schema_data: Dict, user: User) -> str:
        """
        Crée un nouveau schéma d'annotation dans MongoDB
        
        Args:
            document: Instance Django du document
            schema_data: Données du schéma (ai_generated_schema, final_schema, fields)
            user: Utilisateur créateur
            
        Returns:
            str: ID du schéma créé
        """
        try:
            schema = AnnotationSchemaMongo(
                document_id=document.id,
                name=schema_data.get('name', f'Schéma pour {document.title}'),
                description=schema_data.get('description', ''),
                ai_generated_schema=schema_data.get('ai_generated_schema', {}),
                final_schema=schema_data.get('final_schema', {}),
                fields=schema_data.get('fields', []),
                created_by_id=user.id
            )
            schema.save()
            
            logger.info(f"Schéma d'annotation créé: {schema.id} pour document {document.id}")
            return str(schema.id)
            
        except Exception as e:
            logger.error(f"Erreur lors de la création du schéma: {e}")
            raise
    
    def get_annotation_schema(self, document_id: uuid.UUID) -> Optional[AnnotationSchemaMongo]:
        """Récupère le schéma d'annotation pour un document"""
        try:
            return AnnotationSchemaMongo.objects(document_id=document_id).first()
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du schéma: {e}")
            return None
    
    def update_annotation_schema(self, document_id: uuid.UUID, updates: Dict) -> bool:
        """Met à jour un schéma d'annotation"""
        try:
            schema = AnnotationSchemaMongo.objects(document_id=document_id).first()
            if not schema:
                return False
            
            for key, value in updates.items():
                if hasattr(schema, key):
                    setattr(schema, key, value)
            
            schema.save()
            logger.info(f"Schéma mis à jour pour document {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du schéma: {e}")
            return False
    
    def validate_annotation_schema(self, document_id: uuid.UUID, user: User) -> bool:
        """Valide un schéma d'annotation"""
        try:
            schema = AnnotationSchemaMongo.objects(document_id=document_id).first()
            if not schema:
                return False
            
            schema.is_validated = True
            schema.validated_at = datetime.utcnow()
            schema.save()
            
            logger.info(f"Schéma validé pour document {document_id} par {user.username}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la validation du schéma: {e}")
            return False
    
    # ==================== ANNOTATIONS ====================
    
    def create_annotation(self, document: Document, schema_id: str, user: User, 
                         ai_pre_annotations: Dict = None) -> str:
        """
        Crée une nouvelle annotation dans MongoDB
        
        Args:
            document: Instance Django du document
            schema_id: ID du schéma d'annotation
            user: Utilisateur annotateur
            ai_pre_annotations: Pré-annotations générées par l'IA
            
        Returns:
            str: ID de l'annotation créée
        """
        try:
            annotation = AnnotationMongo(
                document_id=document.id,
                schema_id=uuid.UUID(schema_id),
                ai_pre_annotations=ai_pre_annotations or {},
                final_annotations={},
                annotated_by_id=user.id
            )
            annotation.save()
            
            # Enregistrer dans l'historique
            self._add_annotation_history(
                annotation_id=annotation.id,
                document_id=document.id,
                action_type='created',
                user=user,
                comment='Annotation créée'
            )
            
            logger.info(f"Annotation créée: {annotation.id} pour document {document.id}")
            return str(annotation.id)
            
        except Exception as e:
            logger.error(f"Erreur lors de la création de l'annotation: {e}")
            raise
    
    def get_annotation(self, document_id: uuid.UUID) -> Optional[AnnotationMongo]:
        """Récupère l'annotation pour un document"""
        try:
            return AnnotationMongo.objects(document_id=document_id).first()
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de l'annotation: {e}")
            return None
    
    def update_annotation_field(self, document_id: uuid.UUID, field_name: str, 
                               new_value: Any, user: User) -> bool:
        """Met à jour un champ spécifique de l'annotation"""
        try:
            annotation = AnnotationMongo.objects(document_id=document_id).first()
            if not annotation:
                return False
            
            # Sauvegarder l'ancienne valeur pour l'historique
            old_value = annotation.final_annotations.get(field_name)
            
            # Mettre à jour la valeur
            annotation.final_annotations[field_name] = new_value
            annotation.save()
            
            # Enregistrer dans l'historique
            self._add_annotation_history(
                annotation_id=annotation.id,
                document_id=document_id,
                action_type='field_updated',
                user=user,
                field_name=field_name,
                old_value=old_value,
                new_value=new_value
            )
            
            logger.info(f"Champ {field_name} mis à jour pour document {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du champ: {e}")
            return False
    
    def update_annotation(self, document_id: uuid.UUID, annotations: Dict, user: User) -> bool:
        """Met à jour l'annotation complète"""
        try:
            annotation = AnnotationMongo.objects(document_id=document_id).first()
            if not annotation:
                return False
            
            # Sauvegarder l'ancienne version pour l'historique
            old_annotations = annotation.final_annotations.copy()
            
            # Mettre à jour les annotations
            annotation.final_annotations.update(annotations)
            annotation.save()
            
            # Enregistrer dans l'historique
            self._add_annotation_history(
                annotation_id=annotation.id,
                document_id=document_id,
                action_type='updated',
                user=user,
                old_value=old_annotations,
                new_value=annotation.final_annotations,
                comment='Annotation mise à jour'
            )
            
            logger.info(f"Annotation mise à jour pour document {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour de l'annotation: {e}")
            return False
    
    def complete_annotation(self, document_id: uuid.UUID, user: User) -> bool:
        """Marque une annotation comme complète"""
        try:
            annotation = AnnotationMongo.objects(document_id=document_id).first()
            if not annotation:
                return False
            
            annotation.is_complete = True
            annotation.completed_at = datetime.utcnow()
            annotation.save()
            
            # Enregistrer dans l'historique
            self._add_annotation_history(
                annotation_id=annotation.id,
                document_id=document_id,
                action_type='updated',
                user=user,
                comment='Annotation marquée comme complète'
            )
            
            logger.info(f"Annotation complétée pour document {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la completion de l'annotation: {e}")
            return False
    
    def validate_annotation(self, document_id: uuid.UUID, user: User, 
                           validation_notes: str = '') -> bool:
        """Valide une annotation"""
        try:
            annotation = AnnotationMongo.objects(document_id=document_id).first()
            if not annotation:
                return False
            
            annotation.is_validated = True
            annotation.validated_by_id = user.id
            annotation.validated_at = datetime.utcnow()
            annotation.validation_notes = validation_notes
            annotation.save()
            
            # Enregistrer dans l'historique
            self._add_annotation_history(
                annotation_id=annotation.id,
                document_id=document_id,
                action_type='validated',
                user=user,
                comment=f'Annotation validée: {validation_notes}'
            )
            
            logger.info(f"Annotation validée pour document {document_id} par {user.username}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la validation de l'annotation: {e}")
            return False
    
    # ==================== HISTORIQUE ====================
    
    def _add_annotation_history(self, annotation_id: uuid.UUID, document_id: uuid.UUID,
                               action_type: str, user: User, field_name: str = None,
                               old_value: Any = None, new_value: Any = None,
                               comment: str = '') -> bool:
        """Ajoute une entrée dans l'historique des annotations"""
        try:
            history = AnnotationHistoryMongo(
                annotation_id=annotation_id,
                document_id=document_id,
                action_type=action_type,
                field_name=field_name,
                old_value=old_value,
                new_value=new_value,
                comment=comment,
                performed_by_id=user.id
            )
            history.save()
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout à l'historique: {e}")
            return False
    
    def get_annotation_history(self, document_id: uuid.UUID) -> List[AnnotationHistoryMongo]:
        """Récupère l'historique des annotations pour un document"""
        try:
            return list(AnnotationHistoryMongo.objects(document_id=document_id).order_by('-created_at'))
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de l'historique: {e}")
            return []
    
    # ==================== MÉTADONNÉES ÉTENDUES ====================
    
    def save_document_metadata(self, document: Document, metadata: Dict) -> bool:
        """Sauvegarde les métadonnées étendues d'un document"""
        try:
            doc_meta = DocumentMetadataMongo.objects(document_id=document.id).first()
            if not doc_meta:
                doc_meta = DocumentMetadataMongo(document_id=document.id)
            
            # Mettre à jour les métadonnées
            for key, value in metadata.items():
                if hasattr(doc_meta, key):
                    setattr(doc_meta, key, value)
            
            doc_meta.save()
            logger.info(f"Métadonnées sauvegardées pour document {document.id}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des métadonnées: {e}")
            return False
    
    def get_document_metadata(self, document_id: uuid.UUID) -> Optional[DocumentMetadataMongo]:
        """Récupère les métadonnées étendues d'un document"""
        try:
            return DocumentMetadataMongo.objects(document_id=document_id).first()
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des métadonnées: {e}")
            return None
    
    # ==================== STATISTIQUES ====================
    
    def get_annotation_statistics(self) -> Dict:
        """Récupère les statistiques des annotations"""
        if not self.ensure_connection():
            return {
                'total_annotations': 0,
                'completed_annotations': 0,
                'validated_annotations': 0,
                'pending_annotations': 0,
                'average_completion': 0,
                'status': 'mongodb_unavailable'
            }
            
        try:
            stats = {
                'total_annotations': AnnotationMongo.objects.count(),
                'completed_annotations': AnnotationMongo.objects(is_complete=True).count(),
                'validated_annotations': AnnotationMongo.objects(is_validated=True).count(),
                'pending_annotations': AnnotationMongo.objects(is_complete=False).count(),
                'average_completion': 0,
                'status': 'mongodb_active'
            }
            
            # Calculer le pourcentage moyen de completion
            annotations = AnnotationMongo.objects.only('completion_percentage')
            if annotations:
                total_completion = sum(ann.completion_percentage for ann in annotations)
                stats['average_completion'] = total_completion / len(annotations)
            
            return stats
            
        except Exception as e:
            logger.error(f"Erreur lors du calcul des statistiques: {e}")
            return {
                'total_annotations': 0,
                'completed_annotations': 0,
                'validated_annotations': 0,
                'pending_annotations': 0,
                'average_completion': 0,
                'status': 'mongodb_error',
                'error': str(e)
            }
    
    # ==================== GESTION DES DOCUMENTS ====================
    
    def create_document_metadata(self, document_id: str, title: str, description: str,
                                file_type: str, file_size: int, status: str,
                                metadata: Dict, uploaded_by: str, created_at: datetime) -> bool:
        """Crée les métadonnées d'un document dans MongoDB"""
        try:
            if not self.ensure_connection():
                return False
            
            doc_metadata = DocumentMetadataMongo(
                document_id=document_id,
                title=title,
                description=description,
                file_type=file_type,
                file_size=file_size,
                status=status,
                metadata=metadata,
                uploaded_by=uploaded_by,
                created_at=created_at
            )
            doc_metadata.save()
            
            logger.info(f"Métadonnées document {document_id} créées dans MongoDB")
            return True
            
        except Exception as e:
            logger.error(f"Erreur création métadonnées document: {e}")
            return False
    
    def update_document_metadata(self, document_id: str, title: str = None, 
                                description: str = None, status: str = None,
                                metadata: Dict = None, updated_at: datetime = None) -> bool:
        """Met à jour les métadonnées d'un document dans MongoDB"""
        try:
            if not self.ensure_connection():
                return False
            
            doc_metadata = DocumentMetadataMongo.objects(document_id=document_id).first()
            if not doc_metadata:
                return False
            
            if title is not None:
                doc_metadata.title = title
            if description is not None:
                doc_metadata.description = description
            if status is not None:
                doc_metadata.status = status
            if metadata is not None:
                doc_metadata.metadata = metadata
            if updated_at is not None:
                doc_metadata.updated_at = updated_at
            
            doc_metadata.save()
            
            logger.info(f"Métadonnées document {document_id} mises à jour dans MongoDB")
            return True
            
        except Exception as e:
            logger.error(f"Erreur mise à jour métadonnées document: {e}")
            return False
    
    def delete_document_metadata(self, document_id: str) -> bool:
        """Supprime les métadonnées d'un document de MongoDB"""
        try:
            if not self.ensure_connection():
                return False
            
            # Supprimer les métadonnées du document
            DocumentMetadataMongo.objects(document_id=document_id).delete()
            
            # Supprimer aussi les schémas et annotations associés
            AnnotationSchemaMongo.objects(document_id=document_id).delete()
            AnnotationMongo.objects(document_id=document_id).delete()
            AnnotationHistoryMongo.objects(document_id=document_id).delete()
            
            logger.info(f"Document {document_id} et données associées supprimés de MongoDB")
            return True
            
        except Exception as e:
            logger.error(f"Erreur suppression document: {e}")
            return False
    
    def update_annotation_schema(self, document_id: str, schema_data: Dict) -> bool:
        """Met à jour un schéma d'annotation dans MongoDB"""
        try:
            if not self.ensure_connection():
                return False
            
            schema = AnnotationSchemaMongo.objects(document_id=document_id).first()
            if not schema:
                return False
            
            schema.name = schema_data.get('name', schema.name)
            schema.description = schema_data.get('description', schema.description)
            schema.ai_generated_schema = schema_data.get('ai_generated_schema', schema.ai_generated_schema)
            schema.final_schema = schema_data.get('final_schema', schema.final_schema)
            schema.is_validated = schema_data.get('is_validated', schema.is_validated)
            schema.fields = schema_data.get('fields', schema.fields)
            schema.updated_at = datetime.utcnow()
            
            schema.save()
            
            logger.info(f"Schéma pour document {document_id} mis à jour dans MongoDB")
            return True
            
        except Exception as e:
            logger.error(f"Erreur mise à jour schéma: {e}")
            return False
    
    def delete_annotation_schema(self, document_id: str) -> bool:
        """Supprime un schéma d'annotation de MongoDB"""
        try:
            if not self.ensure_connection():
                return False
            
            AnnotationSchemaMongo.objects(document_id=document_id).delete()
            
            logger.info(f"Schéma pour document {document_id} supprimé de MongoDB")
            return True
            
        except Exception as e:
            logger.error(f"Erreur suppression schéma: {e}")
            return False
    
    def delete_annotation(self, document_id: str) -> bool:
        """Supprime une annotation de MongoDB"""
        try:
            if not self.ensure_connection():
                return False
            
            # Supprimer l'annotation et son historique
            AnnotationMongo.objects(document_id=document_id).delete()
            AnnotationHistoryMongo.objects(document_id=document_id).delete()
            
            logger.info(f"Annotation pour document {document_id} supprimée de MongoDB")
            return True
            
        except Exception as e:
            logger.error(f"Erreur suppression annotation: {e}")
            return False
    
    def create_annotation_history(self, document_id: str, action_type: str,
                                 field_name: str = None, old_value: Any = None,
                                 new_value: Any = None, comment: str = '',
                                 user: User = None) -> bool:
        """Crée une entrée d'historique pour une annotation"""
        try:
            if not self.ensure_connection():
                return False
            
            # Récupérer l'annotation pour obtenir son ID
            annotation = AnnotationMongo.objects(document_id=document_id).first()
            if not annotation:
                return False
            
            history = AnnotationHistoryMongo(
                annotation_id=annotation.id,
                document_id=document_id,
                action_type=action_type,
                field_name=field_name,
                old_value=old_value,
                new_value=new_value,
                comment=comment,
                performed_by_id=user.id if user else None,
                performed_by_username=user.username if user else 'system',
                created_at=datetime.utcnow()
            )
            history.save()
            
            logger.info(f"Historique créé pour document {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur création historique: {e}")
            return False
    
    def is_connected(self) -> bool:
        """Vérifie si MongoDB est connecté"""
        try:
            return self.ensure_connection()
        except Exception:
            return False


# Instance globale du service (créée à la demande)
_mongodb_service = None

def get_mongodb_service():
    """Retourne l'instance du service MongoDB (singleton)"""
    global _mongodb_service
    if _mongodb_service is None:
        _mongodb_service = MongoDBService()
    return _mongodb_service

# Alias pour compatibilité
mongodb_service = get_mongodb_service()