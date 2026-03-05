from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="audit_events", null=True, blank=True
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="audit_events", null=True, blank=True
    )
    event_type = models.CharField(max_length=100)
    message = models.TextField(blank=True, default="")
    metadata = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "event_type", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} ({self.created_at:%Y-%m-%d})"
