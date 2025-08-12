import logging
import os
from typing import Dict, Any
from django.conf import settings

logger = logging.getLogger('documents')


class DocumentProcessor:
    def extract_content(self, document) -> Dict[str, Any]:
        """Extrait le contenu et métadonnées d'un document"""
        try:
            file_path = document.file.path
            file_size = os.path.getsize(file_path)
            file_name = document.file.name

            # Détection du type de fichier
            file_extension = os.path.splitext(file_name)[1].lower()
            file_type = self._get_file_type(file_extension)

            # Extraction du contenu selon le type
            content = ""
            if file_type == 'text':
                content = self._extract_text_content(file_path)
            elif file_type == 'pdf':
                content = self._extract_pdf_content(file_path)
            elif file_type == 'docx':
                content = self._extract_docx_content(file_path)

            metadata = {
                'file_name': file_name,
                'file_size': file_size,
                'file_type': file_type,
                'file_extension': file_extension,
                'content_length': len(content)
            }

            return {
                'success': True,
                'content': content,
                'metadata': metadata
            }

        except Exception as e:
            logger.error(f"Erreur extraction contenu: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def get_document_content(self, document) -> str:
        """Récupère le contenu d'un document"""
        try:
            if hasattr(document, '_cached_content'):
                return document._cached_content

            result = self.extract_content(document)
            if result['success']:
                content = result['content']
                document._cached_content = content
                return content
            return ""

        except Exception as e:
            logger.error(f"Erreur récupération contenu: {str(e)}")
            return ""

    def _get_file_type(self, extension: str) -> str:
        """Détermine le type de fichier à partir de l'extension"""
        type_mapping = {
            '.txt': 'text',
            '.pdf': 'pdf',
            '.docx': 'docx',
            '.doc': 'doc',
            '.xlsx': 'xlsx',
            '.xls': 'xls',
            '.jpg': 'image',
            '.jpeg': 'image',
            '.png': 'image'
        }
        return type_mapping.get(extension, 'unknown')

    def _extract_text_content(self, file_path: str) -> str:
        """Extrait le contenu d'un fichier texte"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='latin-1') as f:
                return f.read()

    def _extract_pdf_content(self, file_path: str) -> str:
        """Extrait le contenu d'un PDF (nécessite PyPDF2)"""
        try:
            import PyPDF2
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                content = ""
                for page in reader.pages:
                    content += page.extract_text() + "\n"
                return content
        except ImportError:
            logger.warning("PyPDF2 non installé, impossible d'extraire le PDF")
            return "Contenu PDF non extrait (PyPDF2 requis)"
        except Exception as e:
            logger.error(f"Erreur extraction PDF: {str(e)}")
            return "Erreur extraction PDF"

    def _extract_docx_content(self, file_path: str) -> str:
        """Extrait le contenu d'un DOCX (nécessite python-docx)"""
        try:
            from docx import Document
            doc = Document(file_path)
            content = ""
            for paragraph in doc.paragraphs:
                content += paragraph.text + "\n"
            return content
        except ImportError:
            logger.warning("python-docx non installé, impossible d'extraire le DOCX")
            return "Contenu DOCX non extrait (python-docx requis)"
        except Exception as e:
            logger.error(f"Erreur extraction DOCX: {str(e)}")
            return "Erreur extraction DOCX"