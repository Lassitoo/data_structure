#!/usr/bin/env python
"""
Script de debug simple pour tester le formulaire
"""

import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'data_structure.settings')
django.setup()

from documents.models import Document, AnnotationSchema
import json

def test_form_data():
    """Test simple pour vérifier les données du formulaire"""
    print("=== Test du formulaire ===")
    
    # Récupérer le dernier schéma créé
    schemas = AnnotationSchema.objects.all().order_by('-created_at')
    if schemas.count() == 0:
        print("❌ Aucun schéma trouvé")
        return
    
    schema = schemas.first()
    print(f"📄 Schéma: {schema.name}")
    print(f"📄 Document: {schema.document.title}")
    
    # Simuler la logique de la vue
    if schema.final_schema and schema.final_schema.get('fields'):
        schema_json = schema.final_schema
        print("✅ Utilisation de final_schema")
    elif schema.ai_generated_schema and schema.ai_generated_schema.get('fields'):
        schema_json = schema.ai_generated_schema
        print("✅ Utilisation de ai_generated_schema")
    else:
        schema_json = {}
        print("❌ Aucun schéma valide")
    
    print(f"\n📊 Nombre de champs: {len(schema_json.get('fields', []))}")
    
    # Afficher les premiers champs
    fields = schema_json.get('fields', [])
    for i, field in enumerate(fields[:5]):  # Afficher seulement les 5 premiers
        print(f"  Champ {i+1}: {field.get('name', 'N/A')} ({field.get('type', 'N/A')})")
    
    if len(fields) > 5:
        print(f"  ... et {len(fields) - 5} autres champs")
    
    # Test du JSON pour JavaScript
    js_data = json.dumps(schema_json, ensure_ascii=False)
    print(f"\n📝 Données JSON (premiers 200 chars): {js_data[:200]}...")
    
    return schema_json

if __name__ == "__main__":
    test_form_data()

