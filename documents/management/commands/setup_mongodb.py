# documents/management/commands/setup_mongodb.py
"""
Commande Django pour initialiser MongoDB et migrer les données existantes
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from documents.models import Document, AnnotationSchema, Annotation, AnnotationHistory
from documents.mongo_models import (
    AnnotationSchemaMongo, AnnotationMongo, AnnotationHistoryMongo,
    DocumentMetadataMongo, connect_mongodb, init_mongodb_indexes
)
from documents.services.mongodb_service import get_mongodb_service
import uuid
from datetime import datetime


class Command(BaseCommand):
    help = 'Initialise MongoDB et migre les données existantes depuis SQLite'

    def add_arguments(self, parser):
        parser.add_argument(
            '--migrate-data',
            action='store_true',
            help='Migre les données existantes depuis SQLite vers MongoDB',
        )
        parser.add_argument(
            '--reset-mongodb',
            action='store_true',
            help='Supprime toutes les données MongoDB existantes',
        )
        parser.add_argument(
            '--test-connection',
            action='store_true',
            help='Teste uniquement la connexion MongoDB',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 Initialisation de MongoDB...'))
        
        # Test de connexion
        if not self._test_mongodb_connection():
            raise CommandError('❌ Impossible de se connecter à MongoDB')
        
        if options['test_connection']:
            self.stdout.write(self.style.SUCCESS('✅ Test de connexion réussi'))
            return
        
        # Reset MongoDB si demandé
        if options['reset_mongodb']:
            self._reset_mongodb()
        
        # Initialiser les index
        self._setup_indexes()
        
        # Migrer les données si demandé
        if options['migrate_data']:
            self._migrate_existing_data()
        
        self.stdout.write(self.style.SUCCESS('✅ Configuration MongoDB terminée'))

    def _test_mongodb_connection(self):
        """Teste la connexion à MongoDB"""
        try:
            if connect_mongodb():
                self.stdout.write(self.style.SUCCESS('✅ Connexion MongoDB établie'))
                return True
            else:
                self.stdout.write(self.style.ERROR('❌ Échec de connexion MongoDB'))
                return False
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Erreur MongoDB: {e}'))
            return False

    def _setup_indexes(self):
        """Configure les index MongoDB"""
        try:
            self.stdout.write('📊 Création des index MongoDB...')
            if init_mongodb_indexes():
                self.stdout.write(self.style.SUCCESS('✅ Index créés avec succès'))
            else:
                self.stdout.write(self.style.WARNING('⚠️ Problème lors de la création des index'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Erreur lors de la création des index: {e}'))

    def _reset_mongodb(self):
        """Supprime toutes les données MongoDB"""
        try:
            self.stdout.write(self.style.WARNING('🗑️ Suppression des données MongoDB...'))
            
            # Supprimer toutes les collections
            AnnotationSchemaMongo.drop_collection()
            AnnotationMongo.drop_collection()
            AnnotationHistoryMongo.drop_collection()
            DocumentMetadataMongo.drop_collection()
            
            self.stdout.write(self.style.SUCCESS('✅ Données MongoDB supprimées'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Erreur lors de la suppression: {e}'))

    def _migrate_existing_data(self):
        """Migre les données existantes depuis SQLite vers MongoDB"""
        try:
            self.stdout.write('🔄 Migration des données vers MongoDB...')
            
            # Migrer les schémas d'annotation
            schemas_migrated = self._migrate_annotation_schemas()
            self.stdout.write(f'📋 {schemas_migrated} schémas migrés')
            
            # Migrer les annotations
            annotations_migrated = self._migrate_annotations()
            self.stdout.write(f'📝 {annotations_migrated} annotations migrées')
            
            # Migrer l'historique
            history_migrated = self._migrate_annotation_history()
            self.stdout.write(f'📚 {history_migrated} entrées d\'historique migrées')
            
            # Migrer les métadonnées des documents
            metadata_migrated = self._migrate_document_metadata()
            self.stdout.write(f'📊 {metadata_migrated} métadonnées migrées')
            
            self.stdout.write(self.style.SUCCESS('✅ Migration terminée'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Erreur lors de la migration: {e}'))

    def _migrate_annotation_schemas(self):
        """Migre les schémas d'annotation"""
        count = 0
        try:
            for schema in AnnotationSchema.objects.all():
                # Vérifier si déjà migré
                if AnnotationSchemaMongo.objects(document_id=schema.document.id).first():
                    continue
                
                mongo_schema = AnnotationSchemaMongo(
                    document_id=schema.document.id,
                    name=schema.name,
                    description=schema.description,
                    ai_generated_schema=schema.ai_generated_schema,
                    final_schema=schema.final_schema,
                    is_validated=schema.is_validated,
                    created_by_id=schema.created_by.id,
                    created_at=schema.created_at,
                    updated_at=schema.updated_at,
                    validated_at=schema.validated_at
                )
                
                # Migrer les champs avec la classe EmbeddedDocument
                from documents.mongo_models import AnnotationFieldMongo
                fields = []
                for field in schema.fields.all():
                    field_mongo = AnnotationFieldMongo(
                        name=field.name,
                        label=field.label,
                        field_type=field.field_type,
                        description=field.description or '',
                        is_required=field.is_required,
                        is_multiple=field.is_multiple,
                        choices=field.choices or [],
                        order=field.order
                    )
                    fields.append(field_mongo)
                
                mongo_schema.fields = fields
                mongo_schema.save()
                count += 1
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erreur migration schémas: {e}'))
        
        return count

    def _migrate_annotations(self):
        """Migre les annotations"""
        count = 0
        try:
            for annotation in Annotation.objects.all():
                # Vérifier si déjà migré
                if AnnotationMongo.objects(document_id=annotation.document.id).first():
                    continue
                
                mongo_annotation = AnnotationMongo(
                    document_id=annotation.document.id,
                    schema_id=uuid.uuid4(),  # Générer un UUID temporaire
                    ai_pre_annotations=annotation.ai_pre_annotations,
                    final_annotations=annotation.final_annotations,
                    is_complete=annotation.is_complete,
                    is_validated=annotation.is_validated,
                    confidence_scores={},
                    validation_notes=annotation.validation_notes,
                    annotated_by_id=annotation.annotated_by.id,
                    validated_by_id=annotation.validated_by.id if annotation.validated_by else None,
                    created_at=annotation.created_at,
                    updated_at=annotation.updated_at,
                    completed_at=annotation.completed_at,
                    validated_at=annotation.validated_at
                )
                
                mongo_annotation.save()
                count += 1
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erreur migration annotations: {e}'))
        
        return count

    def _migrate_annotation_history(self):
        """Migre l'historique des annotations"""
        count = 0
        try:
            for history in AnnotationHistory.objects.all():
                mongo_history = AnnotationHistoryMongo(
                    annotation_id=uuid.uuid4(),  # Générer un UUID temporaire
                    document_id=history.annotation.document.id,
                    action_type=history.action_type,
                    field_name=history.field_name,
                    old_value=history.old_value,
                    new_value=history.new_value,
                    comment=history.comment,
                    performed_by_id=history.performed_by.id,
                    created_at=history.created_at
                )
                
                mongo_history.save()
                count += 1
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erreur migration historique: {e}'))
        
        return count

    def _migrate_document_metadata(self):
        """Migre les métadonnées des documents"""
        count = 0
        try:
            for document in Document.objects.all():
                # Vérifier si déjà migré
                if DocumentMetadataMongo.objects(document_id=document.id).first():
                    continue
                
                mongo_metadata = DocumentMetadataMongo(
                    document_id=document.id,
                    extracted_text='',  # À remplir lors du traitement
                    extracted_entities=[],
                    extracted_keywords=[],
                    ai_analysis=document.metadata,  # Utiliser les métadonnées existantes
                    language_detected='',
                    document_type_detected=document.file_type,
                    word_count=0,
                    page_count=0,
                    character_count=0,
                    created_at=document.created_at,
                    updated_at=document.updated_at
                )
                
                mongo_metadata.save()
                count += 1
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erreur migration métadonnées: {e}'))
        
        return count

    def _create_test_data(self):
        """Crée des données de test dans MongoDB"""
        try:
            self.stdout.write('🧪 Création de données de test...')
            
            # Créer un utilisateur de test s'il n'existe pas
            user, created = User.objects.get_or_create(
                username='test_user',
                defaults={'email': 'test@example.com'}
            )
            
            # Créer un document de test s'il n'existe pas
            if not Document.objects.filter(title='Document de test MongoDB').exists():
                document = Document.objects.create(
                    title='Document de test MongoDB',
                    description='Document créé pour tester MongoDB',
                    file_type='pdf',
                    file_size=1024,
                    uploaded_by=user
                )
                
                # Créer un schéma de test
                schema_data = {
                    'name': 'Schéma de test',
                    'description': 'Schéma créé pour tester MongoDB',
                    'ai_generated_schema': {'test': 'schema'},
                    'final_schema': {'test': 'final'},
                    'fields': [
                        {
                            'name': 'test_field',
                            'label': 'Champ de test',
                            'field_type': 'text',
                            'description': 'Un champ de test',
                            'is_required': True,
                            'is_multiple': False,
                            'choices': [],
                            'order': 1
                        }
                    ]
                }
                
                mongodb_service = get_mongodb_service()
                schema_id = mongodb_service.create_annotation_schema(document, schema_data, user)
                
                # Créer une annotation de test
                annotation_id = mongodb_service.create_annotation(
                    document, schema_id, user, 
                    {'test_field': 'Valeur de test IA'}
                )
                
                self.stdout.write(self.style.SUCCESS('✅ Données de test créées'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Erreur création données test: {e}'))