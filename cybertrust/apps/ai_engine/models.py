from django.conf import settings
from django.db import models


class ChatMessage(models.Model):
    """Virtual CISO Chatbot conversation history."""
    
    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    
    ROLE_CHOICES = (
        (ROLE_USER, "User"),
        (ROLE_ASSISTANT, "Assistant"),
    )
    
    organization = models.ForeignKey(
        "organizations.Organization", 
        on_delete=models.CASCADE, 
        related_name="chatbot_messages",
        null=True,
        blank=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chatbot_messages",
        null=True,
        blank=True
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    language = models.CharField(max_length=10, default="en", choices=[("ar", "Arabic"), ("en", "English")])
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["organization", "created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]
    
    def __str__(self) -> str:
        return f"{self.role}: {self.content[:50]}..."


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
