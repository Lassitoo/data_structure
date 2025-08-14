# documents/services/llama_service.py
import json
import logging
from typing import Dict, Any
import requests
from django.conf import settings

# ChatOllama (compat imports selon version LangChain)
try:
    from langchain_ollama import ChatOllama
except Exception:  # ancien paquet
    try:
        from langchain_community.chat_models import ChatOllama  # type: ignore
    except Exception:
        ChatOllama = None  # sera géré proprement plus bas

try:
    from langchain_core.messages import SystemMessage, HumanMessage
except Exception:
    # Fallback minimal si langchain_core indispo
    class _Msg:
        def __init__(self, content: str): self.content = content


    class SystemMessage(_Msg):
        pass


    class HumanMessage(_Msg):
        pass

logger = logging.getLogger("documents")


class LlamaService:
    """Service pour l'intégration avec llama3.1:8b-instruct-q4_K_M via Ollama avec gestion des gros documents."""

    def __init__(self):
        self.llm = None
        self.direct_api_mode = False
        self._initialize_model()

    # ---------- Initialisation / Santé Ollama ----------
    def _ping(self, base_url: str):
        try:
            r = requests.get(f"{base_url}/api/tags", timeout=5)
            r.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Ollama n'est pas accessible sur {base_url}. Détails: {e}")
            return False

    def _initialize_model(self):
        """
        Initialise le modèle llama3.1:8b-instruct-q4_K_M avec double stratégie:
        1. ChatOllama (LangChain) - recommandé
        2. API directe Ollama - fallback
        """
        try:
            cfg = getattr(settings, "LLAMA_CONFIG", {}) or {}
            base_url = cfg.get("base_url", "http://localhost:11434")
            model = cfg.get("model", "llama3.1:8b-instruct-q4_K_M")
            temperature = cfg.get("temperature", 0.3)
            top_p = cfg.get("top_p", 0.95)
            num_ctx = cfg.get("num_ctx", 32768)

            # Vérifier la santé d'Ollama
            if not self._ping(base_url):
                logger.error("Ollama non accessible - modèle non initialisé")
                self.llm = None
                return

            # Stratégie 1: Essayer ChatOllama (LangChain)
            if ChatOllama is not None:
                try:
                    self.llm = ChatOllama(
                        base_url=base_url,
                        model=model,
                        temperature=temperature,
                        top_p=top_p,
                        num_ctx=num_ctx,
                    )
                    self.direct_api_mode = False
                    logger.info(f"ChatOllama initialisé: model={model}, num_ctx={num_ctx}")
                    return
                except Exception as init_error:
                    logger.warning(f"ChatOllama échoué: {init_error}, basculement vers API directe")

            # Stratégie 2: Mode API directe (fallback)
            self.direct_api_mode = True
            self.base_url = base_url
            self.model_config = {
                'model': model,
                'temperature': temperature,
                'num_ctx': num_ctx,
                'top_p': top_p
            }
            logger.info(f"Mode API directe activé: model={model}, num_ctx={num_ctx}")

        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation: {e}")
            self.llm = None
            self.direct_api_mode = False

    def call_local_mistral(self, prompt: str, max_tokens: int = 2048) -> str:
        """
        Appel direct à l'API Ollama local (votre fonction adaptée pour gros documents)
        """
        try:
            if not hasattr(self, 'base_url') or not hasattr(self, 'model_config'):
                return self._fallback_response("Configuration API directe manquante")

            url = f"{self.base_url}/api/generate"

            # Configuration adaptée pour gros documents
            payload = {
                "model": self.model_config['model'],
                "prompt": prompt,
                "temperature": self.model_config['temperature'],
                "num_ctx": self.model_config['num_ctx'],
                "top_p": self.model_config.get('top_p', 0.95),
                "num_predict": min(max_tokens, 4096),  # Limiter les tokens de sortie
                "stream": False
            }

            logger.info(f"Appel API directe: {len(prompt)} caractères, model={payload['model']}")

            response = requests.post(url, json=payload, timeout=300)  # 5 min timeout

            if response.status_code == 200:
                data = response.json()
                content = data.get("response", "").strip()
                logger.info(f"Réponse API directe: {len(content)} caractères")
                return content
            else:
                logger.error(f"Erreur API Ollama: {response.status_code} - {response.text}")
                return self._fallback_response(f"Erreur Ollama API: {response.status_code}")

        except requests.exceptions.Timeout:
            logger.error("Timeout lors de l'appel à l'API Ollama")
            return self._fallback_response("Timeout API Ollama")
        except Exception as e:
            logger.error(f"Erreur appel API directe: {e}")
            return self._fallback_response(f"Erreur API: {e}")

    def _generate_response(self, prompt: str, max_tokens: int = 2048, system_prompt: str = None) -> str:
        """
        Génère une réponse avec gestion intelligente selon le mode (LangChain ou API directe)
        """
        # Gestion des gros documents - limitation intelligente
        original_length = len(prompt)
        if original_length > 200000:  # > 200k chars
            logger.warning(f"Document très volumineux ({original_length} chars), échantillonnage appliqué")
            prompt = self._create_intelligent_sample(prompt)
            logger.info(f"Échantillonnage: {original_length} -> {len(prompt)} caractères")

        try:
            if self.direct_api_mode:
                # Mode API directe
                return self.call_local_mistral(prompt, max_tokens)

            elif self.llm is not None:
                # Mode LangChain
                return self._generate_with_langchain(prompt, max_tokens, system_prompt)

            else:
                return self._fallback_response("Aucun modèle disponible")

        except Exception as e:
            logger.error(f"Erreur génération réponse: {e}")
            return self._fallback_response(f"Erreur génération: {e}")

    def _generate_with_langchain(self, prompt: str, max_tokens: int, system_prompt: str = None) -> str:
        """Génération via LangChain ChatOllama"""
        try:
            wants_json = "JSON" in prompt.upper()
            call_model = self.llm

            if wants_json:
                try:
                    call_model = self.llm.bind(format="json")
                except Exception:
                    logger.debug("Format JSON non supporté via bind()")

            sys_msg = system_prompt or """Tu es un expert analyste de documents spécialisé dans l'analyse de documents volumineux en français. 
            Si on te demande du JSON, renvoie uniquement du JSON valide.
            Tu traites des documents de toutes tailles avec attention aux détails."""

            messages = [
                SystemMessage(content=sys_msg),
                HumanMessage(content=prompt),
            ]

            logger.info(f"Envoi LangChain: {len(prompt)} caractères")
            res = call_model.invoke(messages)
            content = (getattr(res, "content", None) or "").strip()
            logger.info(f"Réponse LangChain: {len(content)} caractères")

            return content

        except Exception as e:
            logger.error(f"Erreur LangChain: {e}")
            return self._fallback_response(f"Erreur LangChain: {e}")

    def _create_intelligent_sample(self, content: str) -> str:
        """
        Crée un échantillon intelligent pour les très gros documents
        Optimisé pour llama3.1:8b-instruct-q4_K_M avec contexte étendu
        """
        try:
            if len(content) <= 150000:  # < 150k chars, garde tout
                return content

            # Stratégie d'échantillonnage intelligent
            target_size = 120000  # 120k chars pour rester dans les limites

            # 40% début + 30% milieu + 30% fin
            begin_size = int(target_size * 0.4)  # 48k
            middle_size = int(target_size * 0.3)  # 36k
            end_size = int(target_size * 0.3)  # 36k

            beginning = content[:begin_size]

            # Milieu représentatif
            middle_start = len(content) // 2 - middle_size // 2
            middle = content[middle_start:middle_start + middle_size]

            # Fin du document
            end = content[-end_size:] if len(content) > end_size else ""

            # Assembler l'échantillon avec marqueurs
            sample = f"""=== DÉBUT DU DOCUMENT ===
{beginning}

=== SECTION CENTRALE REPRÉSENTATIVE ===
{middle}

=== FIN DU DOCUMENT ===
{end}

[DOCUMENT ORIGINAL: {len(content)} caractères - ÉCHANTILLON: {len(beginning + middle + end)} caractères]"""

            logger.info(f"Échantillon intelligent créé: {len(sample)} chars (original: {len(content)})")
            return sample

        except Exception as e:
            logger.error(f"Erreur création échantillon: {e}")
            # Fallback simple : premiers 100k chars
            return content[:100000] + "\n\n[DOCUMENT TRONQUÉ]"

    # ---------- Fonctions métier adaptées ----------
    def analyze_document_type(self, metadata: Dict, content: str = "") -> str:
        """Analyse le type de document avec llama3.1:8b-instruct-q4_K_M et gestion des gros volumes"""
        try:
            content_length = len(content)
            logger.info(f"Analyse type document: {content_length} caractères avec llama3.1:8b-instruct-q4_K_M")

            # Gestion intelligente selon la taille
            if content_length > 100000:
                # Document volumineux - utiliser échantillon + métadonnées
                sample = self._create_document_type_sample(content, metadata)
                prompt = self._build_document_analysis_prompt(metadata, sample, is_sample=True)
            else:
                # Document normal
                prompt = self._build_document_analysis_prompt(metadata, content)

            response = self._generate_response(prompt, max_tokens=100)

            # Validation de la réponse
            if not response or len(response.strip()) < 3 or response.startswith("ERREUR:"):
                logger.warning(f"Réponse insuffisante ({len(response)} chars), fallback")
                return self._analyze_document_type_fallback(metadata, content)

            # Extraction du type
            doc_type = response.strip().upper()
            for word in doc_type.split():
                if word in ['CONTRAT', 'FACTURE', 'RAPPORT', 'EMAIL', 'LETTRE', 'FORMULAIRE', 'PRESENTATION']:
                    logger.info(f"Type détecté: {word}")
                    return word

            logger.warning(f"Type non reconnu: '{doc_type}', fallback")
            return self._analyze_document_type_fallback(metadata, content)

        except Exception as e:
            logger.error(f"Erreur analyse type: {e}")
            return self._analyze_document_type_fallback(metadata, content)

    def _create_document_type_sample(self, content: str, metadata: Dict) -> str:
        """Crée un échantillon optimisé pour la détection de type"""
        try:
            # Pour la détection de type, on a besoin des éléments clés
            sample_size = 20000  # 20k chars suffisent pour le type

            # Début (souvent titre, en-tête)
            beginning = content[:sample_size // 2]

            # Recherche de mots-clés dans le document
            keywords_sample = ""
            content_lower = content.lower()

            # Chercher des sections importantes
            for keyword in ['conclusion', 'résumé', 'summary', 'objet', 'titre', 'subject']:
                idx = content_lower.find(keyword)
                if idx != -1:
                    keywords_sample += content[max(0, idx - 100):idx + 500] + "\n"
                    if len(keywords_sample) > 2000:
                        break

            # Fin du document
            end = content[-(sample_size // 4):] if len(content) > sample_size // 4 else ""

            sample = f"""DÉBUT:
{beginning}

ÉLÉMENTS CLÉS:
{keywords_sample}

FIN:
{end}"""

            return sample[:sample_size]

        except Exception as e:
            logger.error(f"Erreur échantillon type: {e}")
            return content[:10000]

    def generate_annotation_schema(self, document_metadata: Dict, document_content: str = "") -> Dict:
        """
        Génère un schéma d'annotation avec llama3.1:8b-instruct-q4_K_M et gestion optimisée des gros documents
        """
        try:
            content_length = len(document_content)
            logger.info(f"Génération schéma avec llama3.1:8b-instruct-q4_K_M: {content_length} caractères")

            # Adaptation du contenu selon la taille pour optimiser avec llama3.2
            if content_length > 150000:
                # Très gros document - échantillonnage intelligent
                content_for_schema = self._create_schema_sample(document_content)
                logger.info(f"Échantillon pour schéma: {len(content_for_schema)} caractères")
            elif content_length > 80000:
                # Document moyen - première moitié + fin
                mid_point = len(document_content) // 2
                content_for_schema = document_content[
                                     :60000] + "\n\n[...SECTION INTERMÉDIAIRE...]\n\n" + document_content[-20000:]
            else:
                # Document normal
                content_for_schema = document_content

            prompt = self._build_schema_prompt(document_metadata, content_for_schema)
            response = self._generate_response(prompt, max_tokens=3000)  # Plus de tokens pour schémas complexes

            if response.startswith("ERREUR:"):
                logger.warning(f"Génération IA échoué: {response}")
                return self._fallback_schema(document_metadata)

            schema = self._parse_schema_response(response)
            # Validation et correction des choix manquants
            schema = self._validate_and_fix_schema(schema)

            logger.info("Schéma généré avec llama3.1:8b-instruct-q4_K_M")
            return schema

        except Exception as e:
            logger.error(f"Erreur génération schéma: {e}")
            return self._fallback_schema(document_metadata)

    def _create_schema_sample(self, content: str) -> str:
        """Crée un échantillon optimisé pour la génération de schéma"""
        try:
            # Pour le schéma, on veut capturer la diversité du contenu
            target_size = 100000  # 100k chars optimaux pour llama3.2

            # 50% début + 25% milieu + 25% fin
            begin_size = target_size // 2
            middle_size = target_size // 4
            end_size = target_size // 4

            beginning = content[:begin_size]

            # Milieu représentatif
            middle_start = len(content) // 2 - middle_size // 2
            middle = content[middle_start:middle_start + middle_size]

            # Fin
            end = content[-end_size:] if len(content) > end_size else ""

            sample = f"""{beginning}

--- SECTION REPRÉSENTATIVE DU MILIEU ---
{middle}

--- FIN DU DOCUMENT ---
{end}"""

            return sample

        except Exception as e:
            logger.error(f"Erreur échantillon schéma: {e}")
            return content[:80000]

    def _build_document_analysis_prompt(self, metadata: Dict, content: str, is_sample: bool = False) -> str:
        """Prompt optimisé pour llama3.1:8b-instruct-q4_K_M"""
        sample_info = " (ÉCHANTILLON REPRÉSENTATIF)" if is_sample else ""

        prompt = f"""Tu es un expert en classification de documents. Analyse ce document{sample_info} et détermine son type principal.

MÉTADONNÉES:
- Fichier: {metadata.get('filename', 'N/A')}
- Taille: {metadata.get('file_size', 'N/A')} bytes
- MIME: {metadata.get('mime_type', 'N/A')}
- Pages: {metadata.get('num_pages', 'N/A')}

CONTENU{sample_info}:
{content}

Analyse le contenu et réponds avec UN SEUL MOT parmi:
CONTRAT, FACTURE, RAPPORT, EMAIL, LETTRE, FORMULAIRE, PRESENTATION, AUTRE

TYPE:"""
        return prompt

    # ---------- Validation et parsing améliorés ----------
    def _validate_and_fix_schema(self, schema: Dict) -> Dict:
        """Valide et corrige automatiquement les schémas pour éviter les erreurs"""
        try:
            if not isinstance(schema, dict) or 'fields' not in schema:
                return self._fallback_schema({})

            fields = schema.get('fields', [])
            fixed_fields = []

            for field in fields:
                if not isinstance(field, dict):
                    continue

                field_copy = field.copy()
                field_type = field.get('type', '')
                field_name = field.get('name', '')

                # Correction automatique pour choice/multiple_choice
                if field_type in ['choice', 'multiple_choice']:
                    choices = field.get('choices', [])
                    if not choices or not isinstance(choices, list) or len(choices) == 0:
                        # Générer des choix intelligents selon le nom du champ
                        default_choices = self._generate_smart_choices(field_name, field_type)
                        field_copy['choices'] = default_choices
                        logger.info(f"Choix auto-générés pour '{field_name}': {default_choices}")

                # Nettoyer les propriétés non nécessaires
                elif 'choices' in field_copy:
                    del field_copy['choices']

                fixed_fields.append(field_copy)

            schema['fields'] = fixed_fields
            return schema

        except Exception as e:
            logger.error(f"Erreur validation schéma: {e}")
            return schema

    def _generate_smart_choices(self, field_name: str, field_type: str) -> list:
        """Génère des choix intelligents selon le nom du champ et le contexte"""
        field_lower = field_name.lower()

        # Dictionnaire des choix contextuels
        smart_choices = {
            'etablissement': ["Hôpital universitaire", "Centre hospitalier", "Clinique privée", "Centre spécialisé",
                              "Autre"],
            'hopital': ["CHU", "CHR", "Hôpital local", "Clinique", "Autre"],
            'statut': ["Actif", "Inactif", "En cours", "Terminé", "Suspendu"],
            'priorite': ["Très haute", "Haute", "Moyenne", "Basse"],
            'type': ["Type A", "Type B", "Type C", "Type D", "Autre"],
            'niveau': ["Niveau 1", "Niveau 2", "Niveau 3", "Niveau 4"],
            'categorie': ["Urgent", "Important", "Normal", "Informatif"],
            'service': ["Médical", "Administratif", "Technique", "Qualité", "Autre"],
            'validation': ["Validé", "En cours", "Rejeté", "À réviser"],
            'conformite': ["Conforme", "Non conforme", "Partiellement conforme", "À vérifier"],
            'risque': ["Faible", "Modéré", "Élevé", "Critique"],
            'secteur': ["Public", "Privé", "Mixte", "Autre"]
        }

        # Rechercher une correspondance
        for pattern, choices in smart_choices.items():
            if pattern in field_lower:
                return choices

        # Choix génériques par défaut
        return ["Option 1", "Option 2", "Option 3", "Autre"]

    # ---------- Prompts optimisés pour llama3.1:8b-instruct-q4_K_M ----------
    def _build_schema_prompt(self, metadata: Dict, content: str) -> str:
        """Prompt optimisé pour llama3.1:8b-instruct-q4_K_M avec instructions précises"""
        document_type = metadata.get('document_type', 'UNKNOWN')

        prompt = f"""Tu es un expert en annotation de documents. Analyse ce document et crée un schéma d'annotation JSON complet et précis.

MÉTADONNÉES:
{json.dumps(metadata, indent=2, ensure_ascii=False)}

CONTENU À ANALYSER:
{content}

INSTRUCTIONS PRÉCISES:
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
      "choices": ["option1", "option2", "option3"] // OBLIGATOIRE pour choice/multiple_choice
    }}
  ]
}}

EXIGENCES:
- 6-12 champs selon la richesse du contenu
- Minimum 3 champs obligatoires
- Labels en français claire
- Choix pertinents basés sur le contenu analysé

SCHÉMA JSON:"""
        return prompt

    # ---------- Fallbacks et utilitaires ----------
    def _fallback_response(self, error_msg: str) -> str:
        return f"ERREUR: {error_msg}"

    def _analyze_document_type_fallback(self, metadata: Dict, content: str = "") -> str:
        """Fallback basique pour la détection de type"""
        try:
            filename = (metadata.get('filename', '') or '').lower()
            content_lower = content.lower()[:5000]  # Premiers 5k chars

            # Détection par nom de fichier
            if any(word in filename for word in ['contrat', 'contract']):
                return 'CONTRAT'
            elif any(word in filename for word in ['facture', 'invoice', 'bill']):
                return 'FACTURE'
            elif any(word in filename for word in ['rapport', 'report', 'guideline']):
                return 'RAPPORT'
            elif any(word in filename for word in ['email', 'mail']):
                return 'EMAIL'

            # Détection par contenu
            elif any(word in content_lower for word in ['contrat', 'signataire', 'partie']):
                return 'CONTRAT'
            elif any(word in content_lower for word in ['facture', 'montant', 'tva']):
                return 'FACTURE'
            elif any(word in content_lower for word in ['rapport', 'conclusion', 'recommandation']):
                return 'RAPPORT'
            else:
                return 'AUTRE'

        except Exception:
            return 'AUTRE'

    def _fallback_schema(self, metadata: Dict) -> Dict:
        """Schéma de fallback adapté au type détecté"""
        document_type = (metadata or {}).get('document_type', 'AUTRE')

        if document_type == 'RAPPORT':
            return {
                "name": "schema_rapport_fallback",
                "description": "Schéma de base pour rapport",
                "fields": [
                    {
                        "name": "titre_document",
                        "label": "Titre du document",
                        "type": "text",
                        "description": "Titre principal du rapport",
                        "required": True
                    },
                    {
                        "name": "type_rapport",
                        "label": "Type de rapport",
                        "type": "choice",
                        "description": "Catégorie du rapport",
                        "required": True,
                        "choices": ["Technique", "Réglementaire", "Guideline", "Procédure", "Autre"]
                    },
                    {
                        "name": "resume",
                        "label": "Résumé exécutif",
                        "type": "text",
                        "description": "Résumé des points principaux",
                        "required": False
                    },
                    {
                        "name": "conclusions",
                        "label": "Conclusions principales",
                        "type": "text",
                        "description": "Conclusions et recommandations",
                        "required": False
                    },
                    {
                        "name": "priorite",
                        "label": "Niveau de priorité",
                        "type": "choice",
                        "description": "Importance du document",
                        "required": False,
                        "choices": ["Critique", "Important", "Normal", "Informatif"]
                    },
                    {
                        "name": "domaines",
                        "label": "Domaines concernés",
                        "type": "multiple_choice",
                        "description": "Secteurs impactés",
                        "required": False,
                        "choices": ["Médical", "Pharmaceutique", "Réglementaire", "Qualité", "Autre"]
                    }
                ]
            }
        else:
            # Schéma générique
            return {
                "name": f"schema_{document_type.lower()}_fallback",
                "description": f"Schéma de base pour {document_type}",
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
                        "description": "Catégorie",
                        "required": True,
                        "choices": ["Rapport", "Contrat", "Facture", "Procédure", "Autre"]
                    },
                    {
                        "name": "contenu_principal",
                        "label": "Contenu principal",
                        "type": "text",
                        "description": "Résumé du contenu",
                        "required": False
                    },
                    {
                        "name": "statut",
                        "label": "Statut",
                        "type": "choice",
                        "description": "État du document",
                        "required": False,
                        "choices": ["Actif", "Archivé", "En révision", "Brouillon"]
                    }
                ]
            }

    def _parse_schema_response(self, response: str) -> Dict:
        try:
            response = (response or "").strip()
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            if start_idx != -1 and end_idx != -1:
                json_str = response[start_idx:end_idx]
                schema = json.loads(json_str)
                if isinstance(schema, dict) and 'fields' in schema:
                    return schema
            return self._fallback_schema({})
        except json.JSONDecodeError as e:
            logger.error(f"Erreur parsing JSON: {e}")
            return self._fallback_schema({})

    def _parse_annotation_response(self, response: str, schema: Dict) -> Dict:
        try:
            response = (response or "").strip()
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            if start_idx != -1 and end_idx != -1:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Erreur parsing annotations: {e}")
            return {}

    def _fallback_annotations(self, schema: Dict) -> Dict:
        """Annotations de fallback"""
        annotations = {}
        for field in schema.get('fields', []):
            name = field.get('name')
            ftype = field.get('type')
            if name:
                if ftype == 'number':
                    annotations[name] = 0
                elif ftype == 'boolean':
                    annotations[name] = None
                else:
                    annotations[name] = ""
        return annotations