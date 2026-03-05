"""Evidence management API views."""
import json
import logging
from typing import Optional

from django.core.exceptions import SuspiciousOperation, ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from cybertrust.apps.evidence.models import Evidence, EvidenceControlLink
from cybertrust.apps.controls.models import Control
from cybertrust.apps.organizations.models import Organization
from cybertrust.apps.ai_engine.tasks import analyze_evidence_for_control
from cybertrust.apps.audits.services import record_event

logger = logging.getLogger(__name__)


# ============================================================================
# SERIALIZERS
# ============================================================================


class EvidenceSerializer(serializers.ModelSerializer):
    """Serializer for Evidence model."""
    
    status_display = serializers.CharField(
        source='get_status_display', 
        read_only=True
    )
    file_type_display = serializers.CharField(
        source='get_file_type_display',
        read_only=True
    )
    
    class Meta:
        model = Evidence
        fields = [
            'id',
            'organization',
            'original_filename',
            'file_size',
            'file_type',
            'file_type_display',
            'status',
            'status_display',
            'extracted_text_length',
            'error_message',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'status',
            'extracted_text_length',
            'error_message',
            'created_at',
            'updated_at',
        ]
    
    def get_extracted_text_length(self, obj):
        """Return length of extracted text."""
        return len(obj.extracted_text or '')


