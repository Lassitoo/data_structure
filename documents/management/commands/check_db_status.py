from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

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
    Commande pour vérifier l'état de la base de données
    Usage: python manage.py check_db_status
    """

    help = 'Affiche l\'état actuel de la base de données (Django + MongoDB)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('📊 ÉTAT DE LA BASE DE DONNÉES'))
        self.stdout.write('=' * 50)

        # Vérifier Django
        self.check_django_data()
        
        # Vérifier MongoDB si disponible
        if MONGODB_AVAILABLE:
            self.check_mongodb_data()
        else:
            self.stdout.write(self.style.WARNING('\n🍃 MongoDB non disponible'))

        self.stdout.write('\n' + '=' * 50)

    def check_django_data(self):
        """Vérifie l'état des données Django"""
        self.stdout.write(f'\n🐍 DONNÉES DJANGO :')
        
        # Compter les données
        documents_count = Document.objects.count()
        schemas_count = AnnotationSchema.objects.count()
        fields_count = AnnotationField.objects.count()
        annotations_count = Annotation.objects.count()
        history_count = AnnotationHistory.objects.count()
        users_count = User.objects.count()
        admin_count = User.objects.filter(is_superuser=True).count()
        regular_users_count = User.objects.filter(is_superuser=False).count()

        self.stdout.write(f'  • Documents : {documents_count}')
        self.stdout.write(f'  • Schémas d\'annotation : {schemas_count}')
        self.stdout.write(f'  • Champs d\'annotation : {fields_count}')
        self.stdout.write(f'  • Annotations : {annotations_count}')
        self.stdout.write(f'  • Historique d\'annotations : {history_count}')
        self.stdout.write(f'  • Utilisateurs total : {users_count}')
        self.stdout.write(f'    - Administrateurs : {admin_count}')
        self.stdout.write(f'    - Utilisateurs normaux : {regular_users_count}')

        # Afficher les statuts des documents s'il y en a
        if documents_count > 0:
            self.stdout.write(f'\n  📋 Statuts des documents :')
            from django.db.models import Count
            status_counts = Document.objects.values('status').annotate(count=Count('status')).order_by('status')
            for status_info in status_counts:
                self.stdout.write(f'    - {status_info["status"]} : {status_info["count"]}')

        # Afficher les utilisateurs s'il y en a peu
        if users_count <= 10:
            self.stdout.write(f'\n  👥 Utilisateurs :')
            for user in User.objects.all().order_by('username'):
                role = 'Admin' if user.is_superuser else 'User'
                self.stdout.write(f'    - {user.username} ({role}) - {user.email}')

    def check_mongodb_data(self):
        """Vérifie l'état des données MongoDB"""
        self.stdout.write(f'\n🍃 DONNÉES MONGODB :')
        
        if not connect_mongodb():
            self.stdout.write('  ❌ Impossible de se connecter à MongoDB')
            return

        try:
            # Compter les données MongoDB
            mongo_schemas_count = AnnotationSchemaMongo.objects.count()
            mongo_annotations_count = AnnotationMongo.objects.count()
            mongo_history_count = AnnotationHistoryMongo.objects.count()
            mongo_metadata_count = DocumentMetadataMongo.objects.count()

            self.stdout.write(f'  • Schémas d\'annotation : {mongo_schemas_count}')
            self.stdout.write(f'  • Annotations : {mongo_annotations_count}')
            self.stdout.write(f'  • Historique d\'annotations : {mongo_history_count}')
            self.stdout.write(f'  • Métadonnées de documents : {mongo_metadata_count}')

            # Afficher quelques statistiques si il y a des données
            if mongo_metadata_count > 0:
                self.stdout.write(f'\n  📊 Statistiques MongoDB :')
                
                # Types de fichiers
                pipeline = [
                    {"$group": {"_id": "$file_type", "count": {"$sum": 1}}},
                    {"$sort": {"count": -1}}
                ]
                file_types = list(DocumentMetadataMongo.objects.aggregate(pipeline))
                if file_types:
                    self.stdout.write(f'    Types de fichiers :')
                    for ft in file_types:
                        self.stdout.write(f'      - {ft["_id"]} : {ft["count"]}')

                # Statuts
                pipeline = [
                    {"$group": {"_id": "$status", "count": {"$sum": 1}}},
                    {"$sort": {"count": -1}}
                ]
                statuses = list(DocumentMetadataMongo.objects.aggregate(pipeline))
                if statuses:
                    self.stdout.write(f'    Statuts :')
                    for status in statuses:
                        self.stdout.write(f'      - {status["_id"]} : {status["count"]}')

        except Exception as e:
            self.stdout.write(f'  ❌ Erreur lors de la vérification MongoDB : {e}')