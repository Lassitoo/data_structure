# documents/services/ai_config.py
"""
Configuration centralisée pour les services d'IA
"""

# Configuration Ollama - API directe (plus rapide que ChatOllama)
OLLAMA_CONFIG = {
    'base_url': 'http://localhost:11434',
    'model': 'llama3.1:8b-instruct-q4_K_M',
    'timeout': 300,  # 5 minutes
    'max_retries': 3,
}

# Configuration du modèle pour différents types de documents
# Optimisé pour llama3.1:8b-instruct-q4_K_M (modèle quantifié)
MODEL_CONFIGS = {
    'default': {
        'num_ctx': 131072,        # 128k tokens (Llama 3.1 supporte jusqu'à 128k)
        'temperature': 0.2,       # Plus bas pour plus de précision avec le modèle quantifié
        'top_p': 0.9,            # Réduit pour améliorer la cohérence
        'num_predict': 4096,
        'repeat_penalty': 1.1,
        'top_k': 40,             # Ajouté pour le modèle quantifié
    },
    'large_docs': {
        'num_ctx': 131072,        # Limité à 128k pour Llama 3.1
        'temperature': 0.1,       # Très bas pour les gros documents
        'top_p': 0.85,
        'num_predict': 6144,
        'repeat_penalty': 1.15,
        'top_k': 30,
    },
    'fast': {
        'num_ctx': 32768,         # 32k tokens (plus rapide)
        'temperature': 0.1,       # Très déterministe pour la rapidité
        'top_p': 0.8,
        'num_predict': 2048,
        'repeat_penalty': 1.0,
        'top_k': 20,
    }
}

# Seuils de gestion des documents
DOCUMENT_THRESHOLDS = {
    'small_doc': 50000,           # < 50k chars
    'medium_doc': 100000,         # 50k-100k chars
    'large_doc': 200000,          # 100k-200k chars
    'xlarge_doc': 500000,         # > 500k chars
    'max_allowed': 2000000,       # 2M chars max
}

# Configuration de performance
PERFORMANCE_CONFIG = {
    'chunk_overlap': 2000,
    'sample_ratio_large': 0.4,
    'fallback_threshold': 10,
    'memory_limit_gb': 16,
}

# Prompts optimisés pour Llama 3.1 Instruct
PROMPTS = {
    'document_type': """Tu es un expert en classification de documents. Analyse ce document et détermine son type principal.

MÉTADONNÉES:
- Fichier: {filename}
- Taille: {file_size} bytes
- MIME: {mime_type}

CONTENU:
{content}

Analyse le contenu et réponds avec UN SEUL MOT parmi:
CONTRAT, FACTURE, RAPPORT, EMAIL, LETTRE, FORMULAIRE, PRESENTATION, AUTRE

TYPE:""",

    'schema_generation': """Tu es un expert en annotation de documents. Analyse ce document et crée un schéma d'annotation JSON complet.

MÉTADONNÉES:
{metadata}

CONTENU À ANALYSER:
{content}

INSTRUCTIONS:
1. Analyse TOUT le contenu fourni
2. Identifie les informations clés selon le type: {document_type}
3. Crée des champs d'annotation pertinents et utilisables
4. IMPORTANT: Pour les champs "choice" et "multiple_choice", TOUJOURS inclure une liste "choices"

TYPES DISPONIBLES:
- text: texte libre
- number: valeur numérique  
- date: date (YYYY-MM-DD)
- boolean: true/false
- choice: sélection unique (OBLIGATOIRE: inclure "choices")
- multiple_choice: sélection multiple (OBLIGATOIRE: inclure "choices")
- entity: entités nommées
- classification: catégorie

FORMAT JSON REQUIS:
{{
  "name": "schema_descriptif",
  "description": "Description complète du schéma",
  "fields": [
    {{
      "name": "nom_champ_snake_case",
      "label": "Label français",
      "type": "type_valide",
      "description": "Description détaillée",
      "required": true/false,
      "choices": ["option1", "option2", "option3"]
    }}
  ]
}}

EXIGENCES:
- 6-12 champs selon la richesse du contenu
- Minimum 3 champs obligatoires
- Labels en français claire
- Choix pertinents basés sur le contenu analysé

SCHÉMA JSON:""",

    'pre_annotations': """Tu es un expert en annotation de documents. Analyse ce document et génère des annotations selon le schéma fourni.

CONTENU DU DOCUMENT:
{content}

SCHÉMA D'ANNOTATION:
{schema}

INSTRUCTIONS:
1. Analyse le contenu du document
2. Extrais les informations selon chaque champ du schéma
3. Génère des annotations précises et complètes
4. Pour les champs de type "choice", sélectionne la meilleure option
5. Pour les champs "multiple_choice", sélectionne toutes les options pertinentes

FORMAT JSON REQUIS:
{annotations_json}

ANNOTATIONS:"""
}

# Fallbacks pour les cas d'erreur
FALLBACKS = {
    'document_types': {
        'CONTRAT': ['contrat', 'signataire', 'partie', 'engagement'],
        'FACTURE': ['facture', 'montant', 'tva', 'paiement'],
        'RAPPORT': ['rapport', 'conclusion', 'recommandation', 'analyse'],
        'EMAIL': ['email', 'mail', 'objet', 'expéditeur'],
        'LETTRE': ['lettre', 'correspondance', 'destinataire'],
        'FORMULAIRE': ['formulaire', 'champ', 'case', 'signature'],
        'PRESENTATION': ['présentation', 'slide', 'diapositive'],
    },
    'default_schema': {
        "name": "schema_generique",
        "description": "Schéma générique pour document",
        "fields": [
            {
                "name": "titre",
                "label": "Titre",
                "type": "text",
                "description": "Titre du document",
                "required": True
            },
            {
                "name": "type_document",
                "label": "Type de document",
                "type": "choice",
                "description": "Catégorie du document",
                "required": True,
                "choices": ["Rapport", "Contrat", "Facture", "Procédure", "Autre"]
            },
            {
                "name": "contenu_principal",
                "label": "Contenu principal",
                "type": "text",
                "description": "Résumé du contenu",
                "required": False
            }
        ]
    }
}

