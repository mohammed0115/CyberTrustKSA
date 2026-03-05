from __future__ import annotations

from typing import Iterable, List

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

from cybertrust.apps.audits.services import record_event
from cybertrust.apps.controls.models import Control
from cybertrust.apps.evidence.models import Evidence, EvidenceControlLink


def _detect_file_type(filename: str) -> str:
    ext = (filename or "").lower().rsplit(".", 1)[-1]
    if ext in {"pdf"}:
        return Evidence.FILE_PDF
    if ext in {"docx"}:
        return Evidence.FILE_DOCX
    if ext in {"png", "jpg", "jpeg", "gif", "bmp"}:
        return Evidence.FILE_IMG
    return Evidence.FILE_OTHER


def _validate_file(file_obj) -> tuple[str, int, str]:
    filename = getattr(file_obj, "name", "") or ""
    size = int(getattr(file_obj, "size", 0) or 0)

    max_size = getattr(settings, "MAX_UPLOAD_SIZE", 25 * 1024 * 1024)
    if size and size > max_size:
        raise ValidationError("File too large. Max size is 25MB.")

    allowed = getattr(
        settings,
        "EVIDENCE_ALLOWED_EXTENSIONS",
        {"pdf", "docx", "png", "jpg", "jpeg"},
    )
    ext = filename.lower().rsplit(".", 1)[-1]
    if ext not in allowed:
        raise ValidationError("Unsupported file type. Allowed: PDF, DOCX, PNG, JPG.")

    file_type = _detect_file_type(filename)
    if file_type == Evidence.FILE_OTHER:
        raise ValidationError("Unsupported file type. Allowed: PDF, DOCX, PNG, JPG.")

    return filename, size, file_type


def _normalize_control_ids(control_ids: Iterable[int] | int | None) -> List[int]:
    if control_ids is None:
        return []
    if isinstance(control_ids, (list, tuple, set)):
        return [int(cid) for cid in control_ids if cid]
    return [int(control_ids)]


def create_evidence(*, organization, uploaded_by, file_obj, control_ids=None) -> Evidence:
    if not file_obj:
        raise ValidationError("Evidence file is required.")

    original_filename, file_size, file_type = _validate_file(file_obj)
    with transaction.atomic():
        evidence = Evidence.objects.create(
            organization=organization,
            uploaded_by=uploaded_by,
            file=file_obj,
            original_filename=original_filename,
            file_size=file_size,
            file_type=file_type,
            status=Evidence.STATUS_UPLOADED,
            error_message="",
        )
        control_ids_list = _normalize_control_ids(control_ids)
        if control_ids_list:
            link_evidence_to_controls(evidence, control_ids_list, linked_by=uploaded_by)

    record_event(
        "evidence.upload",
        organization=organization,
        actor=uploaded_by,
        message=f"Evidence uploaded ({evidence.id}).",
        metadata={"evidence_id": evidence.id, "file_type": file_type},
    )
    return evidence


def link_evidence_to_controls(evidence: Evidence, control_ids, linked_by=None) -> List[EvidenceControlLink]:
    control_ids_list = _normalize_control_ids(control_ids)
    if not control_ids_list:
        return []

    controls = list(Control.objects.filter(id__in=control_ids_list, is_active=True))
    if not controls:
        raise ValidationError("No valid controls selected.")

    links = []
    for control in controls:
        link, _ = EvidenceControlLink.objects.get_or_create(
            evidence=evidence,
            control=control,
            defaults={"linked_by": linked_by},
        )
        links.append(link)
    return links
