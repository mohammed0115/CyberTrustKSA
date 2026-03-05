from __future__ import annotations

from django.db.models import QuerySet

from cybertrust.apps.ai_engine.models import AIAnalysisResult


def list_results_for_evidence(evidence) -> QuerySet[AIAnalysisResult]:
    return AIAnalysisResult.objects.filter(evidence=evidence).select_related("control")


def latest_result_for_control(org, control):
    return (
        AIAnalysisResult.objects.filter(organization=org, control=control)
        .order_by("-created_at")
        .first()
    )
