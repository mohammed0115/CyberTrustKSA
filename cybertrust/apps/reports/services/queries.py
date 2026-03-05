from __future__ import annotations

from cybertrust.apps.reports.models import Report


def list_reports_for_org(org):
    return Report.objects.filter(organization=org).order_by("-created_at")


def get_report_for_org(org, report_id: int) -> Report | None:
    return Report.objects.filter(organization=org, id=report_id).first()
