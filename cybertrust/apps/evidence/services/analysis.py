from __future__ import annotations

from typing import Iterable

from django.conf import settings

from cybertrust.apps.ai_engine.tasks import analyze_evidence_for_control


def enqueue_analysis(evidence_id: int, control_ids: Iterable[int]) -> None:
    for control_id in control_ids:
        if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
            analyze_evidence_for_control(evidence_id, control_id)
            continue
        try:
            analyze_evidence_for_control.delay(evidence_id, control_id)
        except Exception:
            analyze_evidence_for_control(evidence_id, control_id)
