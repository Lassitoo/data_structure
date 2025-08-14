from django.core.management.base import BaseCommand
from django.db import transaction

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
    Commande rapide pour supprimer tous les documents de test
    Usage: python manage.py quick_clear
    """

    help = 'Suppression rapide de tous les documents de test (sans confirmation)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('🗑️  Suppression rapide de tous les documents de test...'))

        try:
            with transaction.atomic():
                # Suppression Django
                self.clear_django_data()
                
                # Suppression MongoDB si disponible
                if MONGODB_AVAILABLE:
                    self.clear_mongodb_data()

            self.stdout.write(
                self.style.SUCCESS('✅ Suppression rapide terminée avec succès !')
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Erreur lors de la suppression : {e}')
            )
            raise

    def clear_django_data(self):
        """Supprime rapidement toutes les données Django"""
        # Supprimer dans l'ordre pour éviter les contraintes de clés étrangères
        counts = {
            'history': AnnotationHistory.objects.all().delete()[0],
            'annotations': Annotation.objects.all().delete()[0],
            'fields': AnnotationField.objects.all().delete()[0],
            'schemas': AnnotationSchema.objects.all().delete()[0],
            'documents': Document.objects.all().delete()[0],
        }
        
        total = sum(counts.values())
        self.stdout.write(f'  Django: {total} enregistrements supprimés')

    def clear_mongodb_data(self):
        """Supprime rapidement toutes les données MongoDB"""
        if not connect_mongodb():
            self.stdout.write('  MongoDB: connexion impossible')
            return

        try:
            counts = {
                'history': AnnotationHistoryMongo.objects.all().delete(),
                'annotations': AnnotationMongo.objects.all().delete(),
                'schemas': AnnotationSchemaMongo.objects.all().delete(),
                'metadata': DocumentMetadataMongo.objects.all().delete(),
            }
            
            total = sum(counts.values())
            self.stdout.write(f'  MongoDB: {total} documents supprimés')

        except Exception as e:
            self.stdout.write(f'  MongoDB: erreur - {e}')