from __future__ import annotations

from django.db.models import QuerySet

from cybertrust.apps.evidence.models import Evidence
from cybertrust.apps.evidence.models import EvidenceControlLink


def get_evidence_for_org(org, evidence_id: int) -> Evidence | None:
    return Evidence.objects.filter(id=evidence_id, organization=org).first()


def list_org_evidence(org) -> QuerySet[Evidence]:
    return (
        Evidence.objects.filter(organization=org)
        .select_related("uploaded_by")
        .prefetch_related("control_links__control", "ai_results")
        .order_by("-created_at")
    )


def list_links_for_evidence(evidence: Evidence):
    return EvidenceControlLink.objects.filter(evidence=evidence).select_related("control")


def list_links_for_control(org, control):
    return (
        EvidenceControlLink.objects.filter(control=control, evidence__organization=org)
        .select_related("evidence", "evidence__uploaded_by")
        .order_by("-created_at")
    )
