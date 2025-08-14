from django.apps import AppConfig


class DocumentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'documents'
    
    def ready(self):
        """
        Méthode appelée quand l'application est prête
        Enregistre les signaux pour la synchronisation automatique MongoDB
        """
        try:
            # Importer les signaux pour les enregistrer
            import documents.signals
            print("✅ Signaux MongoDB enregistrés avec succès")
        except Exception as e:
            print(f"❌ Erreur lors de l'enregistrement des signaux MongoDB: {e}")
