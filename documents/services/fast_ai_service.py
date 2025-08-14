# documents/services/fast_ai_service.py
"""
Service IA ultra-rapide utilisant des appels HTTP directs à Ollama
Remplace ChatOllama pour de meilleures performances
"""

import json
import logging
import requests
from typing import Dict, Any, Optional
from .ai_config import OLLAMA_CONFIG, MODEL_CONFIGS, PROMPTS, FALLBACKS, DOCUMENT_THRESHOLDS

logger = logging.getLogger('documents')


class FastAIService:
    """
    Service IA ultra-rapide avec appels HTTP directs à Ollama
    Plus rapide que ChatOllama et plus simple à maintenir
    """

    def __init__(self):
        self.base_url = OLLAMA_CONFIG['base_url']
        self.model = OLLAMA_CONFIG['model']
        self.timeout = OLLAMA_CONFIG['timeout']
        self.max_retries = OLLAMA_CONFIG['max_retries']
        
        # Test de connexion au démarrage
        self._test_connection()

    def _test_connection(self) -> bool:
        """Teste la connexion à Ollama"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                logger.info(f"[OK] Connexion Ollama OK - Modele: {self.model}")
                return True
            else:
                logger.error(f"[ERROR] Erreur connexion Ollama: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"[ERROR] Impossible de se connecter a Ollama: {e}")
            return False

    def _call_ollama_api(self, prompt: str, config_type: str = 'default') -> str:
        """
        Appel direct et ultra-rapide à l'API Ollama
        Plus rapide que ChatOllama car pas de surcharge LangChain
        """
        try:
            # Configuration du modèle selon le type
            model_config = MODEL_CONFIGS.get(config_type, MODEL_CONFIGS['default'])
            
            # Préparation du payload
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,  # Pas de streaming pour plus de rapidité
                **model_config
            }

            # Appel API avec retry
            for attempt in range(self.max_retries):
                try:
                    logger.info(f"[API] Appel API Ollama (tentative {attempt + 1}) - {len(prompt)} chars")
                    
                    response = requests.post(
                        f"{self.base_url}/api/generate",
                        json=payload,
                        timeout=self.timeout
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        content = data.get("response", "").strip()
                        
                        if content and len(content) > 10:  # Réponse valide
                            logger.info(f"Reponse API: {len(content)} chars")
                            return content
                        else:
                            logger.warning(f"[WARNING] Reponse vide ou trop courte: {len(content)} chars")
                            
                    else:
                        logger.error(f"[ERROR] Erreur API: {response.status_code} - {response.text}")
                        
                except requests.exceptions.Timeout:
                    logger.warning(f"[TIMEOUT] Timeout tentative {attempt + 1}")
                    if attempt == self.max_retries - 1:
                        raise
                except Exception as e:
                    logger.error(f"[ERROR] Erreur tentative {attempt + 1}: {e}")
                    if attempt == self.max_retries - 1:
                        raise

            return self._fallback_response("Toutes les tentatives ont échoué")

        except Exception as e:
            logger.error(f"[ERROR] Erreur critique API Ollama: {e}")
            return self._fallback_response(f"Erreur API: {e}")

    def analyze_document_type(self, metadata: Dict, content: str = "") -> str:
        """
        Analyse rapide du type de document
        Optimisé pour la vitesse avec échantillonnage intelligent
        """
        try:
            content_length = len(content)
            logger.info(f"[ANALYZE] Analyse type document: {content_length} chars")

            # Échantillonnage intelligent pour les gros documents
            if content_length > DOCUMENT_THRESHOLDS['large_doc']:
                content = self._create_smart_sample(content, target_size=15000)
                logger.info(f"[SAMPLE] Echantillon cree: {len(content)} chars")

            # Construction du prompt
            prompt = PROMPTS['document_type'].format(
                filename=metadata.get('filename', 'N/A'),
                file_size=metadata.get('file_size', 'N/A'),
                mime_type=metadata.get('mime_type', 'N/A'),
                content=content[:10000]  # Limite pour rapidité
            )

            # Appel API avec config rapide
            response = self._call_ollama_api(prompt, config_type='fast')

            # Extraction du type
            doc_type = self._extract_document_type(response)
            logger.info(f"[RESULT] Type detecte: {doc_type}")
            return doc_type

        except Exception as e:
            logger.error(f"[ERROR] Erreur analyse type: {e}")
            return self._analyze_type_fallback(metadata, content)

    def generate_annotation_schema(self, document_metadata: Dict, document_content: str = "") -> Dict:
        """
        Génération rapide de schéma d'annotation
        Optimisé pour les gros documents avec échantillonnage
        """
        try:
            content_length = len(document_content)
            logger.info(f"[SCHEMA] Generation schema: {content_length} chars")

            # Échantillonnage intelligent pour les gros documents
            if content_length > DOCUMENT_THRESHOLDS['medium_doc']:
                content_for_schema = self._create_schema_sample(document_content)
                logger.info(f"[SAMPLE] Echantillon schema: {len(content_for_schema)} chars")
            else:
                content_for_schema = document_content

            # Construction du prompt
            prompt = PROMPTS['schema_generation'].format(
                metadata=json.dumps(document_metadata, indent=2, ensure_ascii=False),
                content=content_for_schema[:80000],  # Limite pour rapidité
                document_type=document_metadata.get('document_type', 'UNKNOWN')
            )

            # Appel API
            response = self._call_ollama_api(prompt, config_type='default')

            # Parsing et validation
            schema = self._parse_schema_response(response)
            schema = self._validate_and_fix_schema(schema)

            logger.info(f"Schema genere: {len(schema.get('fields', []))} champs")
            return schema

        except Exception as e:
            logger.error(f"[ERROR] Erreur generation schema: {e}")
            return FALLBACKS['default_schema']

    def generate_pre_annotations(self, content: str, schema: Dict) -> Dict:
        """
        Génération rapide de pré-annotations
        Optimisé pour la vitesse
        """
        try:
            logger.info(f"[ANNOTATIONS] Generation pre-annotations")

            # Échantillonnage pour les gros documents
            if len(content) > DOCUMENT_THRESHOLDS['medium_doc']:
                content = self._create_smart_sample(content, target_size=20000)

            # Préparation du template JSON pour les annotations
            annotations_template = {}
            for field in schema.get('fields', []):
                field_name = field.get('name')
                field_type = field.get('type')
                if field_name:
                    if field_type == 'number':
                        annotations_template[field_name] = 0
                    elif field_type == 'boolean':
                        annotations_template[field_name] = None
                    else:
                        annotations_template[field_name] = ""

            # Construction du prompt
            prompt = PROMPTS['pre_annotations'].format(
                content=content[:50000],  # Limite pour rapidité
                schema=json.dumps(schema, indent=2, ensure_ascii=False),
                annotations_json=json.dumps(annotations_template, indent=2, ensure_ascii=False)
            )

            # Appel API
            response = self._call_ollama_api(prompt, config_type='default')

            # Parsing des annotations
            annotations = self._parse_annotation_response(response)
            
            # Validation et nettoyage
            annotations = self._validate_annotations(annotations, schema)

            logger.info(f"[SUCCESS] Pre-annotations generees: {len(annotations)} champs")
            return annotations

        except Exception as e:
            logger.error(f"[ERROR] Erreur pre-annotations: {e}")
            return self._fallback_annotations(schema)

    # ========== MÉTHODES UTILITAIRES OPTIMISÉES ==========

    def _create_smart_sample(self, content: str, target_size: int = 15000) -> str:
        """Échantillonnage intelligent ultra-rapide"""
        try:
            if len(content) <= target_size:
                return content

            # 40% début + 30% milieu + 30% fin
            begin_size = int(target_size * 0.4)
            middle_size = int(target_size * 0.3)
            end_size = int(target_size * 0.3)

            beginning = content[:begin_size]
            middle_start = len(content) // 2 - middle_size // 2
            middle = content[middle_start:middle_start + middle_size]
            end = content[-end_size:] if len(content) > end_size else ""

            sample = f"""=== DÉBUT ===
{beginning}

