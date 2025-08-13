# documents/services/hybrid_service.py
"""
Service hybride qui utilise Django ORM pour les métadonnées et MongoDB pour les données JSON
Fournit une interface transparente pour l'application
"""

from typing import Dict, List, Optional, Any, Union
from django.contrib.auth.models import User
from documents.models import Document, AnnotationSchema, Annotation, AnnotationHistory
from documents.services.mongodb_service import get_mongodb_service
from documents.mongo_models import AnnotationSchemaMongo, AnnotationMongo
import uuid
import logging

logger = logging.getLogger(__name__)


class HybridAnnotationService:
    """Service hybride pour gérer les annotations avec Django + MongoDB"""
    
    def __init__(self):
        self.mongodb_service = get_mongodb_service()
    
    # ==================== SCHÉMAS D'ANNOTATION ====================
    
    def create_annotation_schema(self, document: Document, schema_data: Dict, user: User) -> AnnotationSchema:
        """
        Crée un schéma d'annotation en utilisant Django ORM + MongoDB
        
        Args:
            document: Document Django
            schema_data: Données du schéma
            user: Utilisateur créateur
            
        Returns:
            AnnotationSchema: Instance Django du schéma créé
        """
        try:
            # Créer le schéma dans Django ORM
            django_schema = AnnotationSchema.objects.create(
                document=document,
                name=schema_data.get('name', f'Schéma pour {document.title}'),
                description=schema_data.get('description', ''),
                ai_generated_schema=schema_data.get('ai_generated_schema', {}),
                final_schema=schema_data.get('final_schema', {}),
                created_by=user
            )
            
            # Créer les champs dans Django ORM
            from documents.models import AnnotationField
            for field_data in schema_data.get('fields', []):
                AnnotationField.objects.create(
                    schema=django_schema,
                    name=field_data.get('name', ''),
                    label=field_data.get('label', ''),
                    field_type=field_data.get('field_type', 'text'),
                    description=field_data.get('description', ''),
                    is_required=field_data.get('is_required', False),
                    is_multiple=field_data.get('is_multiple', False),
                    choices=field_data.get('choices', []),
                    order=field_data.get('order', 0)
                )
            
            # Synchroniser avec MongoDB
            try:
                self.mongodb_service.create_annotation_schema(document, schema_data, user)
                logger.info(f"Schéma synchronisé avec MongoDB pour document {document.id}")
            except Exception as e:
                logger.warning(f"Erreur synchronisation MongoDB: {e}")
            
            return django_schema
            
        except Exception as e:
            logger.error(f"Erreur création schéma hybride: {e}")
            raise
    
    def get_annotation_schema(self, document: Document) -> Optional[AnnotationSchema]:
        """Récupère le schéma d'annotation pour un document"""
        try:
            return AnnotationSchema.objects.filter(document=document).first()
        except Exception as e:
            logger.error(f"Erreur récupération schéma: {e}")
            return None
    
    def get_schema_with_mongodb_data(self, document: Document) -> Dict:
        """Récupère le schéma avec les données MongoDB enrichies"""
        try:
            # Récupérer le schéma Django
            django_schema = self.get_annotation_schema(document)
            if not django_schema:
                return {}
            
            # Récupérer les données MongoDB
            mongo_schema = self.mongodb_service.get_annotation_schema(document.id)
            
            # Combiner les données
            schema_data = {
                'id': str(django_schema.id),
                'name': django_schema.name,
                'description': django_schema.description,
                'ai_generated_schema': django_schema.ai_generated_schema,
                'final_schema': django_schema.final_schema,
                'is_validated': django_schema.is_validated,
                'created_by': django_schema.created_by.username,
                'created_at': django_schema.created_at,
                'fields': []
            }
            
            # Ajouter les champs
            for field in django_schema.fields.all():
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
            
            # Enrichir avec les données MongoDB si disponibles
            if mongo_schema:
                schema_data['mongodb_data'] = {
                    'mongo_id': str(mongo_schema.id),
                    'additional_fields': mongo_schema.fields
                }
            
            return schema_data
            
        except Exception as e:
            logger.error(f"Erreur récupération schéma enrichi: {e}")
            return {}
    
    # ==================== ANNOTATIONS ====================
    
    def create_annotation(self, document: Document, user: User, 
                         ai_pre_annotations: Dict = None) -> Annotation:
        """
        Crée une annotation en utilisant Django ORM + MongoDB
        
        Args:
            document: Document Django
            user: Utilisateur annotateur
            ai_pre_annotations: Pré-annotations IA
            
        Returns:
            Annotation: Instance Django de l'annotation créée
        """
        try:
            # Récupérer le schéma
            schema = self.get_annotation_schema(document)
            if not schema:
                raise ValueError("Aucun schéma trouvé pour ce document")
            
            # Créer l'annotation dans Django ORM
            django_annotation = Annotation.objects.create(
                document=document,
                schema=schema,
                ai_pre_annotations=ai_pre_annotations or {},
                annotated_by=user
            )
            
            # Synchroniser avec MongoDB
            try:
                self.mongodb_service.create_annotation(
                    document, str(schema.id), user, ai_pre_annotations
                )
                logger.info(f"Annotation synchronisée avec MongoDB pour document {document.id}")
            except Exception as e:
                logger.warning(f"Erreur synchronisation MongoDB: {e}")
            
            return django_annotation
            
        except Exception as e:
            logger.error(f"Erreur création annotation hybride: {e}")
            raise
    
    def get_annotation(self, document: Document) -> Optional[Annotation]:
        """Récupère l'annotation pour un document"""
        try:
            return Annotation.objects.filter(document=document).first()
        except Exception as e:
            logger.error(f"Erreur récupération annotation: {e}")
            return None
    
    def get_annotation_with_mongodb_data(self, document: Document) -> Dict:
        """Récupère l'annotation avec les données MongoDB enrichies"""
        try:
            # Récupérer l'annotation Django
            django_annotation = self.get_annotation(document)
            if not django_annotation:
                return {}
            
            # Récupérer les données MongoDB
            mongo_annotation = self.mongodb_service.get_annotation(document.id)
            
            # Combiner les données
            annotation_data = {
                'id': str(django_annotation.id),
                'ai_pre_annotations': django_annotation.ai_pre_annotations,
                'final_annotations': django_annotation.final_annotations,
                'is_complete': django_annotation.is_complete,
                'is_validated': django_annotation.is_validated,
                'confidence_score': django_annotation.confidence_score,
                'validation_notes': django_annotation.validation_notes,
                'annotated_by': django_annotation.annotated_by.username,
                'created_at': django_annotation.created_at,
                'completion_percentage': django_annotation.completion_percentage
            }
            
            # Enrichir avec les données MongoDB si disponibles
            if mongo_annotation:
                annotation_data['mongodb_data'] = {
                    'mongo_id': str(mongo_annotation.id),
                    'confidence_scores': mongo_annotation.confidence_scores,
                    'average_confidence': mongo_annotation.average_confidence,
                    'completion_percentage_mongo': mongo_annotation.completion_percentage
                }
                
                # Utiliser les données MongoDB comme source principale pour les annotations
                annotation_data['final_annotations'] = mongo_annotation.final_annotations
                annotation_data['ai_pre_annotations'] = mongo_annotation.ai_pre_annotations
            
            return annotation_data
            
        except Exception as e:
            logger.error(f"Erreur récupération annotation enrichie: {e}")
            return {}
    
    def update_annotation_field(self, document: Document, field_name: str, 
                               new_value: Any, user: User) -> bool:
        """Met à jour un champ d'annotation dans Django et MongoDB"""
        try:
            # Mettre à jour dans Django
            django_annotation = self.get_annotation(document)
            if django_annotation:
                django_annotation.final_annotations[field_name] = new_value
                django_annotation.save()
            
            # Mettre à jour dans MongoDB
            success = self.mongodb_service.update_annotation_field(
                document.id, field_name, new_value, user
            )
            
            if success:
                logger.info(f"Champ {field_name} mis à jour pour document {document.id}")
                return True
            else:
                logger.warning(f"Échec mise à jour MongoDB pour champ {field_name}")
                return False
                
        except Exception as e:
            logger.error(f"Erreur mise à jour champ hybride: {e}")
            return False
    
    def update_annotation(self, document: Document, annotations: Dict, user: User) -> bool:
        """Met à jour l'annotation complète dans Django et MongoDB"""
        try:
            # Mettre à jour dans Django
            django_annotation = self.get_annotation(document)
            if django_annotation:
                django_annotation.final_annotations.update(annotations)
                django_annotation.save()
            
            # Mettre à jour dans MongoDB
            success = self.mongodb_service.update_annotation(
                document.id, annotations, user
            )
            
            if success:
                logger.info(f"Annotation mise à jour pour document {document.id}")
                return True
            else:
                logger.warning(f"Échec mise à jour MongoDB pour annotation")
                return False
                
        except Exception as e:
            logger.error(f"Erreur mise à jour annotation hybride: {e}")
            return False
    
    def validate_annotation(self, document: Document, user: User, 
                           validation_notes: str = '') -> bool:
        """Valide une annotation dans Django et MongoDB"""
        try:
            # Valider dans Django
            django_annotation = self.get_annotation(document)
            if django_annotation:
                django_annotation.is_validated = True
                django_annotation.validated_by = user
                django_annotation.validation_notes = validation_notes
                django_annotation.save()
            
            # Valider dans MongoDB
            success = self.mongodb_service.validate_annotation(
                document.id, user, validation_notes
            )
            
            if success:
                logger.info(f"Annotation validée pour document {document.id}")
                return True
            else:
                logger.warning(f"Échec validation MongoDB")
                return False
                
        except Exception as e:
            logger.error(f"Erreur validation annotation hybride: {e}")
            return False
    
    # ==================== HISTORIQUE ====================
    
    def get_annotation_history(self, document: Document) -> List[Dict]:
        """Récupère l'historique des annotations depuis Django et MongoDB"""
        try:
            history = []
            
            # Récupérer l'historique Django
            django_annotation = self.get_annotation(document)
            if django_annotation:
                for entry in django_annotation.history.all():
                    history.append({
                        'source': 'django',
                        'id': str(entry.id),
                        'action_type': entry.action_type,
                        'field_name': entry.field_name,
                        'old_value': entry.old_value,
                        'new_value': entry.new_value,
                        'comment': entry.comment,
                        'performed_by': entry.performed_by.username,
                        'created_at': entry.created_at
                    })
            
            # Récupérer l'historique MongoDB
            mongo_history = self.mongodb_service.get_annotation_history(document.id)
            for entry in mongo_history:
                history.append({
                    'source': 'mongodb',
                    'id': str(entry.id),
                    'action_type': entry.action_type,
                    'field_name': entry.field_name,
                    'old_value': entry.old_value,
                    'new_value': entry.new_value,
                    'comment': entry.comment,
                    'performed_by_id': entry.performed_by_id,
                    'created_at': entry.created_at
                })
            
            # Trier par date
            history.sort(key=lambda x: x['created_at'], reverse=True)
            
            return history
            
        except Exception as e:
            logger.error(f"Erreur récupération historique hybride: {e}")
            return []
    
    # ==================== STATISTIQUES ====================
    
    def get_combined_statistics(self) -> Dict:
        """Récupère les statistiques combinées Django + MongoDB"""
        try:
            # Statistiques Django
            django_stats = {
                'total_documents': Document.objects.count(),
                'total_schemas': AnnotationSchema.objects.count(),
                'total_annotations_django': Annotation.objects.count(),
                'validated_annotations_django': Annotation.objects.filter(is_validated=True).count(),
                'completed_annotations_django': Annotation.objects.filter(is_complete=True).count()
            }
            
            # Statistiques MongoDB
            mongo_stats = self.mongodb_service.get_annotation_statistics()
            
            # Combiner les statistiques
            combined_stats = {
                **django_stats,
                **mongo_stats,
                'data_sources': ['django', 'mongodb'],
                'sync_status': 'active'
            }
            
            return combined_stats
            
        except Exception as e:
            logger.error(f"Erreur calcul statistiques hybrides: {e}")
            return {}


# Instance globale du service hybride
hybrid_service = HybridAnnotationService()