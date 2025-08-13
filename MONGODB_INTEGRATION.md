# 🍃 Intégration MongoDB - Documentation

## 📋 Vue d'ensemble

Votre projet utilise maintenant une **architecture hybride** qui combine :
- **Django ORM** pour les métadonnées et relations
- **MongoDB** pour les données JSON d'annotations

## 🏗️ Architecture

### Base de données hybride
```
┌─────────────────┐    ┌─────────────────┐
│   Django ORM    │    │    MongoDB      │
│   (SQLite)      │    │  (MongoEngine)  │
├─────────────────┤    ├─────────────────┤
│ • Users         │    │ • Annotations   │
│ • Documents     │    │ • Schemas       │
│ • Metadata      │    │ • History       │
│ • Relations     │    │ • JSON Data     │
└─────────────────┘    └─────────────────┘
         │                       │
         └───────────────────────┘
                    │
            ┌─────────────────┐
            │ Hybrid Service  │
            │ (Transparent)   │
            └─────────────────┘
```

### Modèles de données

#### Django ORM (SQLite)
- `Document` - Métadonnées des documents
- `User` - Gestion des utilisateurs
- `AnnotationSchema` - Structure des schémas
- `Annotation` - Références et statuts

#### MongoDB (MongoEngine)
- `AnnotationSchemaMongo` - Schémas JSON complets
- `AnnotationMongo` - Annotations JSON avec données
- `AnnotationHistoryMongo` - Historique détaillé
- `DocumentMetadataMongo` - Métadonnées étendues

## 🚀 Services disponibles

### 1. MongoDBService
Service bas niveau pour les opérations MongoDB directes.

```python
from documents.services.mongodb_service import get_mongodb_service

mongodb_service = get_mongodb_service()
stats = mongodb_service.get_annotation_statistics()
```

### 2. HybridAnnotationService (Recommandé)
Service haut niveau qui gère automatiquement Django + MongoDB.

```python
from documents.services.hybrid_service import hybrid_service

# Créer un schéma
schema = hybrid_service.create_annotation_schema(document, schema_data, user)

# Récupérer une annotation avec données MongoDB
annotation_data = hybrid_service.get_annotation_with_mongodb_data(document)
```

## 📊 Avantages de cette architecture

### ✅ Avantages
- **Performance** : JSON stocké nativement dans MongoDB
- **Flexibilité** : Schémas dynamiques pour les annotations
- **Scalabilité** : MongoDB gère mieux les gros volumes JSON
- **Compatibilité** : Code Django existant fonctionne toujours
- **Historique riche** : Suivi détaillé des modifications

### 🔄 Synchronisation automatique
- Toutes les opérations sont synchronisées entre Django et MongoDB
- Mode dégradé si MongoDB est indisponible
- Interface transparente pour l'application

## 🛠️ Utilisation

### Configuration
La configuration est automatique. MongoDB est configuré dans `settings.py` :

```python
MONGODB_SETTINGS = {
    'db': 'data_structure_db',
    'host': 'mongodb://localhost:27017/data_structure_db',
    'connect': False,
}
```

### Commandes de gestion

```bash
# Tester la connexion MongoDB
python manage.py setup_mongodb --test-connection

# Initialiser MongoDB et créer les index
python manage.py setup_mongodb

# Migrer les données existantes vers MongoDB
python manage.py setup_mongodb --migrate-data

# Reset complet de MongoDB
python manage.py setup_mongodb --reset-mongodb
```

### Utilisation dans les vues

```python
from documents.services.hybrid_service import hybrid_service

def annotation_view(request, document_id):
    document = get_object_or_404(Document, id=document_id)
    
    # Récupérer l'annotation avec données MongoDB
    annotation_data = hybrid_service.get_annotation_with_mongodb_data(document)
    
    # Mettre à jour un champ
    if request.method == 'POST':
        field_name = request.POST.get('field_name')
        new_value = request.POST.get('value')
        
        success = hybrid_service.update_annotation_field(
            document, field_name, new_value, request.user
        )
        
    return render(request, 'annotation.html', {
        'document': document,
        'annotation': annotation_data
    })
```

## 📈 Statistiques et monitoring

### Statistiques combinées
```python
from documents.services.hybrid_service import hybrid_service

stats = hybrid_service.get_combined_statistics()
print(f"Documents: {stats['total_documents']}")
print(f"Annotations MongoDB: {stats['total_annotations']}")
print(f"Status: {stats['status']}")
```

### Historique des annotations
```python
history = hybrid_service.get_annotation_history(document)
for entry in history:
    print(f"{entry['action_type']} par {entry['performed_by']} le {entry['created_at']}")
```

## 🔧 Maintenance

### Vérification de l'état
```python
# Test complet de l'intégration
python test_mongodb_integration.py
```

### Sauvegarde
- **Django** : Sauvegarde SQLite habituelle
- **MongoDB** : `mongodump --db data_structure_db`

### Restauration
- **Django** : Restauration SQLite habituelle  
- **MongoDB** : `mongorestore --db data_structure_db`

## 🚨 Gestion des erreurs

### Mode dégradé
Si MongoDB est indisponible, le système fonctionne en mode dégradé :
- Les opérations continuent avec Django ORM uniquement
- Les nouvelles annotations sont stockées dans Django
- Synchronisation automatique lors du retour de MongoDB

### Logs
Les erreurs MongoDB sont loggées dans `logs/django.log` :
```
[INFO] Connexion MongoDB établie avec succès
[WARNING] MongoDB indisponible - mode dégradé
[ERROR] Erreur synchronisation MongoDB: ...
```

## 📝 Migration des données existantes

Vos données existantes ont été automatiquement migrées :
- ✅ **18 documents** migrés
- ✅ **6 annotations** migrées  
- ✅ **Métadonnées** préservées
- ✅ **Historique** conservé

## 🎯 Prochaines étapes

1. **Tester** l'interface utilisateur avec les nouvelles données MongoDB
2. **Optimiser** les requêtes selon vos besoins
3. **Configurer** la sauvegarde MongoDB en production
4. **Monitorer** les performances

## 📞 Support

En cas de problème :
1. Vérifier les logs : `logs/django.log`
2. Tester la connexion : `python manage.py setup_mongodb --test-connection`
3. Exécuter les tests : `python test_mongodb_integration.py`

---

🎉 **Félicitations !** Votre système utilise maintenant MongoDB pour stocker efficacement vos données JSON d'annotations tout en conservant la compatibilité avec votre code Django existant.