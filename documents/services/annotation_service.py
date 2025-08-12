# documents/services/annotation_service.py
import logging
from typing import Dict, Any, Optional
from django.utils import timezone
from django.contrib.auth.models import User

from .metadata_extractor import MetadataExtractor
from .mistral_service import MistralService
from ..models import Document, AnnotationSchema, Annotation, AnnotationField, AnnotationHistory

logger = logging.getLogger('documents')


class AnnotationService:
    """Service principal pour la gestion du workflow d'annotation"""

    def __init__(self):
        self.metadata_extractor = MetadataExtractor()
        self.mistral_service = MistralService()

    def process_uploaded_document(self, document: Document, user: User) -> Dict[str, Any]:
        """
        Lance le traitement complet d'un document téléversé

        Args:
            document (Document): Instance du document
            user (User): Utilisateur qui a téléversé le document

        Returns:
            Dict: Résultat du traitement
        """
        try:
            logger.info(f"Début du traitement du document: {document.title}")

            # 1. Extraction des métadonnées
            metadata_result = self.extract_document_metadata(document)
            if not metadata_result['success']:
                return metadata_result

            # 2. Analyse complète du contenu par le LLM
            analysis_result = self.analyze_document_content(document)
            if not analysis_result['success']:
                logger.warning(f"Analyse du contenu échouée: {analysis_result.get('error')}")
                # On continue même si l'analyse échoue

            # 3. Génération du schéma d'annotation basé sur l'analyse complète
            schema_result = self.generate_annotation_schema(document, user)
            if not schema_result['success']:
                return schema_result

            logger.info(f"Traitement terminé pour: {document.title}")
            return {
                'success': True,
                'message': 'Document traité avec succès',
                'metadata': metadata_result['metadata'],
                'content_analysis': analysis_result.get('analysis', {}),
                'schema_id': schema_result['schema_id']
            }

        except Exception as e:
            logger.error(f"Erreur lors du traitement du document: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def extract_document_metadata(self, document: Document) -> Dict[str, Any]:
        """
        Extrait les métadonnées d'un document

        Args:
            document (Document): Instance du document

        Returns:
            Dict: Résultat de l'extraction
        """
        try:
            logger.info(f"Extraction des métadonnées pour: {document.title}")

            # Extraction des métadonnées
            file_path = document.file.path
            metadata = self.metadata_extractor.extract_metadata(file_path)

            # Mise à jour du document
            document.metadata = metadata
            document.status = 'metadata_extracted'
            document.save()

            logger.info(f"Métadonnées extraites pour: {document.title}")
            return {
                'success': True,
                'metadata': metadata
            }

        except Exception as e:
            logger.error(f"Erreur extraction métadonnées: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def analyze_document_content(self, document: Document) -> Dict[str, Any]:
        """
        Analyse le contenu complet du document avec le LLM

        Args:
            document (Document): Instance du document

        Returns:
            Dict: Résultat de l'analyse
        """
        try:
            logger.info(f"Analyse du contenu pour: {document.title}")

            # Extraction du contenu complet
            file_path = document.file.path
            # Limite à 8000 caractères pour éviter de surcharger le LLM
            full_content = self.metadata_extractor.extract_full_content(file_path, max_chars=8000)

            if not full_content.strip():
                logger.warning(f"Aucun contenu textuel extrait pour: {document.title}")
                return {
                    'success': False,
                    'error': 'Aucun contenu textuel extractible'
                }

            # Analyse du type de document avec plus de contexte
            document_type = self.mistral_service.analyze_document_type(
                document.metadata,
                full_content
            )

            # Mise à jour des métadonnées avec le type détecté
            if 'metadata' not in document.metadata:
                document.metadata['ai_analysis'] = {}

            document.metadata['ai_analysis'] = {
                'detected_type': document_type,
                'content_length': len(full_content),
                'analyzed_at': timezone.now().isoformat()
            }

            # Mise à jour du document_type dans les métadonnées principales
            document.metadata['document_type'] = document_type
            document.save()

            logger.info(f"Analyse terminée pour: {document.title} - Type détecté: {document_type}")
            return {
                'success': True,
                'analysis': {
                    'detected_type': document_type,
                    'content_length': len(full_content)
                }
            }

        except Exception as e:
            logger.error(f"Erreur analyse contenu: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def generate_annotation_schema(self, document: Document, user: User) -> Dict[str, Any]:
        """
        Génère un schéma d'annotation avec l'IA basé sur le contenu complet

        Args:
            document (Document): Instance du document
            user (User): Utilisateur créateur du schéma

        Returns:
            Dict: Résultat de la génération
        """
        try:
            logger.info(f"Génération du schéma d'annotation pour: {document.title}")

            # Extraction du contenu textuel complet pour l'analyse
            content = self._extract_full_text_content(document)

            # Génération du schéma avec l'IA en utilisant le contenu complet
            ai_schema = self.mistral_service.generate_annotation_schema(
                document.metadata,
                content
            )

            # Création du schéma en base
            schema = AnnotationSchema.objects.create(
                document=document,
                name=ai_schema.get('name', f'Schéma pour {document.title}'),
                description=ai_schema.get('description', ''),
                ai_generated_schema=ai_schema,
                final_schema=ai_schema,  # Initialement identique
                created_by=user
            )

            # Création des champs d'annotation
            self._create_annotation_fields(schema, ai_schema)

            # Mise à jour du statut du document
            document.status = 'schema_proposed'
            document.save()

            logger.info(f"Schéma généré pour: {document.title}")
            return {
                'success': True,
                'schema_id': schema.id,
                'schema': ai_schema
            }

        except Exception as e:
            logger.error(f"Erreur génération schéma: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def validate_annotation_schema(self, schema: AnnotationSchema, updated_schema: Dict, user: User) -> Dict[str, Any]:
        """
        Valide et met à jour un schéma d'annotation

        Args:
            schema (AnnotationSchema): Instance du schéma
            updated_schema (Dict): Schéma mis à jour
            user (User): Utilisateur validateur

        Returns:
            Dict: Résultat de la validation
        """
        try:
            logger.info(f"Validation du schéma pour: {schema.document.title}")

            # Mise à jour du schéma
            schema.final_schema = updated_schema
            schema.is_validated = True
            schema.validated_at = timezone.now()
            schema.save()

            # Recréation des champs d'annotation
            schema.fields.all().delete()
            self._create_annotation_fields(schema, updated_schema)

            # Mise à jour du statut du document
            schema.document.status = 'schema_validated'
            schema.document.save()

            logger.info(f"Schéma validé pour: {schema.document.title}")
            return {
                'success': True,
                'message': 'Schéma validé avec succès'
            }

        except Exception as e:
            logger.error(f"Erreur validation schéma: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def generate_pre_annotations(self, document: Document, user: User) -> Dict[str, Any]:
        """
        Génère des pré-annotations automatiques

        Args:
            document (Document): Instance du document
            user (User): Utilisateur annotateur

        Returns:
            Dict: Résultat de la génération
        """
        try:
            logger.info(f"Génération des pré-annotations pour: {document.title}")

            # Vérification du schéma validé
            if not hasattr(document, 'annotation_schema') or not document.annotation_schema.is_validated:
                return {
                    'success': False,
                    'error': 'Schéma d\'annotation non validé'
                }

            schema = document.annotation_schema

            # Extraction du contenu textuel complet
            content = self._extract_full_text_content(document)

            # Génération des pré-annotations avec l'IA
            ai_annotations = self.mistral_service.generate_pre_annotations(
                content,
                schema.final_schema
            )

            # Création ou mise à jour de l'annotation
            annotation, created = Annotation.objects.get_or_create(
                document=document,
                defaults={
                    'schema': schema,
                    'annotated_by': user
                }
            )

            annotation.ai_pre_annotations = ai_annotations
            annotation.final_annotations = ai_annotations  # Initialement identique
            annotation.save()

            # Enregistrement dans l'historique
            AnnotationHistory.objects.create(
                annotation=annotation,
                action_type='created',
                comment='Pré-annotations générées automatiquement',
                performed_by=user
            )

            # Mise à jour du statut du document
            document.status = 'pre_annotated'
            document.save()

            logger.info(f"Pré-annotations générées pour: {document.title}")
            return {
                'success': True,
                'annotation_id': annotation.id,
                'annotations': ai_annotations
            }

        except Exception as e:
            logger.error(f"Erreur génération pré-annotations: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def update_annotations(self, annotation: Annotation, updated_annotations: Dict, user: User,
                           field_name: str = None) -> Dict[str, Any]:
        """
        Met à jour les annotations.
        - Si field_name est fourni : maj d'un seul champ + 1 entrée d'historique.
        - Sinon : maj bulk (form complet) + 1 entrée d'historique par champ modifié.
        """
        try:
            logger.info(f"Mise à jour des annotations pour: {annotation.document.title}")

            # Cas 1 : un seul champ
            if field_name:
                old_value = annotation.final_annotations.get(field_name)
                new_value = updated_annotations.get(field_name)

                # Applique la mise à jour
                if new_value is not None:
                    annotation.final_annotations[field_name] = new_value
                    annotation.save()

                    AnnotationHistory.objects.create(
                        annotation=annotation,
                        action_type='updated',
                        field_name=field_name,  # 👈 jamais None ici
                        old_value=old_value,
                        new_value=new_value,
                        performed_by=user
                    )

            # Cas 2 : bulk (tous les champs du formulaire)
            else:
                changed = False
                for k, new_v in (updated_annotations or {}).items():
                    old_v = annotation.final_annotations.get(k)
                    # Optionnel : ne loguer que si changement réel
                    if old_v != new_v:
                        annotation.final_annotations[k] = new_v
                        AnnotationHistory.objects.create(
                            annotation=annotation,
                            action_type='updated',
                            field_name=k,  # 👈 un nom de champ réel
                            old_value=old_v,
                            new_value=new_v,
                            performed_by=user
                        )
                        changed = True

                if changed:
                    annotation.save()

            # Vérifie la complétion
            if self._check_annotation_completion(annotation):
                annotation.is_complete = True
                annotation.completed_at = timezone.now()
                annotation.document.status = 'annotated'
                annotation.document.save(
                    update_fields=["status"] + (["updated_at"] if hasattr(annotation.document, "updated_at") else []))
                annotation.save(update_fields=["is_complete", "completed_at"])

            logger.info(f"Annotations mises à jour pour: {annotation.document.title}")
            return {'success': True, 'completion_percentage': annotation.completion_percentage}

        except Exception as e:
            logger.error(f"Erreur mise à jour annotations: {str(e)}")
            return {'success': False, 'error': str(e)}

    def validate_annotations(self, annotation: Annotation, validator: User, notes: str = "") -> Dict[str, Any]:
        """
        Valide les annotations finales

        Args:
            annotation (Annotation): Instance d'annotation
            validator (User): Utilisateur validateur
            notes (str): Notes de validation

        Returns:
            Dict: Résultat de la validation
        """
        try:
            logger.info(f"Validation des annotations pour: {annotation.document.title}")

            # Validation
            annotation.is_validated = True
            annotation.validated_by = validator
            annotation.validated_at = timezone.now()
            annotation.validation_notes = notes
            annotation.save()

            # Mise à jour du document
            document = annotation.document
            document.status = 'validated'
            document.validated_by = validator
            document.validated_at = timezone.now()
            document.save()

            # Enregistrement dans l'historique
            AnnotationHistory.objects.create(
                annotation=annotation,
                action_type='validated',
                comment=f'Annotations validées: {notes}',
                performed_by=validator
            )

            logger.info(f"Annotations validées pour: {annotation.document.title}")
            return {
                'success': True,
                'message': 'Annotations validées avec succès'
            }

        except Exception as e:
            logger.error(f"Erreur validation annotations: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _extract_full_text_content(self, document: Document) -> str:
        """
        Extrait la TOTALITÉ du contenu textuel d'un document pour l'analyse complète par l'IA

        Args:
            document (Document): Instance du document

        Returns:
            str: Contenu textuel COMPLET INTÉGRAL
        """
        try:
            file_path = document.file.path

            # Utilisation de la nouvelle méthode d'extraction COMPLÈTE - AUCUNE LIMITATION
            full_content = self.metadata_extractor.extract_full_content(file_path)

            if full_content and len(full_content.strip()) > 0:
                logger.info(f"Contenu COMPLET extrait: {len(full_content)} caractères pour {document.title}")
                return full_content

            # Fallback sur l'ancien système si l'extraction complète échoue
            logger.warning(f"Extraction complète échouée, utilisation du fallback pour: {document.title}")
            return self._extract_text_content_fallback(document)

        except Exception as e:
            logger.error(f"Erreur extraction contenu complet: {str(e)}")
            return self._extract_text_content_fallback(document)

    def _extract_text_content_fallback(self, document: Document) -> str:
        """Méthode fallback pour l'extraction de contenu (ancienne méthode)"""
        try:
            if 'text_preview' in document.metadata:
                return document.metadata['text_preview']

            # Extraction basique selon le type de fichier
            file_path = document.file.path
            file_extension = document.file_extension

            if file_extension == '.txt':
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()[:2000]  # Limite à 2000 caractères

            # Pour d'autres types, retourner le contenu des métadonnées
            return str(document.metadata.get('text_preview', ''))[:2000]

        except Exception as e:
            logger.error(f"Erreur extraction contenu textuel fallback: {str(e)}")
            return ""

    def _create_annotation_fields(self, schema: AnnotationSchema, schema_data: Dict):
        """Crée les champs d'annotation à partir du schéma"""
        try:
            fields_data = schema_data.get('fields', [])

            for i, field_data in enumerate(fields_data):
                AnnotationField.objects.create(
                    schema=schema,
                    name=field_data.get('name', f'field_{i}'),
                    label=field_data.get('label', field_data.get('name', f'Champ {i + 1}')),
                    field_type=field_data.get('type', 'text'),
                    description=field_data.get('description', ''),
                    is_required=field_data.get('required', False),
                    choices=field_data.get('choices', []),
                    order=i
                )

        except Exception as e:
            logger.error(f"Erreur création champs annotation: {str(e)}")

    def _check_annotation_completion(self, annotation: Annotation) -> bool:
        """Vérifie si l'annotation est complète"""
        try:
            required_fields = annotation.schema.fields.filter(is_required=True)

            for field in required_fields:
                field_value = annotation.final_annotations.get(field.name)
                if not field_value or (isinstance(field_value, str) and field_value.strip() == ""):
                    return False

            return True

        except Exception as e:
            logger.error(f"Erreur vérification completion: {str(e)}")
            return False

    def get_document_statistics(self) -> Dict[str, Any]:
        """Retourne des statistiques sur les documents"""
        try:
            from django.db.models import Count

            total_documents = Document.objects.count()

            stats_by_status = Document.objects.values('status').annotate(
                count=Count('id')
            ).order_by('status')

            stats_by_type = Document.objects.values('file_type').annotate(
                count=Count('id')
            ).order_by('file_type')

            validated_annotations = Annotation.objects.filter(is_validated=True).count()

            return {
                'total_documents': total_documents,
                'by_status': list(stats_by_status),
                'by_type': list(stats_by_type),
                'validated_annotations': validated_annotations
            }

        except Exception as e:
            logger.error(f"Erreur statistiques: {str(e)}")
            return {}