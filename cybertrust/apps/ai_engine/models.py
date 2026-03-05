from django.db import models


class AIAnalysisResult(models.Model):
    STATUS_COMPLIANT = "COMPLIANT"
    STATUS_PARTIAL = "PARTIAL"
    STATUS_NON_COMPLIANT = "NON_COMPLIANT"
    STATUS_UNKNOWN = "UNKNOWN"

    STATUS_CHOICES = (
        (STATUS_COMPLIANT, "Compliant"),
        (STATUS_PARTIAL, "Partial"),
        (STATUS_NON_COMPLIANT, "Non Compliant"),
        (STATUS_UNKNOWN, "Unknown"),
    )

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="ai_results")
    evidence = models.ForeignKey("evidence.Evidence", on_delete=models.CASCADE, related_name="ai_results")
    control = models.ForeignKey("controls.Control", on_delete=models.CASCADE, related_name="ai_results")
    model_name = models.CharField(max_length=120)
    score = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_UNKNOWN)
    confidence = models.PositiveIntegerField(default=0)
    missing_points = models.JSONField(blank=True, null=True)
    recommendations = models.JSONField(blank=True, null=True)
    citations = models.JSONField(blank=True, null=True)
    raw_json = models.JSONField(blank=True, null=True)
    summary_ar = models.TextField(blank=True, null=True)
    summary_en = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "control", "created_at"]),
            models.Index(fields=["evidence", "control"]),
        ]

    def __str__(self) -> str:
        return f"{self.control.code} ({self.score})"