=== MILIEU ===
{middle}

=== FIN ===
{end}"""

            return sample

        except Exception as e:
            logger.error(f"[ERROR] Erreur echantillon: {e}")
            return content[:target_size]

    def _create_schema_sample(self, content: str) -> str:
        """Échantillonnage spécialisé pour les schémas"""
        try:
            target_size = 80000  # Plus grand pour les schémas
            
            if len(content) <= target_size:
                return content

            # 50% début + 25% milieu + 25% fin
            begin_size = target_size // 2
            middle_size = target_size // 4
            end_size = target_size // 4

            beginning = content[:begin_size]
            middle_start = len(content) // 2 - middle_size // 2
            middle = content[middle_start:middle_start + middle_size]
            end = content[-end_size:] if len(content) > end_size else ""

            sample = f"""{beginning}

--- SECTION REPRÉSENTATIVE ---
{middle}

--- FIN ---
{end}"""

            return sample

        except Exception as e:
            logger.error(f"[ERROR] Erreur echantillon schema: {e}")
            return content[:60000]

    def _extract_document_type(self, response: str) -> str:
        """Extraction rapide du type de document"""
        try:
            response = response.strip().upper()
            for word in response.split():
                if word in ['CONTRAT', 'FACTURE', 'RAPPORT', 'EMAIL', 'LETTRE', 'FORMULAIRE', 'PRESENTATION']:
                    return word
            return 'AUTRE'
        except Exception:
            return 'AUTRE'

    def _parse_schema_response(self, response: str) -> Dict:
        """Parsing rapide du JSON de schéma"""
        try:
            response = response.strip()
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = response[start_idx:end_idx]
                schema = json.loads(json_str)
                if isinstance(schema, dict) and 'fields' in schema:
                    return schema
                    
            return FALLBACKS['default_schema']
        except json.JSONDecodeError as e:
            logger.error(f"[ERROR] Erreur parsing JSON schema: {e}")
            return FALLBACKS['default_schema']

    def _parse_annotation_response(self, response: str) -> Dict:
        """Parsing rapide du JSON d'annotations"""
        try:
            response = response.strip()
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"[ERROR] Erreur parsing JSON annotations: {e}")
            return {}

    def _validate_and_fix_schema(self, schema: Dict) -> Dict:
        """Validation et correction rapide du schéma"""
        try:
            if not isinstance(schema, dict) or 'fields' not in schema:
                return FALLBACKS['default_schema']

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
                    if not choices or not isinstance(choices, list):
                        field_copy['choices'] = self._generate_smart_choices(field_name)
                elif 'choices' in field_copy:
                    del field_copy['choices']

                fixed_fields.append(field_copy)

            schema['fields'] = fixed_fields
            return schema

        except Exception as e:
            logger.error(f"[ERROR] Erreur validation schema: {e}")
            return schema

    def _validate_annotations(self, annotations: Dict, schema: Dict) -> Dict:
        """Validation rapide des annotations"""
        try:
            validated = {}
            for field in schema.get('fields', []):
                field_name = field.get('name')
                field_type = field.get('type')
                
                if field_name in annotations:
                    value = annotations[field_name]
                    
                    # Validation selon le type
                    if field_type == 'number' and not isinstance(value, (int, float)):
                        value = 0
                    elif field_type == 'boolean' and not isinstance(value, bool):
                        value = None
                    elif field_type == 'choice' and value not in field.get('choices', []):
                        value = field.get('choices', [''])[0] if field.get('choices') else ""
                    
                    validated[field_name] = value
                else:
                    # Valeur par défaut
                    if field_type == 'number':
                        validated[field_name] = 0
                    elif field_type == 'boolean':
                        validated[field_name] = None
                    else:
                        validated[field_name] = ""

            return validated

        except Exception as e:
            logger.error(f"[ERROR] Erreur validation annotations: {e}")
            return annotations

    def _generate_smart_choices(self, field_name: str) -> list:
        """Génération rapide de choix intelligents"""
        field_lower = field_name.lower()
        
        # Dictionnaire des choix contextuels
        smart_choices = {
            'etablissement': ["Hôpital universitaire", "Centre hospitalier", "Clinique privée", "Autre"],
            'statut': ["Actif", "Inactif", "En cours", "Terminé"],
            'priorite': ["Très haute", "Haute", "Moyenne", "Basse"],
            'type': ["Type A", "Type B", "Type C", "Autre"],
            'categorie': ["Urgent", "Important", "Normal", "Informatif"],
            'validation': ["Validé", "En cours", "Rejeté", "À réviser"],
        }

        for pattern, choices in smart_choices.items():
            if pattern in field_lower:
                return choices

        return ["Option 1", "Option 2", "Option 3", "Autre"]

    def _analyze_type_fallback(self, metadata: Dict, content: str = "") -> str:
        """Fallback rapide pour la détection de type"""
        try:
            filename = (metadata.get('filename', '') or '').lower()
            content_lower = content.lower()[:3000]

            # Détection par nom de fichier
            if any(word in filename for word in ['contrat', 'contract']):
                return 'CONTRAT'
            elif any(word in filename for word in ['facture', 'invoice']):
                return 'FACTURE'
            elif any(word in filename for word in ['rapport', 'report']):
                return 'RAPPORT'
            elif any(word in filename for word in ['email', 'mail']):
                return 'EMAIL'

            # Détection par contenu
            elif any(word in content_lower for word in ['contrat', 'signataire']):
                return 'CONTRAT'
            elif any(word in content_lower for word in ['facture', 'montant']):
                return 'FACTURE'
            elif any(word in content_lower for word in ['rapport', 'conclusion']):
                return 'RAPPORT'
            else:
                return 'AUTRE'

        except Exception:
            return 'AUTRE'

    def _fallback_annotations(self, schema: Dict) -> Dict:
        """Annotations de fallback rapides"""
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

    def _fallback_response(self, error_msg: str) -> str:
        """Réponse de fallback"""
        return f"ERREUR: {error_msg}"

