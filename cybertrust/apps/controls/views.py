"""Controls App Views - Cloud Integration Guides API + Dashboard."""
import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from cybertrust.apps.controls.services.cloud_guides import (
    generate_cloud_guide,
    get_all_cloud_guides,
    generate_integration_checklist,
)
from cybertrust.apps.controls.services.scoring import (
    get_dashboard_kpis,
    compute_control_score,
    get_category_scores,
)
from cybertrust.apps.controls.models import Control, ControlCategory
from cybertrust.apps.ai_engine.models import AIAnalysisResult
from cybertrust.apps.organizations.models import Organization

logger = logging.getLogger(__name__)


# ============================================================================
# CLOUD INTEGRATION GUIDES
# ============================================================================


@login_required
@require_http_methods(["GET"])
def get_cloud_guide(request, provider, requirement):
    """Get cloud integration guide for specific provider and requirement."""
    try:
        language = request.GET.get("lang", "en")
        if language not in ["ar", "en"]:
            language = "en"
        
        guide = generate_cloud_guide(provider, requirement, language)
        
        return JsonResponse({
            "success": True,
            "guide": guide
        })
    
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


@login_required
@require_http_methods(["GET"])
def list_cloud_guides(request):
    """List all available cloud integration guides."""
    try:
        guides = get_all_cloud_guides()
        
        return JsonResponse({
            "success": True,
            "total": len(guides),
            "guides": guides
        })
    
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_integration_checklist(request, provider, slug=None):
    """Get full integration checklist for a cloud provider."""
    try:
        language = request.GET.get("lang", "en")
        
        organization = None
        if slug and hasattr(request, 'current_org'):
            organization = request.current_org
        
        checklist = generate_integration_checklist(provider, organization, language)
        
        return JsonResponse({
            "success": True,
            "checklist": checklist
        })
    
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


