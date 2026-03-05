
from __future__ import annotations

import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Organization(models.Model):
    VENDOR_TYPE_GENERAL = "GENERAL"
    VENDOR_TYPE_HIGH_RISK = "HIGH_RISK"
    VENDOR_TYPE_CHOICES = (
        (VENDOR_TYPE_GENERAL, "General Services"),
        (VENDOR_TYPE_HIGH_RISK, "High-Risk Services"),
    )
    
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    industry = models.CharField(max_length=100, blank=True, default="")
    size = models.CharField(max_length=50, blank=True, default="")
    vendor_type = models.CharField(
        max_length=20,
        choices=VENDOR_TYPE_CHOICES,
        default=VENDOR_TYPE_GENERAL,
        help_text="Auto-categorized based on initial assessment"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Membership(models.Model):
    ROLE_ADMIN = "ADMIN"
    ROLE_SECURITY_OFFICER = "SECURITY_OFFICER"
    ROLE_AUDITOR = "AUDITOR"
    ROLE_VIEWER = "VIEWER"

    ROLE_CHOICES = (
        (ROLE_ADMIN, "Admin"),
        (ROLE_SECURITY_OFFICER, "Security Officer"),
        (ROLE_AUDITOR, "Auditor"),
        (ROLE_VIEWER, "Viewer"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=32, choices=ROLE_CHOICES, default=ROLE_VIEWER)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "organization")

    def __str__(self) -> str:
        return f"{self.user} - {self.organization} ({self.role})"


class Invitation(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    role = models.CharField(max_length=32, choices=Membership.ROLE_CHOICES, default=Membership.ROLE_VIEWER)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="sent_invitations"
    )
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["email", "organization"]),
            models.Index(fields=["token"]),
        ]

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @property
    def is_accepted(self) -> bool:
        return self.accepted_at is not None

    @classmethod
    def default_expiry(cls):
        return timezone.now() + timedelta(hours=72)

    def __str__(self) -> str:
        return f"Invite {self.email} to {self.organization}"


class VendorAssessment(models.Model):
    """Initial vendor assessment to determine vendor type (General vs High-Risk)."""
    
    STATUS_PENDING = "PENDING"
    STATUS_COMPLETED = "COMPLETED"
    
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_COMPLETED, "Completed"),
    )
    
    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        related_name="assessment"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    responses = models.JSONField(blank=True, default=dict, help_text="Questionnaire responses")
    vendor_type_determined = models.CharField(
        max_length=20,
        choices=Organization.VENDOR_TYPE_CHOICES,
        default=Organization.VENDOR_TYPE_GENERAL
    )
    risk_score = models.PositiveIntegerField(default=0, help_text="0-100 risk score")
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-created_at"]
    
    def __str__(self) -> str:
        return f"{self.organization.name} - {self.get_status_display()}"


class AssessmentQuestion(models.Model):
    """Dynamic assessment questions."""
    
    question_ar = models.TextField(help_text="Question in Arabic")
    question_en = models.TextField(help_text="Question in English")
    category = models.CharField(
        max_length=50,
        default="general",
        choices=[
            ("general", "General"),
            ("data_protection", "Data Protection"),
            ("infrastructure", "Infrastructure"),
            ("access_control", "Access Control"),
            ("incident_response", "Incident Response"),
        ]
    )
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ["order"]
    
    def __str__(self) -> str:
        return f"{self.category} - {self.question_en[:50]}"
