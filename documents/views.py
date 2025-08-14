# documents/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
import json
import logging

from .models import Document, AnnotationSchema, Annotation, AnnotationField, AnnotationHistory
from .forms import (
    DocumentUploadForm, AnnotationSchemaForm, AnnotationForm,
    ValidationForm, SearchForm
)
from .services.annotation_service import AnnotationService
from .services.hybrid_service import HybridAnnotationService

logger = logging.getLogger('documents')

# Instance globale du service hybride
hybrid_service = HybridAnnotationService()


@login_required
def dashboard(request):
    """Vue principale du tableau de bord"""
    try:
        # Utiliser le service hybride pour les statistiques combinées
        stats = hybrid_service.get_combined_statistics()

        # Documents récents de l'utilisateur
        recent_documents = Document.objects.filter(
            uploaded_by=request.user
        ).order_by('-created_at')[:5]

        # Annotations en cours pour l'utilisateur (Django + MongoDB)
        pending_annotations = Annotation.objects.filter(
            annotated_by=request.user,
            is_complete=False
        ).select_related('document')[:5]

        # Documents à valider (pour les experts)
        documents_to_validate = Document.objects.filter(
            status='annotated'
        ).select_related('annotation')[:5]

        context = {
            'stats': stats,
            'recent_documents': recent_documents,
            'pending_annotations': pending_annotations,
            'documents_to_validate': documents_to_validate,
        }

        return render(request, 'documents/dashboard.html', context)

    except Exception as e:
        logger.error(f"Erreur dashboard: {str(e)}")
        messages.error(request, f"Erreur lors du chargement du tableau de bord: {str(e)}")
        return render(request, 'documents/dashboard.html', {'stats': {}})


