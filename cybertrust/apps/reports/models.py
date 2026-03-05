from __future__ import annotations

from django.conf import settings
from django.db import models

from cybertrust.apps.organizations.models import Organization


class Report(models.Model):
    TYPE_COMPLIANCE = "COMPLIANCE"
    TYPE_RISK = "RISK"
    TYPE_SUMMARY = "SUMMARY"

    REPORT_TYPE_CHOICES = (
        (TYPE_COMPLIANCE, "Compliance"),
        (TYPE_RISK, "Risk"),
        (TYPE_SUMMARY, "Summary"),
    )

    STATUS_GENERATING = "GENERATING"
    STATUS_READY = "READY"
    STATUS_FAILED = "FAILED"

    STATUS_CHOICES = (
        (STATUS_GENERATING, "Generating"),
        (STATUS_READY, "Ready"),
        (STATUS_FAILED, "Failed"),
    )

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="reports")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_reports",
    )
    name = models.CharField(max_length=255)
    report_type = models.CharField(max_length=32, choices=REPORT_TYPE_CHOICES, default=TYPE_COMPLIANCE)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_GENERATING)
    file = models.FileField(upload_to="reports/%Y/%m/", null=True, blank=True)
    size_bytes = models.PositiveIntegerField(default=0)
    html = models.TextField(blank=True, default="")
    meta = models.JSONField(null=True, blank=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.organization} - {self.name}"

    @property
    def size_display(self) -> str:
        if not self.size_bytes:
            return "-"
        size = float(self.size_bytes)
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024.0:
                return f"{size:.1f}{unit}"
            size /= 1024.0
        return f"{size:.1f}TB"
