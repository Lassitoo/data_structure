#!/usr/bin/env python3
"""
Test spécifique pour le fichier CELEX PDF
Teste l'extraction des métadonnées et la génération du JSON
"""

import os
import sys
import json
import time
from pathlib import Path

# Ajouter le répertoire du projet au path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Imports Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'data_structure.settings')
import django
django.setup()

from documents.services.fast_ai_service import FastAIService
from documents.services.document_processor import DocumentProcessor
from documents.services.metadata_extractor import MetadataExtractor

def test_celex_pdf():
    """Test complet avec le fichier CELEX PDF"""
    
    print("=" * 60)
    print("TEST DU FICHIER CELEX PDF")
    print("=" * 60)
    
    # Chemin du fichier
    pdf_path = "media/documents/2025/08/12/CELEX_52013XC080204_EN_TXT.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"❌ Fichier non trouvé: {pdf_path}")
        return False
    
    print(f"📄 Fichier trouvé: {pdf_path}")
    print(f"📊 Taille: {os.path.getsize(pdf_path):,} bytes")
    
    # 1. Test de l'extraction des métadonnées
    print("\n" + "=" * 40)
    print("1. EXTRACTION DES MÉTADONNÉES")
    print("=" * 40)
    
    try:
        metadata_extractor = MetadataExtractor()
        metadata = metadata_extractor.extract_metadata(pdf_path)
        
        print("✅ Métadonnées extraites:")
        for key, value in metadata.items():
            print(f"   {key}: {value}")
            
    except Exception as e:
        print(f"❌ Erreur lors de l'extraction des métadonnées: {e}")
        return False
    
    # 2. Test de l'extraction du contenu
    print("\n" + "=" * 40)
    print("2. EXTRACTION DU CONTENU")
    print("=" * 40)
    
    try:
        # Extraction directe du contenu PDF
        import PyPDF2
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            content = ""
            for page in reader.pages:
                content += page.extract_text() + "\n"
        
        print(f"✅ Contenu extrait: {len(content):,} caractères")
        print(f"📝 Aperçu (premiers 500 caractères):")
        print("-" * 40)
        print(content[:500] + "..." if len(content) > 500 else content)
        print("-" * 40)
        
    except Exception as e:
        print(f"❌ Erreur lors de l'extraction du contenu: {e}")
        return False
    
    # 3. Test du service AI
    print("\n" + "=" * 40)
    print("3. TEST DU SERVICE AI")
    print("=" * 40)
    
    try:
        ai_service = FastAIService()
        
        # Test de connexion
        print("🔌 Test de connexion à Ollama...")
        if not ai_service._test_connection():
            print("❌ Impossible de se connecter à Ollama")
            return False
        print("✅ Connexion à Ollama réussie")
        
        # Test d'analyse du type de document
        print("\n🔍 Analyse du type de document...")
        start_time = time.time()
        
        # Préparation des métadonnées pour l'analyse
        analysis_metadata = {
            'filename': os.path.basename(pdf_path),
            'file_size': os.path.getsize(pdf_path),
            'mime_type': "application/pdf"
        }
        
        document_type = ai_service.analyze_document_type(
            metadata=analysis_metadata,
            content=content[:10000]  # Premier 10k caractères pour l'analyse
        )
        analysis_time = time.time() - start_time
        
        print(f"✅ Type de document détecté: {document_type}")
        print(f"⏱️  Temps d'analyse: {analysis_time:.2f} secondes")
        
        # Test de génération du schéma
        print("\n📋 Génération du schéma d'annotation...")
        start_time = time.time()
        
        # Ajout du type de document aux métadonnées
        metadata['document_type'] = document_type
        
        schema = ai_service.generate_annotation_schema(
            document_metadata=metadata,
            document_content=content[:20000]  # Premier 20k caractères pour le schéma
        )
        schema_time = time.time() - start_time
        
        print(f"✅ Schéma généré en {schema_time:.2f} secondes")
        print("📋 Structure du schéma:")
        print(json.dumps(schema, indent=2, ensure_ascii=False))
        
        # Test de génération des pré-annotations
        print("\n🏷️  Génération des pré-annotations...")
        start_time = time.time()
        annotations = ai_service.generate_pre_annotations(
            content=content[:30000],  # Premier 30k caractères pour les annotations
            schema=schema
        )
        annotation_time = time.time() - start_time
        
        print(f"✅ Pré-annotations générées en {annotation_time:.2f} secondes")
        print("🏷️  Annotations générées:")
        print(json.dumps(annotations, indent=2, ensure_ascii=False))
        
        # Résumé des performances
        total_time = analysis_time + schema_time + annotation_time
        print(f"\n📊 RÉSUMÉ DES PERFORMANCES:")
        print(f"   - Analyse du type: {analysis_time:.2f}s")
        print(f"   - Génération du schéma: {schema_time:.2f}s")
        print(f"   - Pré-annotations: {annotation_time:.2f}s")
        print(f"   - Temps total: {total_time:.2f}s")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors du test du service AI: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Fonction principale"""
    print("🚀 Démarrage du test CELEX PDF...")
    
    success = test_celex_pdf()
    
    if success:
        print("\n" + "=" * 60)
        print("✅ TEST RÉUSSI!")
        print("=" * 60)
        print("Le service AI fonctionne correctement avec le fichier CELEX PDF.")
        print("- Extraction des métadonnées: ✅")
        print("- Extraction du contenu: ✅")
        print("- Analyse du type de document: ✅")
        print("- Génération du schéma JSON: ✅")
        print("- Génération des pré-annotations: ✅")
    else:
        print("\n" + "=" * 60)
        print("❌ TEST ÉCHOUÉ!")
        print("=" * 60)
        print("Des erreurs ont été rencontrées lors du test.")
        sys.exit(1)

if __name__ == "__main__":
    main()