# ============================================================================
# COMPLIANCE DASHBOARD & SCORING
# ============================================================================


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_dashboard(request, org_slug: str):
    """
    Get compliance dashboard with KPIs, scores, and recommendations.
    
    GET /api/v1/organizations/{org_slug}/dashboard/
    
    Returns:
    {
        "overall_score": 72,
        "risk_level": "MEDIUM",
        "controls_completed": 42,
        "total_controls": 114,
        "evidence_pending": 3,
        "category_scores": [
            {
                "id": 1,
                "name": "Access Control",
                "score": 85,
                "status": "COMPLIANT"
            }
        ],
        "top_missing_controls": [
            {
                "id": 1,
                "code": "AC-001",
                "title": "User Access Management",
                "score": 20,
                "status": "NON_COMPLIANT",
                "risk_level": "HIGH"
            }
        ]
    }
    """
    try:
        # Verify organization and access
        org = get_object_or_404(Organization, slug=org_slug)
        
        if not request.user.organizations.filter(id=org.id).exists():
            return Response(
                {"error": "You don't have access to this organization"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get KPI data
        kpi_data = get_dashboard_kpis(org)
        
        # Get category scores
        category_scores = get_category_scores(org)
        
        # Format category scores response
        categories_response = []
        for cat, score in category_scores.items():
            categories_response.append({
                'id': cat.id,
                'name': cat.name_en,
                'name_ar': cat.name_ar,
                'code': cat.code,
                'score': score['score'],
                'status': score['status'],
            })
        
        # Format missing controls
        missing_controls_response = []
        for control in kpi_data.get('missing_controls', []):
            missing_controls_response.append({
                'id': control.id,
                'code': control.code,
                'title': control.title_en,
                'title_ar': control.title_ar,
                'score': kpi_data['missing_controls'][control]['score'],
                'status': kpi_data['missing_controls'][control]['status'],
                'risk_level': control.risk_level,
            })
        
        return Response({
            'overall_score': kpi_data['overall_score'],
            'risk_level': kpi_data['risk_level'],
            'controls_completed': kpi_data['controls_completed'],
            'total_controls': Control.objects.count(),
            'evidence_pending': kpi_data['evidence_pending'],
            'category_scores': categories_response,
            'top_missing_controls': missing_controls_response,
            'last_updated': 'now',
        })
        
    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}", exc_info=True)
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================================
# CONTROL DETAILS & ANALYSIS RESULTS
# ============================================================================


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_control_details(request, org_slug: str, control_id: int):
    """
    Get control details with latest analysis results and score.
    
    GET /api/v1/organizations/{org_slug}/controls/{id}/details/
    
    Returns:
    {
        "control": {
            "id": 1,
            "code": "AC-001",
            "title": "User Access Management",
            "category": "Access Control",
            "risk_level": "HIGH",
            "description": "..."
        },
        "score": {
            "score": 20,
            "status": "NON_COMPLIANT",
            "confidence": 95,
            "computed_at": "2026-03-05T10:30:00Z"
        },
        "analysis_results": [
            {
                "id": 1,
                "evidence_id": 42,
                "evidence_filename": "policy.pdf",
                "status": "NON_COMPLIANT",
                "score": 0,
                "confidence": 95,
                "summary": "No evidence of user access management.",
                "summary_ar": "...",
                "missing_points": [...],
                "recommendations": [...],
                "citations": [...],
                "created_at": "2026-03-05T10:30:00Z"
            }
        ]
    }
    """
    try:
        # Verify organization and access
        org = get_object_or_404(Organization, slug=org_slug)
        
        if not request.user.organizations.filter(id=org.id).exists():
            return Response(
                {"error": "You don't have access"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get control
        control = get_object_or_404(Control, id=control_id)
        
        # Get control score
        score_data = compute_control_score(org, control)
        
        # Get analysis results
        results = AIAnalysisResult.objects.filter(
            organization=org,
            control=control
        ).select_related('evidence').order_by('-created_at')
        
        # Format results
        analysis_results = []
        for result in results:
            analysis_results.append({
                'id': result.id,
                'evidence_id': result.evidence.id,
                'evidence_filename': result.evidence.original_filename,
                'status': result.status,
                'score': result.score,
                'confidence': result.confidence,
                'summary': result.summary_en,
                'summary_ar': result.summary_ar,
                'missing_points': result.missing_points or [],
                'recommendations': result.recommendations or [],
                'citations': result.citations or [],
                'created_at': result.created_at.isoformat(),
            })
        
        return Response({
            'control': {
                'id': control.id,
                'code': control.code,
                'title': control.title_en,
                'title_ar': control.title_ar,
                'category': control.category.name_en,
                'risk_level': control.risk_level,
                'description': control.description_en,
                'description_ar': control.description_ar,
            },
            'score': {
                'score': score_data['score'],
                'status': score_data['status'],
                'confidence': score_data['confidence'],
                'computed_at': 'now',
            },
            'analysis_results': analysis_results,
        })
        
    except Exception as e:
        logger.error(f"Control details error: {str(e)}", exc_info=True)
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_controls(request, org_slug: str):
    """
    List all controls with their scores and compliance status.
    
    GET /api/v1/organizations/{org_slug}/controls/
    
    Query parameters:
    - category: Filter by category ID
    - risk_level: Filter by risk level (HIGH, MEDIUM, LOW)
    - status: Filter by score status (COMPLIANT, PARTIAL, NON_COMPLIANT, UNKNOWN)
    - limit: Results per page (default: 50)
    - offset: Pagination offset (default: 0)
    
    Returns:
    {
        "count": 114,
        "results": [
            {
                "id": 1,
                "code": "AC-001",
                "title": "User Access Management",
                "category": "Access Control",
                "risk_level": "HIGH",
                "score": 20,
                "status": "NON_COMPLIANT"
            }
        ]
    }
    """
    try:
        org = get_object_or_404(Organization, slug=org_slug)
        
        if not request.user.organizations.filter(id=org.id).exists():
            return Response(
                {"error": "You don't have access"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get filters
        category_id = request.query_params.get('category')
        risk_level = request.query_params.get('risk_level')
        status_filter = request.query_params.get('status')
        limit = int(request.query_params.get('limit', 50))
        offset = int(request.query_params.get('offset', 0))
        
        # Start with all controls
        queryset = Control.objects.select_related('category').order_by('code')
        
        # Apply filters
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        if risk_level:
            queryset = queryset.filter(risk_level=risk_level)
        
        # Get total count
        total_count = queryset.count()
        
        # Apply pagination
        controls = queryset[offset:offset + limit]
        
        # Build response with scores
        results = []
        for control in controls:
            score_data = compute_control_score(org, control)
            
            # Apply status filter after computing scores
            if status_filter and score_data['status'] != status_filter:
                continue
            
            results.append({
                'id': control.id,
                'code': control.code,
                'title': control.title_en,
                'title_ar': control.title_ar,
                'category': control.category.name_en,
                'risk_level': control.risk_level,
                'score': score_data['score'],
                'status': score_data['status'],
            })
        
        return Response({
            'count': total_count,
            'limit': limit,
            'offset': offset,
            'results': results,
        })
        
    except ValueError:
        return Response(
            {"error": "Invalid query parameters"},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"List controls error: {str(e)}")
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

