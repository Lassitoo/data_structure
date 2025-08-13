#!/usr/bin/env python
"""
Script de test pour vérifier l'intégration MongoDB
"""

import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'data_structure.settings')
django.setup()

from documents.services.hybrid_service import hybrid_service
from documents.services.mongodb_service import get_mongodb_service
from documents.models import Document
from django.contrib.auth.models import User


def test_mongodb_integration():
    """Test complet de l'intégration MongoDB"""
    
    print("🧪 === TEST D'INTÉGRATION MONGODB ===")
    
    # Test 1: Connexion MongoDB
    print("\n1️⃣ Test de connexion MongoDB...")
    try:
        mongodb_service = get_mongodb_service()
        if mongodb_service.ensure_connection():
            print("✅ Connexion MongoDB réussie")
        else:
            print("⚠️ MongoDB en mode dégradé")
    except Exception as e:
        print(f"❌ Erreur connexion: {e}")
    
    # Test 2: Statistiques MongoDB
    print("\n2️⃣ Test des statistiques MongoDB...")
    try:
        stats = mongodb_service.get_annotation_statistics()
        print(f"📊 Statistiques MongoDB: {stats}")
        
        if stats.get('status') == 'mongodb_active':
            print("✅ MongoDB actif et fonctionnel")
        elif stats.get('status') == 'mongodb_unavailable':
            print("⚠️ MongoDB indisponible - mode dégradé")
        else:
            print("❌ Problème avec MongoDB")
            
    except Exception as e:
        print(f"❌ Erreur statistiques: {e}")
    
    # Test 3: Statistiques hybrides
    print("\n3️⃣ Test des statistiques hybrides...")
    try:
        hybrid_stats = hybrid_service.get_combined_statistics()
        print(f"📈 Statistiques hybrides:")
        for key, value in hybrid_stats.items():
            print(f"   {key}: {value}")
        print("✅ Service hybride fonctionnel")
    except Exception as e:
        print(f"❌ Erreur service hybride: {e}")
    
    # Test 4: Données existantes
    print("\n4️⃣ Test des données existantes...")
    try:
        documents_count = Document.objects.count()
        users_count = User.objects.count()
        
        print(f"📄 Documents dans Django: {documents_count}")
        print(f"👥 Utilisateurs dans Django: {users_count}")
        
        if documents_count > 0:
            print("✅ Données existantes trouvées")
            
            # Test avec un document existant
            document = Document.objects.first()
            print(f"📋 Test avec document: {document.title}")
            
            # Test récupération schéma
            schema_data = hybrid_service.get_schema_with_mongodb_data(document)
            if schema_data:
                print(f"✅ Schéma récupéré: {schema_data.get('name', 'Sans nom')}")
            else:
                print("⚠️ Aucun schéma trouvé pour ce document")
            
            # Test récupération annotation
            annotation_data = hybrid_service.get_annotation_with_mongodb_data(document)
            if annotation_data:
                print(f"✅ Annotation récupérée: {len(annotation_data.get('final_annotations', {}))} champs")
            else:
                print("⚠️ Aucune annotation trouvée pour ce document")
                
        else:
            print("⚠️ Aucune donnée existante")
            
    except Exception as e:
        print(f"❌ Erreur test données: {e}")
    
    # Test 5: Création de test
    print("\n5️⃣ Test de création...")
    try:
        # Créer un utilisateur de test s'il n'existe pas
        user, created = User.objects.get_or_create(
            username='test_mongodb',
            defaults={'email': 'test@mongodb.com'}
        )
        
        if created:
            print("✅ Utilisateur de test créé")
        else:
            print("✅ Utilisateur de test existant")
        
        # Créer un document de test
        test_doc, doc_created = Document.objects.get_or_create(
            title='Test MongoDB Integration',
            defaults={
                'description': 'Document de test pour MongoDB',
                'file_type': 'pdf',
                'file_size': 1024,
                'uploaded_by': user
            }
        )
        
        if doc_created:
            print("✅ Document de test créé")
            
            # Créer un schéma de test
            schema_data = {
                'name': 'Schéma de test MongoDB',
                'description': 'Test d\'intégration',
                'ai_generated_schema': {'test': True},
                'final_schema': {'validated': True},
                'fields': [
                    {
                        'name': 'test_field',
                        'label': 'Champ de test',
                        'field_type': 'text',
                        'description': 'Un champ pour tester',
                        'is_required': True,
                        'is_multiple': False,
                        'choices': [],
                        'order': 1
                    }
                ]
            }
            
            schema = hybrid_service.create_annotation_schema(test_doc, schema_data, user)
            print(f"✅ Schéma de test créé: {schema.name}")
            
            # Créer une annotation de test
            annotation = hybrid_service.create_annotation(
                test_doc, user, 
                {'test_field': 'Valeur de test IA'}
            )
            print(f"✅ Annotation de test créée: {annotation.id}")
            
        else:
            print("✅ Document de test existant")
            
    except Exception as e:
        print(f"❌ Erreur création test: {e}")
    
    print("\n🎉 === TESTS TERMINÉS ===")
    print("\n📋 Résumé:")
    print("- MongoDB configuré avec MongoEngine")
    print("- Service hybride Django + MongoDB")
    print("- Données JSON stockées dans MongoDB")
    print("- Métadonnées dans Django ORM")
    print("- Interface transparente pour l'application")


if __name__ == '__main__':
    test_mongodb_integration()