from __future__ import annotations

from typing import Iterable

from django.db.models import Count, Q

from cybertrust.apps.ai_engine.models import AIAnalysisResult
from cybertrust.apps.controls.models import Control, ControlCategory
from cybertrust.apps.evidence.models import Evidence

STATUS_SCORE_MAP = {
    AIAnalysisResult.STATUS_COMPLIANT: 100,
    AIAnalysisResult.STATUS_PARTIAL: 60,
    AIAnalysisResult.STATUS_NON_COMPLIANT: 0,
    AIAnalysisResult.STATUS_UNKNOWN: 20,
}

RISK_WEIGHTS = {
    Control.RISK_HIGH: 1.5,
    Control.RISK_MEDIUM: 1.0,
    Control.RISK_LOW: 0.7,
}


def _latest_result(org, control: Control) -> AIAnalysisResult | None:
    return (
        AIAnalysisResult.objects.filter(organization=org, control=control)
        .order_by("-created_at")
        .first()
    )


def compute_control_score(org, control: Control) -> dict:
    result = _latest_result(org, control)
    if not result:
        return {"score": STATUS_SCORE_MAP[AIAnalysisResult.STATUS_UNKNOWN], "status": AIAnalysisResult.STATUS_UNKNOWN, "confidence": 0}
    score = STATUS_SCORE_MAP.get(result.status, STATUS_SCORE_MAP[AIAnalysisResult.STATUS_UNKNOWN])
    return {"score": score, "status": result.status, "confidence": result.confidence}


def compute_category_score(org, category: ControlCategory) -> int:
    controls = Control.objects.filter(category=category, is_active=True)
    total = 0.0
    weight_sum = 0.0
    for control in controls:
        weight = RISK_WEIGHTS.get(control.risk_level, 1.0)
        score = compute_control_score(org, control)["score"]
        total += score * weight
        weight_sum += weight
    if weight_sum == 0:
        return 0
    return round(total / weight_sum)


def compute_overall_score(org) -> int:
    controls = Control.objects.filter(is_active=True)
    total = 0.0
    weight_sum = 0.0
    for control in controls:
        weight = RISK_WEIGHTS.get(control.risk_level, 1.0)
        score = compute_control_score(org, control)["score"]
        total += score * weight
        weight_sum += weight
    if weight_sum == 0:
        return 0
    return round(total / weight_sum)


def get_controls_overview(org):
    controls = (
        Control.objects.filter(is_active=True)
        .select_related("category")
        .annotate(
            evidence_count=Count(
                "evidence_links",
                filter=Q(evidence_links__evidence__organization=org),
                distinct=True,
            )
        )
    )
    rows = []
    for control in controls:
        latest = _latest_result(org, control)
        rows.append(
            {
                "control": control,
                "score": latest.score if latest else 0,
                "status": latest.status if latest else AIAnalysisResult.STATUS_UNKNOWN,
                "confidence": latest.confidence if latest else 0,
                "evidence_count": control.evidence_count,
            }
        )
    return rows


def get_category_scores(org):
    categories = ControlCategory.objects.all().order_by("order", "name_en")
    rows = []
    for category in categories:
        rows.append(
            {
                "category": category,
                "score": compute_category_score(org, category),
            }
        )
    return rows


def get_missing_controls(org, limit: int = 5):
    controls = Control.objects.filter(is_active=True)
    missing = []
    for control in controls:
        latest = _latest_result(org, control)
        score = STATUS_SCORE_MAP.get(latest.status, STATUS_SCORE_MAP[AIAnalysisResult.STATUS_UNKNOWN]) if latest else STATUS_SCORE_MAP[AIAnalysisResult.STATUS_UNKNOWN]
        status = latest.status if latest else AIAnalysisResult.STATUS_UNKNOWN
        if score < 50 or status == AIAnalysisResult.STATUS_UNKNOWN:
            missing.append((control, score, status))
    missing.sort(key=lambda item: (RISK_WEIGHTS.get(item[0].risk_level, 1.0) * -1, item[1]))
    return missing[:limit]


def get_dashboard_kpis(org):
    overall = compute_overall_score(org)
    completed = (
        AIAnalysisResult.objects.filter(organization=org)
        .values("control")
        .distinct()
        .count()
    )
    evidence_pending = Evidence.objects.filter(
        organization=org,
        status__in=[Evidence.STATUS_UPLOADED, Evidence.STATUS_EXTRACTING, Evidence.STATUS_PROCESSING],
    ).count()

    if overall >= 80:
        risk_level = "LOW"
    elif overall >= 50:
        risk_level = "MEDIUM"
    else:
        risk_level = "HIGH"

    missing_controls = get_missing_controls(org, limit=5)
    return {
        "overall_score": overall,
        "controls_completed": completed,
        "evidence_pending": evidence_pending,
        "risk_level": risk_level,
        "missing_controls": missing_controls,
    }
