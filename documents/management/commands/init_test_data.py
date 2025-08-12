from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.utils import timezone
from datetime import timedelta
import json
import random

from documents.models import (
    Document, AnnotationSchema, AnnotationField,
    Annotation, AnnotationHistory
)


class Command(BaseCommand):
    """
    Commande pour initialiser des données de test
    Usage: python manage.py init_test_data [--users N] [--documents N] [--clear]
    """

    help = 'Initialise des données de test pour le système Data Structure'

    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=int,
            default=3,
            help='Nombre d\'utilisateurs de test à créer (défaut: 3)'
        )
        parser.add_argument(
            '--documents',
            type=int,
            default=10,
            help='Nombre de documents de test à créer (défaut: 10)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Supprimer toutes les données existantes avant de créer les nouvelles'
        )
        parser.add_argument(
            '--no-ai',
            action='store_true',
            help='Ne pas générer de données IA (pour les tests sans Mistral)'
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.clear_data()

        users = self.create_users(options['users'])
        self.create_documents(users, options['documents'], not options['no_ai'])

        self.stdout.write(
            self.style.SUCCESS(
                f'Données de test créées avec succès !\n'
                f'- {options["users"]} utilisateurs\n'
                f'- {options["documents"]} documents\n'
                f'Vous pouvez maintenant tester le système.'
            )
        )

    def clear_data(self):
        """Supprime toutes les données de test"""
        self.stdout.write('Suppression des données existantes...')

        # Supprimer dans l'ordre pour éviter les contraintes de clés étrangères
        AnnotationHistory.objects.all().delete()
        Annotation.objects.all().delete()
        AnnotationField.objects.all().delete()
        AnnotationSchema.objects.all().delete()
        Document.objects.all().delete()

        # Supprimer les utilisateurs de test (sauf admin)
        User.objects.filter(is_superuser=False).delete()

        self.stdout.write(self.style.SUCCESS('Données supprimées.'))

    def create_users(self, count):
        """Crée des utilisateurs de test"""
        self.stdout.write(f'Création de {count} utilisateurs...')

        users = []
        user_data = [
            {'username': 'annotateur1', 'email': 'annotateur1@example.com', 'first_name': 'Alice',
             'last_name': 'Dupont'},
            {'username': 'annotateur2', 'email': 'annotateur2@example.com', 'first_name': 'Bob', 'last_name': 'Martin'},
            {'username': 'validateur1', 'email': 'validateur1@example.com', 'first_name': 'Claire',
             'last_name': 'Bernard'},
            {'username': 'expert1', 'email': 'expert1@example.com', 'first_name': 'David', 'last_name': 'Moreau'},
            {'username': 'admin_test', 'email': 'admin@example.com', 'first_name': 'Emma', 'last_name': 'Admin'},
        ]

        for i in range(min(count, len(user_data))):
            data = user_data[i]
            user, created = User.objects.get_or_create(
                username=data['username'],
                defaults={
                    'email': data['email'],
                    'first_name': data['first_name'],
                    'last_name': data['last_name'],
                    'is_staff': data['username'] == 'admin_test',
                }
            )
            if created:
                user.set_password('testpass123')
                user.save()
                self.stdout.write(f'  ✓ Utilisateur créé: {user.username}')
            else:
                self.stdout.write(f'  → Utilisateur existant: {user.username}')

            users.append(user)

        return users

    def create_documents(self, users, count, with_ai=True):
        """Crée des documents de test avec leurs annotations"""
        self.stdout.write(f'Création de {count} documents...')

        document_templates = [
            {
                'title': 'Contrat de travail - {name}',
                'description': 'Contrat de travail à durée indéterminée',
                'file_type': 'pdf',
                'content': 'Contrat de travail entre XYZ Corp et {name}...',
                'schema_type': 'contrat'
            },
            {
                'title': 'Facture #{number}',
                'description': 'Facture de prestation de services',
                'file_type': 'pdf',
                'content': 'Facture n°{number} du {date}...',
                'schema_type': 'facture'
            },
            {
                'title': 'Rapport mensuel {month}',
                'description': 'Rapport d\'activité mensuel',
                'file_type': 'docx',
                'content': 'Rapport d\'activité pour le mois de {month}...',
                'schema_type': 'rapport'
            },
            {
                'title': 'Présentation projet {project}',
                'description': 'Slides de présentation du projet',
                'file_type': 'pdf',
                'content': 'Présentation du projet {project}...',
                'schema_type': 'presentation'
            },
            {
                'title': 'Email important - {subject}',
                'description': 'Communication interne importante',
                'file_type': 'txt',
                'content': 'De: admin@company.com\nObjet: {subject}\n\nContenu important...',
                'schema_type': 'email'
            }
        ]

        statuses = ['uploaded', 'metadata_extracted', 'schema_proposed', 'schema_validated', 'pre_annotated',
                    'annotated', 'validated']

        for i in range(count):
            template = random.choice(document_templates)
            user = random.choice(users)

            # Générer des données variables
            names = ['Alice Dupont', 'Bob Martin', 'Claire Bernard', 'David Moreau']
            months = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin']
            projects = ['Alpha', 'Beta', 'Gamma', 'Delta', 'Epsilon']
            subjects = ['Réunion urgente', 'Nouvelle procédure', 'Mise à jour importante', 'Formation requise']

            variables = {
                'name': random.choice(names),
                'number': f'2024-{i + 1:03d}',
                'date': (timezone.now() - timedelta(days=random.randint(1, 90))).strftime('%d/%m/%Y'),
                'month': random.choice(months),
                'project': random.choice(projects),
                'subject': random.choice(subjects)
            }

            # Créer le document
            title = template['title'].format(**variables)
            content = template['content'].format(**variables)

            document = Document.objects.create(
                title=title,
                description=template['description'],
                file_type=template['file_type'],
                file_size=random.randint(1024, 1024 * 1024 * 5),  # 1KB à 5MB
                status=random.choice(statuses),
                uploaded_by=user,
                metadata={
                    'document_type': template['file_type'].upper(),
                    'word_count': len(content.split()),
                    'character_count': len(content),
                    'text_preview': content[:500],
                    'extraction_date': timezone.now().isoformat(),
                    'file_extension': f'.{template["file_type"]}',
                    'mime_type': f'application/{template["file_type"]}' if template[
                                                                               'file_type'] != 'txt' else 'text/plain'
                }
            )

            # Créer un fichier factice
            fake_file_content = content.encode('utf-8')
            document.file.save(
                f'{title[:50]}.{template["file_type"]}',
                ContentFile(fake_file_content),
                save=True
            )

            # Créer un schéma d'annotation si le document a progressé
            if document.status in ['schema_proposed', 'schema_validated', 'pre_annotated', 'annotated', 'validated']:
                schema = self.create_annotation_schema(document, template['schema_type'], with_ai)

                # Créer une annotation si le document a encore plus progressé
                if document.status in ['pre_annotated', 'annotated', 'validated']:
                    annotation = self.create_annotation(document, schema, user, with_ai)

                    # Valider l'annotation si nécessaire
                    if document.status == 'validated':
                        annotation.is_validated = True
                        annotation.validated_by = random.choice(users)
                        annotation.validated_at = timezone.now()
                        annotation.confidence_score = random.uniform(7.0, 10.0)
                        annotation.validation_notes = random.choice([
                            'Annotation excellente, très précise.',
                            'Bon travail, quelques détails mineurs à améliorer.',
                            'Annotation complète et bien structurée.',
                            'Parfait, toutes les informations sont correctes.'
                        ])
                        annotation.save()

                        document.validated_by = annotation.validated_by
                        document.validated_at = annotation.validated_at
                        document.save()

            self.stdout.write(f'  ✓ Document créé: {title[:50]}... (statut: {document.status})')

    def create_annotation_schema(self, document, schema_type, with_ai=True):
        """Crée un schéma d'annotation pour un document"""

        schema_templates = {
            'contrat': {
                'name': 'Schéma Contrat de Travail',
                'description': 'Schéma pour l\'annotation des contrats de travail',
                'fields': [
                    {'name': 'employee_name', 'label': 'Nom de l\'employé', 'type': 'text', 'required': True},
                    {'name': 'position', 'label': 'Poste', 'type': 'text', 'required': True},
                    {'name': 'salary', 'label': 'Salaire', 'type': 'number', 'required': True},
                    {'name': 'start_date', 'label': 'Date de début', 'type': 'date', 'required': True},
                    {'name': 'contract_type', 'label': 'Type de contrat', 'type': 'choice', 'required': True,
                     'choices': ['CDI', 'CDD', 'Stage', 'Freelance']},
                    {'name': 'benefits', 'label': 'Avantages', 'type': 'multiple_choice', 'required': False,
                     'choices': ['Tickets restaurant', 'Mutuelle', 'Primes', 'Télétravail']},
                ]
            },
            'facture': {
                'name': 'Schéma Facture',
                'description': 'Schéma pour l\'annotation des factures',
                'fields': [
                    {'name': 'invoice_number', 'label': 'Numéro de facture', 'type': 'text', 'required': True},
                    {'name': 'client_name', 'label': 'Nom du client', 'type': 'text', 'required': True},
                    {'name': 'amount', 'label': 'Montant total', 'type': 'number', 'required': True},
                    {'name': 'invoice_date', 'label': 'Date de facture', 'type': 'date', 'required': True},
                    {'name': 'due_date', 'label': 'Date d\'échéance', 'type': 'date', 'required': True},
                    {'name': 'status', 'label': 'Statut', 'type': 'choice', 'required': True,
                     'choices': ['En attente', 'Payée', 'En retard', 'Annulée']},
                ]
            },
            'rapport': {
                'name': 'Schéma Rapport',
                'description': 'Schéma pour l\'annotation des rapports',
                'fields': [
                    {'name': 'report_title', 'label': 'Titre du rapport', 'type': 'text', 'required': True},
                    {'name': 'author', 'label': 'Auteur', 'type': 'text', 'required': True},
                    {'name': 'period', 'label': 'Période couverte', 'type': 'text', 'required': True},
                    {'name': 'summary', 'label': 'Résumé exécutif', 'type': 'text', 'required': True},
                    {'name': 'recommendations', 'label': 'Recommandations', 'type': 'text', 'required': False},
                    {'name': 'confidential', 'label': 'Confidentiel', 'type': 'boolean', 'required': False},
                ]
            },
            'presentation': {
                'name': 'Schéma Présentation',
                'description': 'Schéma pour l\'annotation des présentations',
                'fields': [
                    {'name': 'presentation_title', 'label': 'Titre de la présentation', 'type': 'text',
                     'required': True},
                    {'name': 'presenter', 'label': 'Présentateur', 'type': 'text', 'required': True},
                    {'name': 'target_audience', 'label': 'Public cible', 'type': 'text', 'required': True},
                    {'name': 'key_points', 'label': 'Points clés', 'type': 'text', 'required': True},
                    {'name': 'duration', 'label': 'Durée estimée', 'type': 'number', 'required': False},
                ]
            },
            'email': {
                'name': 'Schéma Email',
                'description': 'Schéma pour l\'annotation des emails',
                'fields': [
                    {'name': 'subject', 'label': 'Objet', 'type': 'text', 'required': True},
                    {'name': 'sender', 'label': 'Expéditeur', 'type': 'text', 'required': True},
                    {'name': 'priority', 'label': 'Priorité', 'type': 'choice', 'required': True,
                     'choices': ['Basse', 'Normale', 'Haute', 'Urgente']},
                    {'name': 'category', 'label': 'Catégorie', 'type': 'choice', 'required': True,
                     'choices': ['Administratif', 'Technique', 'Commercial', 'RH']},
                    {'name': 'action_required', 'label': 'Action requise', 'type': 'boolean', 'required': False},
                ]
            }
        }

        template = schema_templates.get(schema_type, schema_templates['contrat'])

        # Créer le schéma
        schema = AnnotationSchema.objects.create(
            document=document,
            name=template['name'],
            description=template['description'],
            ai_generated_schema=template if with_ai else {},
            final_schema=template,
            is_validated=True,
            created_by=document.uploaded_by
        )

        # Créer les champs
        for i, field_data in enumerate(template['fields']):
            AnnotationField.objects.create(
                schema=schema,
                name=field_data['name'],
                label=field_data['label'],
                field_type=field_data['type'],
                description=field_data.get('description', ''),
                is_required=field_data.get('required', False),
                choices=field_data.get('choices', []),
                order=i
            )

        return schema

    def create_annotation(self, document, schema, user, with_ai=True):
        """Crée une annotation pour un document"""

        # Générer des données d'annotation réalistes selon le type de schéma
        annotation_data = {}
        ai_pre_annotations = {}

        for field in schema.fields.all():
            if field.field_type == 'text':
                if 'name' in field.name.lower():
                    value = random.choice(['Alice Dupont', 'Bob Martin', 'Claire Bernard', 'David Moreau'])
                elif 'title' in field.name.lower() or 'subject' in field.name.lower():
                    value = document.title
                elif 'author' in field.name.lower() or 'presenter' in field.name.lower():
                    value = user.get_full_name() or user.username
                elif 'summary' in field.name.lower():
                    value = 'Résumé automatiquement généré du contenu du document.'
                else:
                    value = f'Valeur pour {field.label}'

            elif field.field_type == 'number':
                if 'salary' in field.name.lower():
                    value = random.randint(30000, 80000)
                elif 'amount' in field.name.lower():
                    value = random.randint(100, 10000)
                elif 'duration' in field.name.lower():
                    value = random.randint(15, 120)
                else:
                    value = random.randint(1, 1000)

            elif field.field_type == 'date':
                value = (timezone.now() - timedelta(days=random.randint(0, 365))).date().isoformat()

            elif field.field_type == 'boolean':
                value = random.choice([True, False])

            elif field.field_type == 'choice':
                value = random.choice(field.choices) if field.choices else 'Option 1'

            elif field.field_type == 'multiple_choice':
                num_choices = random.randint(1, min(3, len(field.choices))) if field.choices else 1
                value = random.sample(field.choices, num_choices) if field.choices else ['Option 1']

            else:
                value = f'Valeur pour {field.label}'

            annotation_data[field.name] = value

            # Générer des pré-annotations IA légèrement différentes
            if with_ai:
                if field.field_type == 'text' and random.random() < 0.3:
                    ai_pre_annotations[field.name] = f'[IA] {value}'
                elif field.field_type == 'choice' and random.random() < 0.2:
                    other_choices = [c for c in field.choices if c != value] if field.choices else []
                    if other_choices:
                        ai_pre_annotations[field.name] = random.choice(other_choices)
                else:
                    ai_pre_annotations[field.name] = value

        # Créer l'annotation
        annotation = Annotation.objects.create(
            document=document,
            schema=schema,
            ai_pre_annotations=ai_pre_annotations if with_ai else {},
            final_annotations=annotation_data,
            is_complete=random.choice([True, True, True, False]),  # 75% de chance d'être complète
            annotated_by=user
        )

        # Créer quelques entrées d'historique
        AnnotationHistory.objects.create(
            annotation=annotation,
            action_type='created',
            comment='Annotation créée automatiquement',
            performed_by=user
        )

        if random.random() < 0.5:  # 50% de chance d'avoir des modifications
            AnnotationHistory.objects.create(
                annotation=annotation,
                action_type='updated',
                field_name=random.choice([f.name for f in schema.fields.all()]),
                old_value='Ancienne valeur',
                new_value='Nouvelle valeur',
                comment='Mise à jour des données',
                performed_by=user
            )

        return annotation