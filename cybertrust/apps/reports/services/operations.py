from __future__ import annotations

from django.core.files.base import ContentFile
from django.utils import timezone

from cybertrust.apps.audits.services import record_event
from cybertrust.apps.reports.models import Report

from .report_builder import build_report_context, build_report_pdf, render_report_html


def generate_compliance_report(org, created_by=None, report_type: str = Report.TYPE_COMPLIANCE) -> Report:
    now = timezone.now()
    report_name = f"{org.name} Compliance Report {now.strftime('%Y-%m-%d')}"
    report = Report.objects.create(
        organization=org,
        created_by=created_by,
        name=report_name,
        report_type=report_type,
        status=Report.STATUS_GENERATING,
    )

    try:
        context = build_report_context(org)
        html = render_report_html(context)
        pdf_bytes = build_report_pdf(context)
        timestamp = now.strftime("%Y%m%d-%H%M")
        filename = f"{org.slug}-{report_type.lower()}-{timestamp}.pdf"
        report.file.save(filename, ContentFile(pdf_bytes), save=False)
        report.html = html
        report.status = Report.STATUS_READY
        report.generated_at = now
        report.size_bytes = report.file.size if report.file else len(pdf_bytes)
        report.save()
        record_event(
            "REPORT_GENERATED",
            organization=org,
            actor=created_by,
            message=f"Report generated: {report.name}",
            metadata={"report_id": report.id, "report_type": report.report_type},
        )
    except Exception as exc:
        report.status = Report.STATUS_FAILED
        report.meta = {"error": str(exc)}
        report.save(update_fields=["status", "meta"])
        record_event(
            "REPORT_FAILED",
            organization=org,
            actor=created_by,
            message=f"Report failed: {report.name}",
            metadata={"error": str(exc), "report_id": report.id},
        )
        raise

    return report
