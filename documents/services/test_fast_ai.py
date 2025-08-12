# documents/services/test_fast_ai.py
"""
Test du service IA rapide
"""

import os
import sys
import django

# Configuration Django pour les tests
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'data_structure.settings')
django.setup()

from fast_ai_service import FastAIService
import json


def test_ai_service():
    """Test complet du service IA rapide"""
    
    print("🚀 Test du service IA rapide")
    print("=" * 50)
    
    # Initialisation du service
    try:
        ai_service = FastAIService()
        print("✅ Service IA initialisé avec succès")
    except Exception as e:
        print(f"❌ Erreur initialisation: {e}")
        return
    
    # Test de connexion
    print("\n🔌 Test de connexion Ollama...")
    if ai_service._test_connection():
        print("✅ Connexion Ollama OK")
    else:
        print("❌ Connexion Ollama échouée")
        return
    
    # Test d'analyse de type de document
    print("\n📋 Test d'analyse de type de document...")
    metadata = {
        'filename': 'test_contrat.pdf',
        'file_size': 1024000,
        'mime_type': 'application/pdf'
    }
    
    content = """
    CONTRAT DE TRAVAIL
    
    Entre les soussignés :
    La société ABC, représentée par M. Dupont
    Et M. Martin, employé
    
    Article 1 - Objet
    Le présent contrat a pour objet l'embauche de M. Martin en qualité de développeur.
    
    Article 2 - Durée
    Le contrat est conclu pour une durée indéterminée.
    
    Article 3 - Rémunération
    Le salaire mensuel est fixé à 3500 euros brut.
    """
    
    doc_type = ai_service.analyze_document_type(metadata, content)
    print(f"📋 Type détecté: {doc_type}")
    
    # Test de génération de schéma
    print("\n🏗️ Test de génération de schéma...")
    metadata['document_type'] = doc_type
    
    schema = ai_service.generate_annotation_schema(metadata, content)
    print(f"✅ Schéma généré: {len(schema.get('fields', []))} champs")
    print("📝 Champs du schéma:")
    for field in schema.get('fields', [])[:3]:  # Afficher les 3 premiers
        print(f"  - {field.get('name')}: {field.get('type')}")
    
    # Test de génération de pré-annotations
    print("\n🏷️ Test de génération de pré-annotations...")
    annotations = ai_service.generate_pre_annotations(content, schema)
    print(f"✅ Pré-annotations générées: {len(annotations)} champs")
    print("📝 Exemples d'annotations:")
    for i, (key, value) in enumerate(list(annotations.items())[:3]):
        print(f"  - {key}: {value}")
    
    print("\n🎉 Tests terminés avec succès!")


def test_performance():
    """Test de performance"""
    
    print("\n⚡ Test de performance")
    print("=" * 30)
    
    import time
    
    ai_service = FastAIService()
    
    # Test simple
    start_time = time.time()
    
    metadata = {'filename': 'test.pdf', 'file_size': 1000000, 'mime_type': 'application/pdf'}
    content = "Ceci est un document de test pour mesurer les performances."
    
    doc_type = ai_service.analyze_document_type(metadata, content)
    
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"⏱️ Temps d'analyse: {duration:.2f} secondes")
    print(f"📋 Type détecté: {doc_type}")


if __name__ == "__main__":
    print("🧪 Tests du service IA rapide")
    print("=" * 50)
    
    # Test principal
    test_ai_service()
    
    # Test de performance
    test_performance()
    
    print("\n✨ Tous les tests sont terminés!")

