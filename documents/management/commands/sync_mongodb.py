# documents/management/commands/sync_mongodb.py
"""
Commande Django pour gérer la synchronisation MongoDB
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from documents.models import Document, AnnotationSchema, Annotation
from documents.services.mongodb_service import get_mongodb_service
from documents.signals import force_sync_document_to_mongodb, sync_all_pending_documents
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Gère la synchronisation entre Django et MongoDB'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-sync',
            action='store_true',
            help='Teste la synchronisation automatique',
        )
        parser.add_argument(
            '--force-sync',
            type=str,
            help='Force la synchronisation d\'un document spécifique (UUID)',
        )
        parser.add_argument(
            '--sync-all',
            action='store_true',
            help='Synchronise tous les documents avec MongoDB',
        )
        parser.add_argument(
            '--check-status',
            action='store_true',
            help='Vérifie le statut de synchronisation',
        )
        parser.add_argument(
            '--repair-sync',
            action='store_true',
            help='Répare les problèmes de synchronisation',
        )

    def handle(self, *args, **options):
        """Point d'entrée principal de la commande"""
        
        if options['test_sync']:
            self.test_synchronization()
        elif options['force_sync']:
            self.force_sync_document(options['force_sync'])
        elif options['sync_all']:
            self.sync_all_documents()
        elif options['check_status']:
            self.check_sync_status()
        elif options['repair_sync']:
            self.repair_synchronization()
        else:
            self.stdout.write(
                self.style.WARNING('Aucune action spécifiée. Utilisez --help pour voir les options.')
            )

    def test_synchronization(self):
        """Teste la synchronisation automatique"""
        self.stdout.write("🧪 Test de la synchronisation automatique...")
        
        try:
            # Vérifier la connexion MongoDB
            mongodb_service = get_mongodb_service()
            if not mongodb_service.is_connected():
                raise CommandError("❌ MongoDB n'est pas connecté")
            
            self.stdout.write(self.style.SUCCESS("✅ MongoDB connecté"))
            
            # Créer un utilisateur de test
            test_user, created = User.objects.get_or_create(
                username='sync_test_user',
                defaults={
                    'email': 'sync_test@example.com',
                    'first_name': 'Sync',
                    'last_name': 'Test'
                }
            )
            
            # Créer un document de test
            document = Document.objects.create(
                title="Test synchronisation automatique",
                description="Document créé pour tester la sync",
                file_type="pdf",
                file_size=2048,
                status="uploaded",
                metadata={"test": "auto_sync"},
                uploaded_by=test_user
            )
            
            self.stdout.write(f"✅ Document de test créé: {document.id}")
            
            # Vérifier la synchronisation
            from documents.mongo_models import DocumentMetadataMongo
            mongo_doc = DocumentMetadataMongo.objects(document_id=str(document.id)).first()
            
            if mongo_doc:
                self.stdout.write(self.style.SUCCESS("✅ Document synchronisé automatiquement dans MongoDB"))
                
                # Tester une mise à jour
                document.title = "Document mis à jour - test sync"
                document.save()
                
                mongo_doc.reload()
                if mongo_doc.title == document.title:
                    self.stdout.write(self.style.SUCCESS("✅ Mise à jour synchronisée automatiquement"))
                else:
                    self.stdout.write(self.style.ERROR("❌ Mise à jour non synchronisée"))
                
            else:
                self.stdout.write(self.style.ERROR("❌ Document non synchronisé dans MongoDB"))
            
            # Nettoyer
            document.delete()
            test_user.delete()
            
            self.stdout.write(self.style.SUCCESS("🎉 Test de synchronisation terminé avec succès"))
            
        except Exception as e:
            raise CommandError(f"Erreur lors du test: {e}")

    def force_sync_document(self, document_id):
        """Force la synchronisation d'un document spécifique"""
        self.stdout.write(f"🔄 Synchronisation forcée du document {document_id}...")
        
        try:
            success = force_sync_document_to_mongodb(document_id)
            if success:
                self.stdout.write(self.style.SUCCESS(f"✅ Document {document_id} synchronisé"))
            else:
                self.stdout.write(self.style.ERROR(f"❌ Échec synchronisation document {document_id}"))
                
        except Exception as e:
            raise CommandError(f"Erreur synchronisation forcée: {e}")

    def sync_all_documents(self):
        """Synchronise tous les documents avec MongoDB"""
        self.stdout.write("🔄 Synchronisation de tous les documents...")
        
        try:
            result = sync_all_pending_documents()
            
            self.stdout.write(f"📊 Résultats de synchronisation:")
            self.stdout.write(f"   ✅ Réussies: {result['synced']}")
            self.stdout.write(f"   ❌ Erreurs: {result['errors']}")
            
            if result['errors'] == 0:
                self.stdout.write(self.style.SUCCESS("🎉 Tous les documents synchronisés"))
            else:
                self.stdout.write(self.style.WARNING(f"⚠️ {result['errors']} erreurs de synchronisation"))
                
        except Exception as e:
            raise CommandError(f"Erreur synchronisation globale: {e}")

    def check_sync_status(self):
        """Vérifie le statut de synchronisation"""
        self.stdout.write("📊 Vérification du statut de synchronisation...")
        
        try:
            # Compter les documents Django
            django_docs = Document.objects.count()
            django_schemas = AnnotationSchema.objects.count()
            django_annotations = Annotation.objects.count()
            
            self.stdout.write(f"📄 Django:")
            self.stdout.write(f"   Documents: {django_docs}")
            self.stdout.write(f"   Schémas: {django_schemas}")
            self.stdout.write(f"   Annotations: {django_annotations}")
            
            # Compter les documents MongoDB
            mongodb_service = get_mongodb_service()
            if mongodb_service.is_connected():
                from documents.mongo_models import (
                    DocumentMetadataMongo, AnnotationSchemaMongo, AnnotationMongo
                )
                
                mongo_docs = DocumentMetadataMongo.objects.count()
                mongo_schemas = AnnotationSchemaMongo.objects.count()
                mongo_annotations = AnnotationMongo.objects.count()
                
                self.stdout.write(f"🍃 MongoDB:")
                self.stdout.write(f"   Documents: {mongo_docs}")
                self.stdout.write(f"   Schémas: {mongo_schemas}")
                self.stdout.write(f"   Annotations: {mongo_annotations}")
                
                # Vérifier la cohérence
                if django_docs == mongo_docs:
                    self.stdout.write(self.style.SUCCESS("✅ Documents synchronisés"))
                else:
                    self.stdout.write(self.style.WARNING(f"⚠️ Désynchronisation documents: Django({django_docs}) vs MongoDB({mongo_docs})"))
                
                if django_schemas == mongo_schemas:
                    self.stdout.write(self.style.SUCCESS("✅ Schémas synchronisés"))
                else:
                    self.stdout.write(self.style.WARNING(f"⚠️ Désynchronisation schémas: Django({django_schemas}) vs MongoDB({mongo_schemas})"))
                
                if django_annotations == mongo_annotations:
                    self.stdout.write(self.style.SUCCESS("✅ Annotations synchronisées"))
                else:
                    self.stdout.write(self.style.WARNING(f"⚠️ Désynchronisation annotations: Django({django_annotations}) vs MongoDB({mongo_annotations})"))
                
            else:
                self.stdout.write(self.style.ERROR("❌ MongoDB non connecté"))
                
        except Exception as e:
            raise CommandError(f"Erreur vérification statut: {e}")

    def repair_synchronization(self):
        """Répare les problèmes de synchronisation"""
        self.stdout.write("🔧 Réparation de la synchronisation...")
        
        try:
            mongodb_service = get_mongodb_service()
            if not mongodb_service.is_connected():
                raise CommandError("❌ MongoDB non connecté")
            
            # Identifier les documents non synchronisés
            from documents.mongo_models import DocumentMetadataMongo
            
            django_docs = Document.objects.all()
            repaired_count = 0
            error_count = 0
            
            for doc in django_docs:
                try:
                    mongo_doc = DocumentMetadataMongo.objects(document_id=str(doc.id)).first()
                    if not mongo_doc:
                        # Document manquant dans MongoDB
                        self.stdout.write(f"🔄 Réparation document {doc.id}...")
                        success = force_sync_document_to_mongodb(doc.id)
                        if success:
                            repaired_count += 1
                            self.stdout.write(f"   ✅ Réparé")
                        else:
                            error_count += 1
                            self.stdout.write(f"   ❌ Échec")
                    else:
                        # Vérifier la cohérence des données
                        if mongo_doc.title != doc.title or mongo_doc.status != doc.status:
                            self.stdout.write(f"🔄 Mise à jour document {doc.id}...")
                            mongo_doc.title = doc.title
                            mongo_doc.description = doc.description
                            mongo_doc.status = doc.status
                            mongo_doc.metadata = doc.metadata
                            mongo_doc.save()
                            repaired_count += 1
                            self.stdout.write(f"   ✅ Mis à jour")
                            
                except Exception as e:
                    error_count += 1
                    self.stdout.write(f"   ❌ Erreur: {e}")
            
            self.stdout.write(f"📊 Réparation terminée:")
            self.stdout.write(f"   ✅ Réparés: {repaired_count}")
            self.stdout.write(f"   ❌ Erreurs: {error_count}")
            
            if error_count == 0:
                self.stdout.write(self.style.SUCCESS("🎉 Synchronisation réparée avec succès"))
            else:
                self.stdout.write(self.style.WARNING(f"⚠️ {error_count} erreurs lors de la réparation"))
                
        except Exception as e:
            raise CommandError(f"Erreur réparation: {e}")