#!/usr/bin/env python3
"""
Script de mise à jour du service IA
Remplace ChatOllama par des appels HTTP directs plus rapides
"""

import os
import sys
import subprocess
import shutil

def print_step(message):
    """Affiche une étape avec formatage"""
    print(f"\n{'='*60}")
    print(f"🔄 {message}")
    print(f"{'='*60}")

def print_success(message):
    """Affiche un succès"""
    print(f"✅ {message}")

def print_error(message):
    """Affiche une erreur"""
    print(f"❌ {message}")

def check_ollama():
    """Vérifie si Ollama est installé et fonctionnel"""
    print_step("Vérification d'Ollama")
    
    try:
        # Test de connexion à Ollama
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        
        if response.status_code == 200:
            print_success("Ollama est accessible sur http://localhost:11434")
            
            # Vérifier si le modèle mistral:latest est disponible
            models = response.json().get('models', [])
            mistral_available = any('mistral' in model.get('name', '').lower() for model in models)
            
            if mistral_available:
                print_success("Modèle Mistral détecté")
                return True
            else:
                print_error("Modèle Mistral non trouvé. Installez-le avec: ollama pull mistral:latest")
                return False
        else:
            print_error(f"Ollama répond avec le code {response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"Impossible de se connecter à Ollama: {e}")
        print("💡 Assurez-vous qu'Ollama est installé et en cours d'exécution")
        return False

def update_requirements():
    """Met à jour le fichier requirements.txt"""
    print_step("Mise à jour des dépendances")
    
    try:
        # Lire le fichier requirements.txt actuel
        with open('requirements.txt', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Supprimer les dépendances ChatOllama/LangChain
        lines_to_remove = [
            'transformers',
            'torch',
            'torchvision', 
            'torchaudio',
            'accelerate',
            'sentencepiece',
            'tokenizers',
            'langchain',
            'langchain-ollama',
            'langchain-community',
            'langchain-core'
        ]
        
        new_lines = []
        for line in content.split('\n'):
            line_stripped = line.strip()
            should_keep = True
            
            for dep in lines_to_remove:
                if line_stripped.startswith(dep):
                    should_keep = False
                    print(f"🗑️ Suppression: {line_stripped}")
                    break
            
            if should_keep and line_stripped:
                new_lines.append(line)
        
        # Ajouter les nouvelles dépendances minimales
        new_dependencies = [
            '# Dépendances IA simplifiées (plus de ChatOllama)',
            'requests>=2.31.0',  # Pour les appels HTTP directs',
            '',
            '# Traitement des fichiers',
            'python-docx',
            'PyPDF2', 
            'openpyxl',
            'Pillow',
            '',
            '# Framework Django',
            'Django',
            'djangorestframework',
            '',
            '# Utilitaires',
            'python-dateutil',
            'pytz',
            '',
            '# Tests',
            'pytest',
            'pytest-django',
            '',
            '# Production',
            'gunicorn',
            'whitenoise'
        ]
        
        # Écrire le nouveau fichier
        with open('requirements.txt', 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines + new_dependencies))
        
        print_success("Fichier requirements.txt mis à jour")
        return True
        
    except Exception as e:
        print_error(f"Erreur lors de la mise à jour: {e}")
        return False

def backup_old_service():
    """Sauvegarde l'ancien service Mistral"""
    print_step("Sauvegarde de l'ancien service")
    
    try:
        old_file = 'documents/services/mistral_service.py'
        backup_file = 'documents/services/mistral_service_backup.py'
        
        if os.path.exists(old_file):
            shutil.copy2(old_file, backup_file)
            print_success(f"Ancien service sauvegardé: {backup_file}")
        else:
            print("ℹ️ Aucun ancien service à sauvegarder")
        
        return True
        
    except Exception as e:
        print_error(f"Erreur lors de la sauvegarde: {e}")
        return False

def test_new_service():
    """Teste le nouveau service IA"""
    print_step("Test du nouveau service IA")
    
    try:
        # Test simple du service
        import sys
        sys.path.append('documents/services')
        
        from fast_ai_service import FastAIService
        
        # Test d'initialisation
        ai_service = FastAIService()
        print_success("Service IA initialisé")
        
        # Test de connexion
        if ai_service._test_connection():
            print_success("Connexion Ollama OK")
        else:
            print_error("Connexion Ollama échouée")
            return False
        
        # Test simple d'analyse
        metadata = {'filename': 'test.pdf', 'file_size': 1000000, 'mime_type': 'application/pdf'}
        content = "Ceci est un document de test."
        
        doc_type = ai_service.analyze_document_type(metadata, content)
        print_success(f"Test d'analyse réussi: {doc_type}")
        
        return True
        
    except Exception as e:
        print_error(f"Erreur lors du test: {e}")
        return False

def create_migration_script():
    """Crée un script de migration pour la base de données"""
    print_step("Création du script de migration")
    
    try:
        script_content = '''#!/usr/bin/env python3
"""
Script de migration pour le nouveau service IA
"""

import os
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'data_structure.settings')
django.setup()

from documents.services.fast_ai_service import FastAIService
from documents.models import Document, AnnotationSchema

def migrate_existing_documents():
    """Met à jour les documents existants avec le nouveau service"""
    print("🔄 Migration des documents existants...")
    
    # Documents sans schéma d'annotation
    documents_without_schema = Document.objects.filter(
        annotation_schema__isnull=True,
        status__in=['uploaded', 'metadata_extracted']
    )
    
    print(f"📄 {documents_without_schema.count()} documents à traiter")
    
    ai_service = FastAIService()
    
    for document in documents_without_schema:
        try:
            print(f"🔄 Traitement de: {document.title}")
            
            # Extraction du contenu
            from documents.services.metadata_extractor import MetadataExtractor
            extractor = MetadataExtractor()
            content = extractor.extract_full_content(document.file.path)
            
            # Analyse du type
            doc_type = ai_service.analyze_document_type(document.metadata, content)
            document.metadata['document_type'] = doc_type
            document.save()
            
            # Génération du schéma
            schema = ai_service.generate_annotation_schema(document.metadata, content)
            
            # Création du schéma en base
            annotation_schema = AnnotationSchema.objects.create(
                document=document,
                name=schema.get('name', f'Schéma pour {document.title}'),
                description=schema.get('description', ''),
                ai_generated_schema=schema,
                final_schema=schema,
                created_by=document.uploaded_by
            )
            
            # Mise à jour du statut
            document.status = 'schema_proposed'
            document.save()
            
            print(f"✅ {document.title} traité avec succès")
            
        except Exception as e:
            print(f"❌ Erreur pour {document.title}: {e}")
    
    print("🎉 Migration terminée!")

if __name__ == "__main__":
    migrate_existing_documents()
'''
        
        with open('migrate_ai_service.py', 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        print_success("Script de migration créé: migrate_ai_service.py")
        return True
        
    except Exception as e:
        print_error(f"Erreur lors de la création du script: {e}")
        return False

def main():
    """Fonction principale de mise à jour"""
    print("🚀 Mise à jour du service IA - Remplacement de ChatOllama")
    print("=" * 70)
    
    # Vérifications préalables
    if not check_ollama():
        print("\n❌ Ollama n'est pas configuré correctement")
        print("💡 Installez et configurez Ollama avant de continuer")
        return False
    
    # Étapes de mise à jour
    steps = [
        ("Sauvegarde de l'ancien service", backup_old_service),
        ("Mise à jour des dépendances", update_requirements),
        ("Test du nouveau service", test_new_service),
        ("Création du script de migration", create_migration_script),
    ]
    
    for step_name, step_func in steps:
        print_step(step_name)
        if not step_func():
            print_error(f"Étape '{step_name}' a échoué")
            return False
    
    # Instructions finales
    print_step("Mise à jour terminée!")
    print("""
🎉 Mise à jour réussie! Voici ce qui a été fait:

✅ ChatOllama remplacé par des appels HTTP directs
✅ Configuration IA centralisée dans documents/services/ai_config.py
✅ Nouveau service ultra-rapide: FastAIService
✅ Ancien service sauvegardé
✅ Dépendances nettoyées

📋 Prochaines étapes:

1. Installez les nouvelles dépendances:
   pip install -r requirements.txt

2. Testez le nouveau service:
   python documents/services/test_fast_ai.py

3. Migrez les documents existants (optionnel):
   python migrate_ai_service.py

4. Redémarrez votre application Django

🚀 Votre application est maintenant plus rapide et plus simple!
""")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

