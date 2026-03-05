from __future__ import annotations

import logging

from django.db import transaction

from cybertrust.apps.audits.services import record_event
from cybertrust.apps.ai_engine.models import AIAnalysisResult
from cybertrust.apps.ai_engine.services.extractors import (
    extract_text_from_docx,
    extract_text_from_image,
    extract_text_from_pdf,
)
from cybertrust.apps.ai_engine.services.openai_client import analyze_control_text, build_unknown_result
from cybertrust.apps.controls.models import Control, ControlScoreSnapshot
from cybertrust.apps.controls.services.scoring import STATUS_SCORE_MAP
from cybertrust.apps.evidence.models import Evidence, EvidenceControlLink

logger = logging.getLogger("ai_engine")


def _extract_text(evidence: Evidence) -> str:
    path = evidence.file.path
    if evidence.file_type == Evidence.FILE_PDF:
        return extract_text_from_pdf(path)
    if evidence.file_type == Evidence.FILE_DOCX:
        return extract_text_from_docx(path)
    if evidence.file_type == Evidence.FILE_IMG:
        return extract_text_from_image(path)
    return ""


def _update_evidence_status(evidence: Evidence) -> None:
    linked = EvidenceControlLink.objects.filter(evidence=evidence).count()
    if not linked:
        return
    analyzed = (
        AIAnalysisResult.objects.filter(evidence=evidence)
        .values("control")
        .distinct()
        .count()
    )
    if analyzed >= linked:
        evidence.status = Evidence.STATUS_ANALYZED
        evidence.save(update_fields=["status", "updated_at"])
    else:
        evidence.status = Evidence.STATUS_ANALYZING
        evidence.save(update_fields=["status", "updated_at"])


def analyze_evidence_against_control(evidence_id: int, control_id: int) -> None:
    evidence = Evidence.objects.select_related("organization").filter(id=evidence_id).first()
    control = Control.objects.filter(id=control_id).first()
    if not evidence or not control:
        return

    evidence.status = Evidence.STATUS_EXTRACTING
    evidence.error_message = ""
    evidence.save(update_fields=["status", "error_message", "updated_at"])

    record_event(
        "analysis.started",
        organization=evidence.organization,
        actor=evidence.uploaded_by,
        message=f"Analysis started for evidence {evidence_id} / control {control.code}",
        metadata={"evidence_id": evidence_id, "control_id": control_id},
    )

    try:
        text = evidence.extracted_text
        if not text:
            text = _extract_text(evidence)
            evidence.extracted_text = text
        evidence.status = Evidence.STATUS_EXTRACTED
        evidence.save(update_fields=["extracted_text", "status", "updated_at"])

        if not text or len(text) < 50:
            result_data = build_unknown_result("Evidence text is insufficient.")
        else:
            evidence.status = Evidence.STATUS_ANALYZING
            evidence.save(update_fields=["status", "updated_at"])
            result_data = analyze_control_text(text, control)

        with transaction.atomic():
            AIAnalysisResult.objects.create(
                organization=evidence.organization,
                evidence=evidence,
                control=control,
                model_name=result_data.get("model_name") or "openai",
                score=int(result_data.get("score", 0)),
                status=result_data.get("status", AIAnalysisResult.STATUS_UNKNOWN),
                confidence=int(result_data.get("confidence", 0)),
                missing_points=result_data.get("missing_points"),
                recommendations=result_data.get("recommendations"),
                citations=result_data.get("citations"),
                raw_json=result_data,
                summary_ar=result_data.get("summary_ar"),
                summary_en=result_data.get("summary_en"),
            )
            mapped_score = STATUS_SCORE_MAP.get(
                result_data.get("status", ControlScoreSnapshot.STATUS_UNKNOWN),
                STATUS_SCORE_MAP[ControlScoreSnapshot.STATUS_UNKNOWN],
            )
            ControlScoreSnapshot.objects.create(
                organization=evidence.organization,
                control=control,
                score=int(mapped_score),
                status=result_data.get("status", ControlScoreSnapshot.STATUS_UNKNOWN),
            )

        _update_evidence_status(evidence)
        record_event(
            "analysis.completed",
            organization=evidence.organization,
            actor=evidence.uploaded_by,
            message=f"Analysis completed for evidence {evidence_id} / control {control.code}",
            metadata={"evidence_id": evidence_id, "control_id": control_id},
        )
    except Exception as exc:  # pragma: no cover
        logger.exception("AI analysis failed for evidence %s", evidence_id)
        evidence.status = Evidence.STATUS_FAILED
        evidence.error_message = str(exc)
        evidence.save(update_fields=["status", "error_message", "updated_at"])
        record_event(
            "analysis.failed",
            organization=evidence.organization,
            actor=evidence.uploaded_by,
            message=str(exc),
            metadata={"evidence_id": evidence_id, "control_id": control_id},
        )