# ============================================================================
# EVIDENCE UPLOAD & LISTING
# ============================================================================


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_evidence(request, org_slug: str):
    """
    Upload evidence file to an organization.
    
    POST /api/v1/organizations/{org_slug}/evidence/upload/
    
    Multipart form data:
    - file: Evidence file (PDF, DOCX, PNG, JPG)
    - description: Optional description
    
    Returns:
    {
        "id": 42,
        "original_filename": "policy.pdf",
        "status": "UPLOADED",
        "file_size": 2048,
        "message": "Evidence uploaded successfully"
    }
    """
    try:
        # Verify organization exists and user has access
        org = get_object_or_404(Organization, slug=org_slug)
        
        # Check permission (ensure user belongs to org)
        if not request.user.organizations.filter(id=org.id).exists():
            return Response(
                {"error": "You don't have access to this organization"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get file from request
        if 'file' not in request.FILES:
            return Response(
                {"error": "No file provided"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        uploaded_file = request.FILES['file']
        
        # Validate file size
        from django.conf import settings
        max_size = getattr(settings, 'MAX_UPLOAD_SIZE', 25 * 1024 * 1024)
        
        if uploaded_file.size > max_size:
            return Response(
                {
                    "error": f"File too large. Max size: {max_size / (1024*1024):.0f}MB, "
                            f"Your file: {uploaded_file.size / (1024*1024):.1f}MB"
                },
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            )
        
        # Validate file extension
        from django.core.files.uploadedfile import UploadedFile
        
        allowed_extensions = getattr(
            settings, 
            'EVIDENCE_ALLOWED_EXTENSIONS', 
            ['pdf', 'docx', 'png', 'jpg', 'jpeg']
        )
        
        file_ext = uploaded_file.name.split('.')[-1].lower()
        if file_ext not in allowed_extensions:
            return Response(
                {
                    "error": f"File type not allowed. Allowed: {', '.join(allowed_extensions)}"
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Determine file type
        file_type_map = {
            'pdf': Evidence.FILE_PDF,
            'docx': Evidence.FILE_DOCX,
            'doc': Evidence.FILE_DOCX,
            'png': Evidence.FILE_IMAGE,
            'jpg': Evidence.FILE_IMAGE,
            'jpeg': Evidence.FILE_IMAGE,
        }
        file_type = file_type_map.get(file_ext, Evidence.FILE_OTHER)
        
        # Create evidence record
        with transaction.atomic():
            evidence = Evidence.objects.create(
                organization=org,
                uploaded_by=request.user,
                file=uploaded_file,
                original_filename=uploaded_file.name,
                file_size=uploaded_file.size,
                file_type=file_type,
                status=Evidence.STATUS_UPLOADED,
            )
            
            # Record audit event
            record_event(
                organization_id=org.id,
                event_type='EVIDENCE_UPLOADED',
                description=f"Evidence uploaded: {uploaded_file.name}",
                metadata={
                    'evidence_id': evidence.id,
                    'filename': uploaded_file.name,
                    'file_size': uploaded_file.size,
                    'user_id': request.user.id,
                }
            )
        
        logger.info(
            f"Evidence uploaded: id={evidence.id}, org={org_slug}, "
            f"filename={uploaded_file.name}, size={uploaded_file.size}"
        )
        
        return Response(
            {
                'id': evidence.id,
                'original_filename': evidence.original_filename,
                'status': evidence.status,
                'file_size': evidence.file_size,
                'message': 'Evidence uploaded successfully'
            },
            status=status.HTTP_201_CREATED
        )
        
    except Exception as e:
        logger.error(f"Evidence upload failed: {str(e)}", exc_info=True)
        return Response(
            {"error": f"Upload failed: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_evidence(request, org_slug: str):
    """
    List all evidence files for an organization.
    
    GET /api/v1/organizations/{org_slug}/evidence/
    
    Query parameters:
    - status: Filter by status (UPLOADED, EXTRACTED, ANALYZED, FAILED)
    - limit: Number of results (default: 20)
    - offset: Pagination offset (default: 0)
    
    Returns:
    {
        "count": 42,
        "next": "...",
        "previous": "...",
        "results": [...]
    }
    """
    try:
        org = get_object_or_404(Organization, slug=org_slug)
        
        # Check permission
        if not request.user.organizations.filter(id=org.id).exists():
            return Response(
                {"error": "You don't have access to this organization"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get query parameters
        status_filter = request.query_params.get('status')
        limit = int(request.query_params.get('limit', 20))
        offset = int(request.query_params.get('offset', 0))
        
        # Build queryset
        queryset = Evidence.objects.filter(
            organization=org
        ).select_related('uploaded_by').order_by('-created_at')
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Get total count
        total_count = queryset.count()
        
        # Apply pagination
        results = queryset[offset:offset + limit]
        
        # Serialize
        serializer = EvidenceSerializer(results, many=True)
        
        return Response({
            'count': total_count,
            'limit': limit,
            'offset': offset,
            'results': serializer.data
        })
        
    except ValueError:
        return Response(
            {"error": "Invalid query parameters"},
            status=status.HTTP_400_BAD_REQUEST
        )


# ============================================================================
# EVIDENCE DETAILS & STATUS TRACKING
# ============================================================================


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def evidence_detail(request, org_slug: str, evidence_id: int):
    """
    Get detail of a specific evidence file.
    
    GET /api/v1/organizations/{org_slug}/evidence/{id}/
    
    Returns full evidence info including extracted text length and status.
    """
    try:
        org = get_object_or_404(Organization, slug=org_slug)
        evidence = get_object_or_404(Evidence, id=evidence_id, organization=org)
        
        # Check permission
        if not request.user.organizations.filter(id=org.id).exists():
            return Response(
                {"error": "You don't have access"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = EvidenceSerializer(evidence)
        return Response(serializer.data)
        
    except Exception as e:
        logger.error(f"Evidence detail error: {str(e)}")
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def evidence_status(request, org_slug: str, evidence_id: int):
    """
    Get real-time status of evidence processing.
    
    GET /api/v1/organizations/{org_slug}/evidence/{id}/status/
    
    Used for progress polling from frontend.
    
    Returns:
    {
        "id": 42,
        "status": "ANALYZING",
        "progress": 66,
        "message": "AI analysis in progress...",
        "extracted_text_length": 5420,
        "error_message": null,
        "linked_controls_count": 3,
        "analyzed_controls_count": 2
    }
    """
    try:
        org = get_object_or_404(Organization, slug=org_slug)
        evidence = get_object_or_404(Evidence, id=evidence_id, organization=org)
        
        # Check permission
        if not request.user.organizations.filter(id=org.id).exists():
            return Response(
                {"error": "You don't have access"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Map status to progress percentage
        progress_map = {
            Evidence.STATUS_UPLOADED: 0,
            Evidence.STATUS_EXTRACTING: 25,
            Evidence.STATUS_EXTRACTED: 25,
            Evidence.STATUS_ANALYZING: 75,
            Evidence.STATUS_ANALYZED: 100,
            Evidence.STATUS_FAILED: 100,
        }
        
        # Get linked controls count
        linked_count = evidence.evidencecontrollink_set.count()
        analyzed_count = evidence.evidencecontrollink_set.filter(
            control__scoringsnapshot__status__in=['COMPLIANT', 'PARTIAL', 'NON_COMPLIANT']
        ).distinct().count()
        
        return Response({
            'id': evidence.id,
            'status': evidence.status,
            'progress': progress_map.get(evidence.status, 0),
            'message': evidence.get_status_display(),
            'extracted_text_length': len(evidence.extracted_text or ''),
            'error_message': evidence.error_message,
            'linked_controls_count': linked_count,
            'analyzed_controls_count': analyzed_count,
        })
        
    except Exception as e:
        logger.error(f"Status endpoint error: {str(e)}")
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================================
# CONTROL LINKING
# ============================================================================


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def link_control(request, org_slug: str, evidence_id: int):
    """
    Link a control to evidence for analysis.
    
    POST /api/v1/organizations/{org_slug}/evidence/{id}/link/
    
    JSON body:
    {
        "control_id": 1
    }
    
    Returns:
    {
        "id": 1,
        "evidence_id": 42,
        "control_id": 1,
        "message": "Control linked successfully"
    }
    """
    try:
        org = get_object_or_404(Organization, slug=org_slug)
        evidence = get_object_or_404(Evidence, id=evidence_id, organization=org)
        
        # Check permission
        if not request.user.organizations.filter(id=org.id).exists():
            return Response(
                {"error": "You don't have access"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if user has permission to modify (ADMIN or SECURITY_OFFICER)
        user_org = request.user.userorganization_set.get(organization=org)
        if user_org.role not in ['ADMIN', 'SECURITY_OFFICER']:
            return Response(
                {"error": "You don't have permission to link controls"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        data = json.loads(request.body)
        control_id = data.get('control_id')
        
        if not control_id:
            return Response(
                {"error": "control_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        control = get_object_or_404(Control, id=control_id)
        
        # Create link if not already exists
        link, created = EvidenceControlLink.objects.get_or_create(
            evidence=evidence,
            control=control
        )
        
        record_event(
            organization_id=org.id,
            event_type='CONTROL_LINKED',
            description=f"Control {control.code} linked to evidence {evidence.id}",
            metadata={
                'evidence_id': evidence.id,
                'control_id': control.id,
                'created': created,
            }
        )
        
        return Response({
            'id': link.id,
            'evidence_id': evidence.id,
            'control_id': control.id,
            'message': 'Control linked successfully' if created 
                      else 'Control already linked',
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
        
    except json.JSONDecodeError:
        return Response(
            {"error": "Invalid JSON"},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Link control error: {str(e)}")
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================================
# ANALYSIS TRIGGERING
# ============================================================================


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def trigger_analysis(request, org_slug: str, evidence_id: int):
    """
    Trigger AI analysis for an evidence file against linked controls.
    
    POST /api/v1/organizations/{org_slug}/evidence/{id}/analyze/
    
    This queues async Celery tasks to analyze the evidence against all
    linked controls.
    
    Returns:
    {
        "message": "Analysis queued successfully",
        "task_ids": ["abc-123", "def-456"],
        "controls_count": 2
    }
    """
    try:
        org = get_object_or_404(Organization, slug=org_slug)
        evidence = get_object_or_404(Evidence, id=evidence_id, organization=org)
        
        # Check permission
        if not request.user.organizations.filter(id=org.id).exists():
            return Response(
                {"error": "You don't have access"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if user has permission (ADMIN or SECURITY_OFFICER)
        user_org = request.user.userorganization_set.get(organization=org)
        if user_org.role not in ['ADMIN', 'SECURITY_OFFICER']:
            return Response(
                {"error": "You don't have permission to trigger analysis"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get linked controls
        linked_controls = evidence.evidencecontrollink_set.values_list(
            'control_id', flat=True
        )
        
        if not linked_controls:
            return Response(
                {"error": "No controls linked to this evidence"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Queue analysis tasks
        task_ids = []
        for control_id in linked_controls:
            task = analyze_evidence_for_control.delay(
                evidence_id=evidence.id,
                control_id=control_id,
                organization_id=org.id
            )
            task_ids.append(task.id)
        
        # Record event
        record_event(
            organization_id=org.id,
            event_type='ANALYSIS_TRIGGERED',
            description=f"Analysis triggered for evidence {evidence.id}",
            metadata={
                'evidence_id': evidence.id,
                'controls_count': len(task_ids),
                'user_id': request.user.id,
                'task_ids': task_ids,
            }
        )
        
        logger.info(
            f"Analysis triggered: evidence={evidence_id}, "
            f"org={org_slug}, controls={len(task_ids)}"
        )
        
        return Response({
            'message': 'Analysis queued successfully',
            'task_ids': task_ids,
            'controls_count': len(task_ids),
        }, status=status.HTTP_202_ACCEPTED)
        
    except Exception as e:
        logger.error(f"Trigger analysis error: {str(e)}", exc_info=True)
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================================
# BATCH OPERATIONS
# ============================================================================


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def extract_all_pending(request, org_slug: str):
    """
    Queue extraction for all pending evidence in organization.
    
    POST /api/v1/organizations/{org_slug}/evidence/extract-all/
    
    Returns:
    {
        "message": "Extraction queued",
        "batch_task_id": "xyz-789",
        "evidence_count": 5
    }
    """
    try:
        org = get_object_or_404(Organization, slug=org_slug)
        
        # Check permission
        if not request.user.organizations.filter(id=org.id).exists():
            return Response(
                {"error": "You don't have access"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        user_org = request.user.userorganization_set.get(organization=org)
        if user_org.role not in ['ADMIN', 'SECURITY_OFFICER']:
            return Response(
                {"error": "Permission denied"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Import here to avoid circular imports
        from cybertrust.apps.ai_engine.tasks import extract_all_evidence_in_batch
        
        # Queue batch extraction
        task = extract_all_evidence_in_batch.delay(org.id)
        
        record_event(
            organization_id=org.id,
            event_type='BATCH_EXTRACTION_QUEUED',
            metadata={'task_id': task.id}
        )
        
        return Response({
            'message': 'Extraction queued',
            'batch_task_id': task.id,
        }, status=status.HTTP_202_ACCEPTED)
        
    except Exception as e:
        logger.error(f"Batch extraction error: {str(e)}")
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def nca_compliance_audit(request, org_slug):
    """
    POST /api/v1/organizations/{org_slug}/evidence/{evidence_id}/nca-audit/
    
    Perform NCA compliance audit on evidence.
    Analyzes evidence against all 114 NCA controls.
    
    Returns full JSON analysis per user specifications.
    """
    try:
        org = UserOrganization.objects.get(
            slug=org_slug,
            user_organization_relationships__user=request.user
        ).organization
        
        # Check permission
        if not is_auditor(request.user, org):
            return Response(
                {"error": "Insufficient permissions"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        evidence_id = request.data.get('evidence_id')
        if not evidence_id:
            return Response(
                {"error": "evidence_id required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Queue async audit task
        from cybertrust.apps.ai_engine.tasks import run_nca_compliance_audit
        task = run_nca_compliance_audit.delay(
            evidence_id=evidence_id,
            org_id=org.id,
            user_id=request.user.id
        )
        
        record_event(
            "COMPLIANCE_AUDIT_STARTED",
            request.user,
            org,
            {
                "evidence_id": evidence_id,
                "task_id": task.id
            }
        )
        
        return Response({
            'message': 'NCA compliance audit started',
            'task_id': task.id,
            'status_url': f'/api/v1/organizations/{org_slug}/audit-status/{task.id}/'
        }, status=status.HTTP_202_ACCEPTED)
        
    except UserOrganization.DoesNotExist:
        return Response(
            {"error": "Organization not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"NCA audit error: {str(e)}")
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def nca_audit_result(request, org_slug, task_id):
    """
    GET /api/v1/organizations/{org_slug}/nca-audit/{task_id}/
    
    Get NCA compliance audit results.
    Returns full JSON analysis with all control assessments.
    """
    try:
        from celery.result import AsyncResult
        result = AsyncResult(task_id)
        
        if result.state == 'PENDING':
            return Response({
                'status': 'PENDING',
                'message': 'Audit in progress...',
                'task_id': task_id
            })
        elif result.state == 'SUCCESS':
            analysis = result.result
            return Response(analysis, status=status.HTTP_200_OK)
        elif result.state == 'FAILURE':
            return Response({
                'error': str(result.info),
                'status': 'FAILED'
            }, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({
                'status': result.state,
                'task_id': task_id
            })
            
    except Exception as e:
        logger.error(f"Audit result error: {str(e)}")
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
