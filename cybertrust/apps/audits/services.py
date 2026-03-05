from __future__ import annotations

from typing import Any, Mapping

from .models import AuditEvent


def record_event(
    event_type: str,
    *,
    organization=None,
    actor=None,
    message: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> AuditEvent:
    return AuditEvent.objects.create(
        event_type=event_type,
        organization=organization,
        actor=actor,
        message=message or "",
        metadata=dict(metadata) if metadata else None,
    )


def list_recent_events(org=None, limit: int = 5):
    qs = AuditEvent.objects.all()
    if org is not None:
        qs = qs.filter(organization=org)
    return qs.order_by("-created_at")[:limit]
