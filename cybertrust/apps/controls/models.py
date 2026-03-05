from django.db import models


class ControlCategory(models.Model):
    name_ar = models.CharField(max_length=255)
    name_en = models.CharField(max_length=255)
    code = models.CharField(max_length=50, blank=True, default="")
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "name_en"]

    def __str__(self) -> str:
        return self.name_en


class Control(models.Model):
    RISK_HIGH = "HIGH"
    RISK_MEDIUM = "MEDIUM"
    RISK_LOW = "LOW"
    RISK_CHOICES = (
        (RISK_HIGH, "High"),
        (RISK_MEDIUM, "Medium"),
        (RISK_LOW, "Low"),
    )

    category = models.ForeignKey(ControlCategory, on_delete=models.CASCADE, related_name="controls")
    code = models.CharField(max_length=50, unique=True)
    title_ar = models.CharField(max_length=255)
    title_en = models.CharField(max_length=255)
    description_ar = models.TextField(blank=True, null=True)
    description_en = models.TextField(blank=True, null=True)
    risk_level = models.CharField(max_length=10, choices=RISK_CHOICES, default=RISK_MEDIUM)
    required_evidence = models.TextField(blank=True, default="")
    references = models.JSONField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category__order", "code"]

    def __str__(self) -> str:
        return self.code


class ControlScoreSnapshot(models.Model):
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

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="control_scores")
    control = models.ForeignKey(Control, on_delete=models.CASCADE, related_name="score_snapshots")
    score = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_UNKNOWN)
    computed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-computed_at"]
        indexes = [
            models.Index(fields=["organization", "control", "computed_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.organization_id} - {self.control.code} ({self.score})"