@login_required
def document_list(request):
    """Liste des documents avec recherche et filtres"""
    try:
        form = SearchForm(request.GET)
        documents = Document.objects.all().order_by('-created_at')

        if form.is_valid():
            query = form.cleaned_data.get('query')
            file_type = form.cleaned_data.get('file_type')
            status = form.cleaned_data.get('status')
            date_from = form.cleaned_data.get('date_from')
            date_to = form.cleaned_data.get('date_to')

            if query:
                documents = documents.filter(
                    Q(title__icontains=query) |
                    Q(description__icontains=query)
                )

            if file_type:
                documents = documents.filter(file_type=file_type)

            if status:
                documents = documents.filter(status=status)

            if date_from:
                documents = documents.filter(created_at__date__gte=date_from)

            if date_to:
                documents = documents.filter(created_at__date__lte=date_to)

        # Pagination
        paginator = Paginator(documents, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context = {
            'form': form,
            'page_obj': page_obj,
            'total_count': documents.count()
        }

        return render(request, 'documents/document_list.html', context)

    except Exception as e:
        logger.error(f"Erreur liste documents: {str(e)}")
        messages.error(request, f"Erreur lors du chargement des documents: {str(e)}")
        return render(request, 'documents/document_list.html', {'page_obj': None})


@login_required
def upload_document(request):
    """Téléversement d'un nouveau document"""
    if request.method == 'POST':
        form = DocumentUploadForm(request.POST, request.FILES)

        if form.is_valid():
            try:
                # Sauvegarde du document
                document = form.save(commit=False)
                document.uploaded_by = request.user
                document.save()

                # Traitement automatique
                annotation_service = AnnotationService()
                result = annotation_service.process_uploaded_document(document, request.user)

                if result['success']:
                    messages.success(
                        request,
                        f'Document "{document.title}" téléversé et traité avec succès!'
                    )
                    return redirect('documents:document_detail', pk=document.pk)
                else:
                    messages.warning(
                        request,
                        f'Document téléversé mais erreur de traitement: {result.get("error", "Erreur inconnue")}'
                    )
                    return redirect('documents:document_detail', pk=document.pk)

            except Exception as e:
                logger.error(f"Erreur upload document: {str(e)}")
                messages.error(request, f"Erreur lors du téléversement: {str(e)}")

        else:
            messages.error(request, "Veuillez corriger les erreurs du formulaire.")

    else:
        form = DocumentUploadForm()

    return render(request, 'documents/upload.html', {'form': form})


@login_required
def document_detail(request, pk):
    """Détail d'un document"""
    try:
        document = get_object_or_404(Document, pk=pk)

        # Récupération des éléments liés
        annotation_schema = getattr(document, 'annotation_schema', None)
        annotation = getattr(document, 'annotation', None)

        context = {
            'document': document,
            'annotation_schema': annotation_schema,
            'annotation': annotation,
            'can_edit_schema': annotation_schema and not annotation_schema.is_validated,
            'can_annotate': annotation_schema and annotation_schema.is_validated,
            'can_validate': annotation and annotation.is_complete and not annotation.is_validated
        }

        return render(request, 'documents/document_detail.html', context)

    except Exception as e:
        logger.error(f"Erreur détail document: {str(e)}")
        messages.error(request, f"Erreur lors du chargement du document: {str(e)}")
        return redirect('documents:document_list')


@login_required
def edit_schema(request, document_pk):
    """Édition du schéma d'annotation"""
    try:
        document = get_object_or_404(Document, pk=document_pk)
        schema = get_object_or_404(AnnotationSchema, document=document)

        if schema.is_validated:
            messages.error(request, "Ce schéma a déjà été validé et ne peut plus être modifié.")
            return redirect('documents:document_detail', pk=document.pk)

        if request.method == 'POST':
            form = AnnotationSchemaForm(request.POST, instance=schema)

            if form.is_valid():
                # Sauvegarde du schéma
                updated_schema = form.save()

                # Validation avec le service
                annotation_service = AnnotationService()
                result = annotation_service.validate_annotation_schema(
                    updated_schema,
                    form.cleaned_data['schema_json'],
                    request.user
                )

                if result['success']:
                    messages.success(request, "Schéma validé avec succès!")
                    return redirect('documents:document_detail', pk=document.pk)
                else:
                    messages.error(request, f"Erreur validation: {result.get('error')}")

            else:
                messages.error(request, "Veuillez corriger les erreurs du formulaire.")

        else:
            form = AnnotationSchemaForm(instance=schema)

        context = {
            'form': form,
            'document': document,
            'schema': schema
        }

        return render(request, 'documents/schema_editor.html', context)

    except Exception as e:
        logger.error(f"Erreur édition schéma: {str(e)}")
        messages.error(request, f"Erreur lors de l'édition du schéma: {str(e)}")
        return redirect('documents:document_detail', pk=document_pk)


@login_required
def schema_form_editor(request, document_pk):
    """Éditeur de schéma avec interface formulaire"""
    try:
        document = get_object_or_404(Document, pk=document_pk)
        schema = get_object_or_404(AnnotationSchema, document=document)
        
        if request.method == 'POST':
            logger.info(f"POST reçu pour schema_form_editor, données: {request.POST}")
            
            # Traitement du formulaire de schéma
            schema_data = request.POST.get('schema_json') or request.POST.get('schema_data')
            logger.info(f"schema_data reçu: {schema_data}")
            
            if schema_data:
                try:
                    # Parser le JSON et sauvegarder dans final_schema
                    schema_json_data = json.loads(schema_data)
                    logger.info(f"JSON parsé avec succès: {schema_json_data}")
                    
                    schema.final_schema = schema_json_data
                    schema.save()
                    logger.info("Schéma sauvegardé avec succès")
                    
                    messages.success(request, "Schéma mis à jour avec succès!")
                    return redirect('documents:schema_editor', document_pk=document.pk)
                except Exception as e:
                    logger.error(f"Erreur lors de la sauvegarde: {str(e)}")
                    messages.error(request, f"Erreur lors de la sauvegarde: {str(e)}")
            else:
                logger.warning("Aucune donnée schema_json reçue")
                # Traitement des données du formulaire structuré
                schema_name = request.POST.get('schema_name', '')
                schema_description = request.POST.get('schema_description', '')
                
                # Construire le schéma à partir des données du formulaire
                # (Cette partie sera implémentée si nécessaire)
                messages.info(request, "Fonctionnalité de sauvegarde du formulaire en cours de développement.")
        
        # Récupération du schéma JSON actuel
        try:
            # Utiliser final_schema s'il existe, sinon ai_generated_schema
            if schema.final_schema and isinstance(schema.final_schema, dict) and schema.final_schema.get('fields'):
                schema_json = schema.final_schema
            elif schema.ai_generated_schema and isinstance(schema.ai_generated_schema, dict) and schema.ai_generated_schema.get('fields'):
                schema_json = schema.ai_generated_schema
            else:
                schema_json = {'name': '', 'description': '', 'fields': []}
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du schéma JSON: {str(e)}")
            schema_json = {'name': '', 'description': '', 'fields': []}
        
        # Sérialiser correctement le JSON pour JavaScript
        schema_json_js = json.dumps(schema_json) if schema_json else json.dumps({'name': '', 'description': '', 'fields': []})
        
        context = {
            'document': document,
            'schema': schema,
            'schema_json': schema_json,
            'schema_json_js': schema_json_js,
        }
        
        return render(request, 'documents/schema_form_editor.html', context)
        
    except Exception as e:
        logger.error(f"Erreur éditeur formulaire schéma: {str(e)}")
        messages.error(request, f"Erreur lors de l'édition du schéma: {str(e)}")
        return redirect('documents:document_detail', pk=document_pk)


@login_required
def annotate_document(request, document_pk):
    """Annotation d'un document"""
    try:
        document = get_object_or_404(Document, pk=document_pk)
        schema = get_object_or_404(AnnotationSchema, document=document)

        if not schema.is_validated:
            messages.error(request, "Le schéma doit être validé avant l'annotation.")
            return redirect('documents:document_detail', pk=document.pk)

        # Récupération ou création de l'annotation
        annotation, created = Annotation.objects.get_or_create(
            document=document,
            defaults={
                'schema': schema,
                'annotated_by': request.user
            }
        )

        # Génération des pré-annotations si nécessaire
        if created or not annotation.ai_pre_annotations:
            annotation_service = AnnotationService()
            result = annotation_service.generate_pre_annotations(document, request.user)

            if not result['success']:
                messages.warning(request, f"Pré-annotations non générées: {result.get('error')}")

        if request.method == 'POST':
            form = AnnotationForm(
                schema,
                annotation.final_annotations,
                request.POST
            )

            if form.is_valid():
                # Mise à jour des annotations
                annotation_data = form.get_annotation_data()

                annotation_service = AnnotationService()
                result = annotation_service.update_annotations(
                    annotation,
                    annotation_data,
                    request.user
                )

                if result['success']:
                    # Recharger l'annotation pour avoir l'état à jour
                    annotation.refresh_from_db()
                    
                    # Vérifier si l'annotation est maintenant complète
                    if annotation.is_complete:
                        messages.success(request, "Annotations sauvegardées et marquées comme complètes!")
                        messages.info(request, "Votre annotation est maintenant prête pour validation.")
                        
                        # Redirection selon l'action
                        if 'save_and_validate' in request.POST:
                            return redirect('documents:validate_annotation', document_pk=document.pk)
                        elif 'save_and_continue' in request.POST:
                            return redirect('documents:annotate_document', document_pk=document.pk)
                        else:
                            return redirect('documents:document_detail', pk=document.pk)
                    else:
                        completion_pct = annotation.completion_percentage
                        messages.success(request, f"Annotations sauvegardées! ({completion_pct:.0f}% complété)")
                        
                        # Redirection selon l'action
                        if 'save_and_continue' in request.POST:
                            return redirect('documents:annotate_document', document_pk=document.pk)
                        else:
                            return redirect('documents:document_detail', pk=document.pk)
                else:
                    messages.error(request, f"Erreur sauvegarde: {result.get('error')}")

            else:
                messages.error(request, "Veuillez corriger les erreurs du formulaire.")

        else:
            form = AnnotationForm(schema, annotation.final_annotations)

        context = {
            'form': form,
            'document': document,
            'annotation': annotation,
            'schema': schema,
            'completion_percentage': annotation.completion_percentage
        }

        return render(request, 'documents/annotation_editor.html', context)

    except Exception as e:
        logger.error(f"Erreur annotation document: {str(e)}")
        messages.error(request, f"Erreur lors de l'annotation: {str(e)}")
        return redirect('documents:document_detail', pk=document_pk)


@login_required
def validate_annotation(request, document_pk):
    """Validation d'une annotation par un expert"""
    try:
        document = get_object_or_404(Document, pk=document_pk)
        annotation = get_object_or_404(Annotation, document=document)

        if not annotation.is_complete:
            messages.error(request, "L'annotation doit être complète avant validation.")
            return redirect('documents:document_detail', pk=document.pk)

        if annotation.is_validated:
            messages.error(request, "Cette annotation a déjà été validée.")
            return redirect('documents:document_detail', pk=document.pk)

        if request.method == 'POST':
            form = ValidationForm(request.POST)

            if form.is_valid():
                validation_status = form.cleaned_data['validation_status']
                notes = form.cleaned_data.get('validation_notes', '')
                confidence_score = form.cleaned_data.get('confidence_score')

                if validation_status == 'approved':
                    # Validation de l'annotation
                    annotation_service = AnnotationService()
                    result = annotation_service.validate_annotations(
                        annotation,
                        request.user,
                        notes
                    )

                    if result['success']:
                        if confidence_score:
                            annotation.confidence_score = confidence_score
                            annotation.save()

                        messages.success(request, "Annotation validée avec succès!")
                        return redirect('documents:document_detail', pk=document.pk)
                    else:
                        messages.error(request, f"Erreur validation: {result.get('error')}")

                elif validation_status == 'rejected':
                    # Rejet de l'annotation
                    AnnotationHistory.objects.create(
                        annotation=annotation,
                        action_type='rejected',
                        comment=f'Annotation rejetée: {notes}',
                        performed_by=request.user
                    )

                    # Réinitialiser le statut
                    annotation.is_complete = False
                    annotation.save()

                    document.status = 'pre_annotated'
                    document.save()

                    messages.warning(request, "Annotation rejetée. Le document est retourné en annotation.")
                    return redirect('documents:document_detail', pk=document.pk)

                else:  # needs_revision
                    # Demande de révision
                    AnnotationHistory.objects.create(
                        annotation=annotation,
                        action_type='updated',
                        comment=f'Révisions demandées: {notes}',
                        performed_by=request.user
                    )

                    messages.info(request, "Révisions demandées. L'annotateur a été notifié.")
                    return redirect('documents:document_detail', pk=document.pk)

            else:
                messages.error(request, "Veuillez corriger les erreurs du formulaire.")

        else:
            form = ValidationForm()

        context = {
            'form': form,
            'document': document,
            'annotation': annotation
        }

        return render(request, 'documents/validate_annotation.html', context)

    except Exception as e:
        logger.error(f"Erreur validation annotation: {str(e)}")
        messages.error(request, f"Erreur lors de la validation: {str(e)}")
        return redirect('documents:document_detail', pk=document_pk)


@login_required
@require_http_methods(["POST"])
def regenerate_schema(request, document_pk):
    """Régénération du schéma d'annotation avec l'IA"""
    try:
        document = get_object_or_404(Document, pk=document_pk)

        if hasattr(document, 'annotation_schema') and document.annotation_schema.is_validated:
            return JsonResponse({
                'success': False,
                'error': 'Le schéma a déjà été validé'
            })

        annotation_service = AnnotationService()
        result = annotation_service.generate_annotation_schema(document, request.user)

        if result['success']:
            return JsonResponse({
                'success': True,
                'message': 'Schéma régénéré avec succès',
                'schema_id': str(result['schema_id'])
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Erreur inconnue')
            })

    except Exception as e:
        logger.error(f"Erreur régénération schéma: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_http_methods(["POST"])
def regenerate_annotations(request, document_pk):
    """Régénération des pré-annotations avec l'IA"""
    try:
        document = get_object_or_404(Document, pk=document_pk)

        if not hasattr(document, 'annotation_schema') or not document.annotation_schema.is_validated:
            return JsonResponse({
                'success': False,
                'error': 'Le schéma doit être validé'
            })

        annotation_service = AnnotationService()
        result = annotation_service.generate_pre_annotations(document, request.user)

        if result['success']:
            return JsonResponse({
                'success': True,
                'message': 'Pré-annotations régénérées avec succès',
                'annotations': result['annotations']
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Erreur inconnue')
            })

    except Exception as e:
        logger.error(f"Erreur régénération annotations: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
def annotation_history(request, document_pk):
    """Historique des modifications d'annotation"""
    try:
        document = get_object_or_404(Document, pk=document_pk)
        annotation = get_object_or_404(Annotation, document=document)

        history = AnnotationHistory.objects.filter(
            annotation=annotation
        ).order_by('-created_at')

        # Pagination
        paginator = Paginator(history, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context = {
            'document': document,
            'annotation': annotation,
            'page_obj': page_obj
        }

        return render(request, 'documents/annotation_history.html', context)

    except Exception as e:
        logger.error(f"Erreur historique annotation: {str(e)}")
        messages.error(request, f"Erreur lors du chargement de l'historique: {str(e)}")
        return redirect('documents:document_detail', pk=document_pk)


@login_required
def export_annotations(request, document_pk):
    """Export des annotations en JSON"""
    try:
        document = get_object_or_404(Document, pk=document_pk)
        annotation = get_object_or_404(Annotation, document=document)

        export_data = {
            'document': {
                'id': str(document.id),
                'title': document.title,
                'filename': document.filename,
                'file_type': document.file_type,
                'created_at': document.created_at.isoformat(),
            },
            'schema': {
                'name': annotation.schema.name,
                'description': annotation.schema.description,
                'fields': list(annotation.schema.fields.values(
                    'name', 'label', 'field_type', 'description', 'is_required'
                ))
            },
            'annotations': annotation.final_annotations,
            'metadata': {
                'annotated_by': annotation.annotated_by.username,
                'annotated_at': annotation.updated_at.isoformat(),
                'is_validated': annotation.is_validated,
                'validated_by': annotation.validated_by.username if annotation.validated_by else None,
                'validated_at': annotation.validated_at.isoformat() if annotation.validated_at else None,
                'confidence_score': annotation.confidence_score,
                'completion_percentage': annotation.completion_percentage
            }
        }

        response = HttpResponse(
            json.dumps(export_data, indent=2, ensure_ascii=False),
            content_type='application/json'
        )
        response['Content-Disposition'] = f'attachment; filename="annotations_{document.filename}.json"'

        return response

    except Exception as e:
        logger.error(f"Erreur export annotations: {str(e)}")
        messages.error(request, f"Erreur lors de l'export: {str(e)}")
        return redirect('documents:document_detail', pk=document_pk)


@login_required
def statistics(request):
    """Page de statistiques globales avec données avancées"""
    try:
        from django.db.models import Avg, Count, F, Q, Sum
        from django.utils import timezone
        from datetime import datetime, timedelta
        import json

        # Statistiques de base
        annotation_service = AnnotationService()
        base_stats = annotation_service.get_document_statistics()

        # Statistiques avancées
        total_documents = Document.objects.count()
        total_annotations = Annotation.objects.count()
        total_schemas = AnnotationSchema.objects.count()
        
        # Répartition par statut avec couleurs
        status_stats = Document.objects.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        status_colors = {
            'uploaded': '#6c757d',
            'metadata_extracted': '#17a2b8', 
            'schema_proposed': '#ffc107',
            'schema_validated': '#28a745',
            'pre_annotated': '#fd7e14',
            'annotated': '#20c997',
            'validated': '#198754',
            'error': '#dc3545'
        }
        
        status_data = []
        for stat in status_stats:
            status_data.append({
                'status': stat['status'],
                'count': stat['count'],
                'color': status_colors.get(stat['status'], '#6c757d'),
                'label': dict(Document.STATUS_CHOICES).get(stat['status'], stat['status'])
            })

        # Répartition par type de fichier
        type_stats = Document.objects.values('file_type').annotate(
            count=Count('id')
        ).order_by('-count')

        # Performance des utilisateurs (top 10)
        user_stats_raw = Document.objects.values(
            'uploaded_by__username',
            'uploaded_by__first_name',
            'uploaded_by__last_name'
        ).annotate(
            total_docs=Count('id'),
            validated_docs=Count('id', filter=Q(status='validated')),
            annotated_docs=Count('id', filter=Q(status__in=['annotated', 'validated'])),
            avg_processing_time=Avg(
                F('updated_at') - F('created_at'),
                filter=Q(status='validated')
            )
        ).order_by('-total_docs')[:10]
        
        # Calculer les taux de réussite
        user_stats = []
        for user in user_stats_raw:
            success_rate = (user['validated_docs'] * 100 / user['total_docs']) if user['total_docs'] > 0 else 0
            user['success_rate'] = round(success_rate, 1)
            user_stats.append(user)

        # Évolution temporelle (6 derniers mois)
        six_months_ago = timezone.now() - timedelta(days=180)
        monthly_stats = []
        
        for i in range(6):
            month_start = six_months_ago + timedelta(days=30*i)
            month_end = month_start + timedelta(days=30)
            
            month_data = {
                'month': month_start.strftime('%b %Y'),
                'documents': Document.objects.filter(
                    created_at__gte=month_start,
                    created_at__lt=month_end
                ).count(),
                'validated': Document.objects.filter(
                    created_at__gte=month_start,
                    created_at__lt=month_end,
                    status='validated'
                ).count(),
                'annotations': Annotation.objects.filter(
                    created_at__gte=month_start,
                    created_at__lt=month_end
                ).count()
            }
            monthly_stats.append(month_data)

        # Statistiques de completion
        completion_stats = Annotation.objects.aggregate(
            avg_completion=Avg('completion_percentage'),
            total_complete=Count('id', filter=Q(is_complete=True)),
            total_validated=Count('id', filter=Q(is_validated=True))
        )

        # Temps de traitement par étape
        processing_stats = {
            'upload_to_schema': Document.objects.filter(
                status__in=['schema_proposed', 'schema_validated', 'pre_annotated', 'annotated', 'validated']
            ).aggregate(
                avg_time=Avg(F('updated_at') - F('created_at'))
            )['avg_time'],
            
            'schema_to_annotation': Document.objects.filter(
                status__in=['annotated', 'validated']
            ).aggregate(
                avg_time=Avg(F('updated_at') - F('created_at'))
            )['avg_time'],
            
            'annotation_to_validation': Document.objects.filter(
                status='validated'
            ).aggregate(
                avg_time=Avg(F('updated_at') - F('created_at'))
            )['avg_time']
        }

        # Statistiques de qualité
        quality_stats = {
            'schema_validation_rate': AnnotationSchema.objects.filter(is_validated=True).count() / max(total_schemas, 1) * 100,
            'annotation_completion_rate': completion_stats['total_complete'] / max(total_annotations, 1) * 100,
            'final_validation_rate': completion_stats['total_validated'] / max(total_annotations, 1) * 100,
            'avg_completion_percentage': completion_stats['avg_completion'] or 0
        }

        # Données pour les graphiques (JSON)
        chart_data = {
            'status_chart': {
                'labels': [item['label'] for item in status_data],
                'data': [item['count'] for item in status_data],
                'colors': [item['color'] for item in status_data]
            },
            'type_chart': {
                'labels': [dict(Document.FILE_TYPE_CHOICES).get(item['file_type'], item['file_type']) for item in type_stats],
                'data': [item['count'] for item in type_stats]
            },
            'monthly_chart': {
                'labels': [item['month'] for item in monthly_stats],
                'documents': [item['documents'] for item in monthly_stats],
                'validated': [item['validated'] for item in monthly_stats],
                'annotations': [item['annotations'] for item in monthly_stats]
            }
        }

        context = {
            'stats': base_stats,
            'total_documents': total_documents,
            'total_annotations': total_annotations,
            'total_schemas': total_schemas,
            'status_data': status_data,
            'type_stats': type_stats,
            'user_stats': user_stats,
            'monthly_stats': monthly_stats,
            'completion_stats': completion_stats,
            'processing_stats': processing_stats,
            'quality_stats': quality_stats,
            'chart_data_json': json.dumps(chart_data)
        }

        return render(request, 'documents/statistics.html', context)

    except Exception as e:
        logger.error(f"Erreur statistiques: {str(e)}")
        messages.error(request, f"Erreur lors du chargement des statistiques: {str(e)}")
        return render(request, 'documents/statistics.html', {'stats': {}})


@login_required
@require_http_methods(["POST"])
def delete_document(request, pk):
    """Suppression d'un document et de tous ses éléments associés"""
    try:
        document = get_object_or_404(Document, pk=pk)
        
        # Vérifier les permissions (optionnel - ajustez selon vos besoins)
        if document.uploaded_by != request.user and not request.user.is_staff:
            messages.error(request, "Vous n'avez pas l'autorisation de supprimer ce document.")
            return redirect('documents:document_list')
        
        # Sauvegarder les informations pour le message
        document_title = document.title
        document_id = str(document.id)
        
        # Compter les éléments associés avant suppression
        annotation_count = 0
        schema_count = 0
        history_count = 0
        
        try:
            if hasattr(document, 'annotation'):
                annotation_count = 1
                history_count = document.annotation.history.count()
            if hasattr(document, 'annotation_schema'):
                schema_count = 1
        except:
            pass
        
        logger.info(f"Suppression du document {document_id} ({document_title}) par {request.user.username}")
        logger.info(f"Éléments associés: {annotation_count} annotation(s), {schema_count} schéma(s), {history_count} entrée(s) d'historique")
        
        # Suppression du document (cascade automatique vers les éléments liés)
        document.delete()
        
        # Message de confirmation
        elements_deleted = []
        if annotation_count > 0:
            elements_deleted.append(f"{annotation_count} annotation(s)")
        if schema_count > 0:
            elements_deleted.append(f"{schema_count} schéma(s)")
        if history_count > 0:
            elements_deleted.append(f"{history_count} entrée(s) d'historique")
        
        if elements_deleted:
            elements_msg = " et " + ", ".join(elements_deleted)
        else:
            elements_msg = ""
        
        messages.success(
            request, 
            f'Document "{document_title}" supprimé avec succès{elements_msg}.'
        )
        
        logger.info(f"Document {document_id} supprimé avec succès")
        
        # Redirection vers la liste des documents
        return redirect('documents:document_list')
        
    except Exception as e:
        logger.error(f"Erreur suppression document: {str(e)}")
        messages.error(request, f"Erreur lors de la suppression du document: {str(e)}")
        return redirect('documents:document_list')


@login_required
def confirm_delete_document(request, pk):
    """Page de confirmation de suppression d'un document"""
    try:
        document = get_object_or_404(Document, pk=pk)
        
        # Vérifier les permissions
        if document.uploaded_by != request.user and not request.user.is_staff:
            messages.error(request, "Vous n'avez pas l'autorisation de supprimer ce document.")
            return redirect('documents:document_list')
        
        # Compter les éléments associés
        associated_elements = {
            'annotation': None,
            'schema': None,
            'history_count': 0,
            'fields_count': 0
        }
        
        try:
            if hasattr(document, 'annotation'):
                associated_elements['annotation'] = document.annotation
                associated_elements['history_count'] = document.annotation.history.count()
            
            if hasattr(document, 'annotation_schema'):
                associated_elements['schema'] = document.annotation_schema
                associated_elements['fields_count'] = document.annotation_schema.fields.count()
        except:
            pass
        
        context = {
            'document': document,
            'associated_elements': associated_elements
        }
        
        return render(request, 'documents/confirm_delete.html', context)
        
    except Exception as e:
        logger.error(f"Erreur confirmation suppression: {str(e)}")
        messages.error(request, f"Erreur lors du chargement de la confirmation: {str(e)}")
        return redirect('documents:document_list')