"""Evidence App URLs - Evidence management and analysis API endpoints."""
from django.urls import path

from . import views

app_name = "evidence"

urlpatterns = [
    # Evidence upload and listing
    path(
        "api/organizations/<str:org_slug>/evidence/upload/",
        views.upload_evidence,
        name="upload"
    ),
    path(
        "api/organizations/<str:org_slug>/evidence/",
        views.list_evidence,
        name="list"
    ),
    
    # Evidence details and status
    path(
        "api/organizations/<str:org_slug>/evidence/<int:evidence_id>/",
        views.evidence_detail,
        name="detail"
    ),
    path(
        "api/organizations/<str:org_slug>/evidence/<int:evidence_id>/status/",
        views.evidence_status,
        name="status"
    ),
    
    # Control linking and analysis
    path(
        "api/organizations/<str:org_slug>/evidence/<int:evidence_id>/link/",
        views.link_control,
        name="link_control"
    ),
    path(
        "api/organizations/<str:org_slug>/evidence/<int:evidence_id>/analyze/",
        views.trigger_analysis,
        name="analyze"
    ),
    
    # Batch operations
    path(
        "api/organizations/<str:org_slug>/evidence/extract-all/",
        views.extract_all_pending,
        name="extract_all"
    ),
    
    # NCA Compliance Audit
    path(
        "api/organizations/<str:org_slug>/evidence/<int:evidence_id>/nca-audit/",
        views.nca_compliance_audit,
        name="nca_audit"
    ),
    path(
        "api/organizations/<str:org_slug>/nca-audit/<str:task_id>/",
        views.nca_audit_result,
        name="nca_audit_result"
    ),
]
