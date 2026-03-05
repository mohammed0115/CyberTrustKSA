from __future__ import annotations

from celery import shared_task

from cybertrust.apps.ai_engine.services.analyze_control import analyze_evidence_against_control


@shared_task(bind=True)
def analyze_evidence_for_control(self, evidence_id: int, control_id: int) -> None:
    analyze_evidence_against_control(evidence_id, control_id)
