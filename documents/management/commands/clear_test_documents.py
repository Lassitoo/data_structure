from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from django.core.files.storage import default_storage
import os

from documents.models import (
    Document, AnnotationSchema, AnnotationField,
    Annotation, AnnotationHistory
)

# Import des modèles MongoDB
try:
    from documents.mongo_models import (
        AnnotationSchemaMongo, AnnotationMongo, 
        AnnotationHistoryMongo, DocumentMetadataMongo,
        connect_mongodb
    )
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False


class Command(BaseCommand):
    """
    Commande pour supprimer tous les documents de test de la base de données
    Usage: python manage.py clear_test_documents [--confirm] [--keep-users] [--mongodb-only] [--django-only]
    """

    help = 'Supprime tous les documents de test de la base de données (Django + MongoDB)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirmer la suppression sans demander de confirmation interactive'
        )
        parser.add_argument(
            '--keep-users',
            action='store_true',
            help='Conserver les utilisateurs de test (ne supprimer que les documents et annotations)'
        )
        parser.add_argument(
            '--mongodb-only',
            action='store_true',
            help='Supprimer uniquement les données MongoDB'
        )
        parser.add_argument(
            '--django-only',
            action='store_true',
            help='Supprimer uniquement les données Django'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Afficher ce qui serait supprimé sans effectuer la suppression'
        )

    def handle(self, *args, **options):
        # Vérifier les options conflictuelles
        if options['mongodb_only'] and options['django_only']:
            self.stdout.write(
                self.style.ERROR('Les options --mongodb-only et --django-only sont mutuellement exclusives')
            )
            return

        # Afficher un résumé de ce qui va être supprimé
        self.show_summary(options)

        # Demander confirmation si pas en mode --confirm
        if not options['confirm'] and not options['dry_run']:
            confirm = input('\nÊtes-vous sûr de vouloir supprimer ces données ? (oui/non): ')
            if confirm.lower() not in ['oui', 'yes', 'y', 'o']:
                self.stdout.write(self.style.WARNING('Suppression annulée.'))
                return

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('Mode dry-run activé - aucune suppression ne sera effectuée.'))
            return

        # Effectuer la suppression
        try:
            with transaction.atomic():
                if not options['mongodb_only']:
                    self.clear_django_data(options['keep_users'])
                
                if not options['django_only'] and MONGODB_AVAILABLE:
                    self.clear_mongodb_data()

            self.stdout.write(
                self.style.SUCCESS('✅ Suppression terminée avec succès !')
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Erreur lors de la suppression : {e}')
            )
            raise

    def show_summary(self, options):
        """Affiche un résumé de ce qui va être supprimé"""
        self.stdout.write(self.style.WARNING('=== RÉSUMÉ DE LA SUPPRESSION ==='))
        
        if not options['mongodb_only']:
            # Compter les données Django
            documents_count = Document.objects.count()
            schemas_count = AnnotationSchema.objects.count()
            fields_count = AnnotationField.objects.count()
            annotations_count = Annotation.objects.count()
            history_count = AnnotationHistory.objects.count()
            users_count = User.objects.filter(is_superuser=False).count()

            self.stdout.write(f'\n📊 DONNÉES DJANGO À SUPPRIMER :')
            self.stdout.write(f'  • Documents : {documents_count}')
            self.stdout.write(f'  • Schémas d\'annotation : {schemas_count}')
            self.stdout.write(f'  • Champs d\'annotation : {fields_count}')
            self.stdout.write(f'  • Annotations : {annotations_count}')
            self.stdout.write(f'  • Historique d\'annotations : {history_count}')
            
            if not options['keep_users']:
                self.stdout.write(f'  • Utilisateurs de test : {users_count}')
            else:
                self.stdout.write(f'  • Utilisateurs de test : 0 (conservés)')

        if not options['django_only'] and MONGODB_AVAILABLE:
            # Se connecter à MongoDB pour compter
            if connect_mongodb():
                try:
                    mongo_schemas_count = AnnotationSchemaMongo.objects.count()
                    mongo_annotations_count = AnnotationMongo.objects.count()
                    mongo_history_count = AnnotationHistoryMongo.objects.count()
                    mongo_metadata_count = DocumentMetadataMongo.objects.count()

                    self.stdout.write(f'\n🍃 DONNÉES MONGODB À SUPPRIMER :')
                    self.stdout.write(f'  • Schémas d\'annotation : {mongo_schemas_count}')
                    self.stdout.write(f'  • Annotations : {mongo_annotations_count}')
                    self.stdout.write(f'  • Historique d\'annotations : {mongo_history_count}')
                    self.stdout.write(f'  • Métadonnées de documents : {mongo_metadata_count}')
                except Exception as e:
                    self.stdout.write(f'  ⚠️  Erreur lors du comptage MongoDB : {e}')
            else:
                self.stdout.write(f'\n🍃 MONGODB : Connexion impossible, données non comptées')

    def clear_django_data(self, keep_users=False):
        """Supprime toutes les données Django de test"""
        self.stdout.write('\n🗑️  Suppression des données Django...')

        # Supprimer les fichiers physiques des documents
        self.clear_document_files()

        # Supprimer dans l'ordre pour éviter les contraintes de clés étrangères
        deleted_counts = {}
        
        deleted_counts['history'] = AnnotationHistory.objects.all().delete()[0]
        self.stdout.write(f'  ✓ Historique d\'annotations supprimé : {deleted_counts["history"]}')

        deleted_counts['annotations'] = Annotation.objects.all().delete()[0]
        self.stdout.write(f'  ✓ Annotations supprimées : {deleted_counts["annotations"]}')

        deleted_counts['fields'] = AnnotationField.objects.all().delete()[0]
        self.stdout.write(f'  ✓ Champs d\'annotation supprimés : {deleted_counts["fields"]}')

        deleted_counts['schemas'] = AnnotationSchema.objects.all().delete()[0]
        self.stdout.write(f'  ✓ Schémas d\'annotation supprimés : {deleted_counts["schemas"]}')

        deleted_counts['documents'] = Document.objects.all().delete()[0]
        self.stdout.write(f'  ✓ Documents supprimés : {deleted_counts["documents"]}')

        if not keep_users:
            # Supprimer les utilisateurs de test (sauf admin)
            deleted_counts['users'] = User.objects.filter(is_superuser=False).delete()[0]
            self.stdout.write(f'  ✓ Utilisateurs de test supprimés : {deleted_counts["users"]}')
        else:
            self.stdout.write(f'  → Utilisateurs conservés')

        total_django = sum(deleted_counts.values())
        self.stdout.write(f'  📊 Total Django supprimé : {total_django} enregistrements')

    def clear_mongodb_data(self):
        """Supprime toutes les données MongoDB de test"""
        self.stdout.write('\n🍃 Suppression des données MongoDB...')

        if not connect_mongodb():
            self.stdout.write(self.style.ERROR('  ❌ Impossible de se connecter à MongoDB'))
            return

        try:
            deleted_counts = {}

            # Supprimer les données MongoDB dans l'ordre
            deleted_counts['history'] = AnnotationHistoryMongo.objects.all().delete()
            self.stdout.write(f'  ✓ Historique d\'annotations MongoDB supprimé : {deleted_counts["history"]}')

            deleted_counts['annotations'] = AnnotationMongo.objects.all().delete()
            self.stdout.write(f'  ✓ Annotations MongoDB supprimées : {deleted_counts["annotations"]}')

            deleted_counts['schemas'] = AnnotationSchemaMongo.objects.all().delete()
            self.stdout.write(f'  ✓ Schémas d\'annotation MongoDB supprimés : {deleted_counts["schemas"]}')

            deleted_counts['metadata'] = DocumentMetadataMongo.objects.all().delete()
            self.stdout.write(f'  ✓ Métadonnées de documents MongoDB supprimées : {deleted_counts["metadata"]}')

            total_mongo = sum(deleted_counts.values())
            self.stdout.write(f'  📊 Total MongoDB supprimé : {total_mongo} documents')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ❌ Erreur lors de la suppression MongoDB : {e}'))
            raise

    def clear_document_files(self):
        """Supprime les fichiers physiques des documents"""
        self.stdout.write('  🗂️  Suppression des fichiers physiques...')
        
        files_deleted = 0
        files_errors = 0
        
        for document in Document.objects.all():
            if document.file:
                try:
                    # Supprimer le fichier physique
                    if default_storage.exists(document.file.name):
                        default_storage.delete(document.file.name)
                        files_deleted += 1
                except Exception as e:
                    files_errors += 1
                    self.stdout.write(f'    ⚠️  Erreur suppression fichier {document.file.name}: {e}')

        self.stdout.write(f'  ✓ Fichiers supprimés : {files_deleted}')
        if files_errors > 0:
            self.stdout.write(f'  ⚠️  Erreurs de suppression : {files_errors}')

        # Nettoyer les dossiers vides dans media/documents/
        self.clean_empty_directories()

    def clean_empty_directories(self):
        """Nettoie les dossiers vides dans media/documents/"""
        try:
            media_root = default_storage.location
            documents_path = os.path.join(media_root, 'documents')
            
            if os.path.exists(documents_path):
                # Parcourir et supprimer les dossiers vides
                for root, dirs, files in os.walk(documents_path, topdown=False):
                    for dir_name in dirs:
                        dir_path = os.path.join(root, dir_name)
                        try:
                            if not os.listdir(dir_path):  # Dossier vide
                                os.rmdir(dir_path)
                        except OSError:
                            pass  # Dossier non vide ou erreur d'accès
                            
                self.stdout.write('  ✓ Dossiers vides nettoyés')
        except Exception as e:
            self.stdout.write(f'  ⚠️  Erreur nettoyage dossiers : {e}')