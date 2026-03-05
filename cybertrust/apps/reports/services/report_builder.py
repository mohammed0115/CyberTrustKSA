from __future__ import annotations

import io
from typing import Any

from django.template.loader import render_to_string
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from cybertrust.apps.ai_engine.models import AIAnalysisResult
from cybertrust.apps.controls.models import Control
from cybertrust.apps.controls.services import get_category_scores, get_missing_controls
from cybertrust.apps.controls.services.scoring import compute_overall_score
from cybertrust.apps.evidence.models import Evidence


def build_report_context(org) -> dict[str, Any]:
    total_controls = Control.objects.filter(is_active=True).count()
    completed_controls = (
        AIAnalysisResult.objects.filter(organization=org)
        .values("control")
        .distinct()
        .count()
    )
    evidence_pending = Evidence.objects.filter(
        organization=org,
        status__in=[Evidence.STATUS_UPLOADED, Evidence.STATUS_EXTRACTING, Evidence.STATUS_PROCESSING],
    ).count()

    overall_score = compute_overall_score(org)
    category_scores = get_category_scores(org)
    missing_controls = get_missing_controls(org, limit=8)

    return {
        "org": org,
        "generated_at": timezone.now(),
        "overall_score": overall_score,
        "total_controls": total_controls,
        "completed_controls": completed_controls,
        "evidence_pending": evidence_pending,
        "category_scores": category_scores,
        "missing_controls": missing_controls,
    }


def render_report_html(context: dict[str, Any]) -> str:
    return render_to_string("reports/compliance_report.html", context)


def build_report_pdf(context: dict[str, Any]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
        title="NCA Compliance Report",
    )

    styles = getSampleStyleSheet()
    story: list[Any] = []

    org = context["org"]
    generated_at = context["generated_at"].strftime("%Y-%m-%d %H:%M")
    story.append(Paragraph("NCA Compliance Report", styles["Title"]))
    story.append(Paragraph(f"Organization: {org.name}", styles["Normal"]))
    story.append(Paragraph(f"Generated at: {generated_at}", styles["Normal"]))
    story.append(Spacer(1, 12))

    kpi_data = [
        ["Compliance Score", f"{context['overall_score']}%"],
        [
            "Controls Completed",
            f"{context['completed_controls']}/{context['total_controls']}",
        ],
        ["Evidence Pending", str(context["evidence_pending"])],
    ]
    kpi_table = Table([["KPI", "Value"]] + kpi_data, colWidths=[8 * cm, 5 * cm])
    kpi_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    story.append(kpi_table)
    story.append(Spacer(1, 16))

    story.append(Paragraph("Category Scores", styles["Heading2"]))
    category_rows = [["Category", "Score"]]
    for row in context["category_scores"]:
        category = row["category"]
        category_rows.append([category.name_en or category.name_ar, f"{row['score']}%"])
    if len(category_rows) == 1:
        category_rows.append(["No categories", "0%"])
    category_table = Table(category_rows, colWidths=[9 * cm, 4 * cm])
    category_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#ffffff")),
            ]
        )
    )
    story.append(category_table)
    story.append(Spacer(1, 16))

    story.append(Paragraph("Top Missing Controls", styles["Heading2"]))
    missing_rows = [["Code", "Title", "Score"]]
    for control, score, _status in context["missing_controls"]:
        title = control.title_en or control.title_ar or ""
        missing_rows.append([control.code, title, f"{score}%"])
    if len(missing_rows) == 1:
        missing_rows.append(["-", "No missing controls", "-"])
    missing_table = Table(missing_rows, colWidths=[4 * cm, 8 * cm, 3 * cm])
    missing_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
            ]
        )
    )
    story.append(missing_table)

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
