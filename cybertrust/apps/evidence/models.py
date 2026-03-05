from django.conf import settings
from django.db import models


class Evidence(models.Model):
    FILE_PDF = "PDF"
    FILE_DOCX = "DOCX"
    FILE_IMG = "IMG"
    FILE_OTHER = "OTHER"
    FILE_CHOICES = (
        (FILE_PDF, "PDF"),
        (FILE_DOCX, "DOCX"),
        (FILE_IMG, "Image"),
        (FILE_OTHER, "Other"),
    )

    STATUS_UPLOADED = "UPLOADED"
    STATUS_EXTRACTING = "EXTRACTING"
    STATUS_PROCESSING = "PROCESSING"  # backward compatibility
    STATUS_EXTRACTED = "EXTRACTED"
    STATUS_ANALYZING = "ANALYZING"
    STATUS_ANALYZED = "ANALYZED"
    STATUS_FAILED = "FAILED"
    STATUS_CHOICES = (
        (STATUS_UPLOADED, "Uploaded"),
        (STATUS_EXTRACTING, "Extracting"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_EXTRACTED, "Extracted"),
        (STATUS_ANALYZING, "Analyzing"),
        (STATUS_ANALYZED, "Analyzed"),
        (STATUS_FAILED, "Failed"),
    )

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="evidence")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="evidence")
    file = models.FileField(upload_to="evidence/%Y/%m/")
    original_filename = models.CharField(max_length=255, blank=True, default="")
    file_size = models.BigIntegerField(default=0)
    file_type = models.CharField(max_length=10, choices=FILE_CHOICES, default=FILE_OTHER)
    extracted_text = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_UPLOADED)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.organization_id} - {self.file.name}"

    @property
    def filename(self) -> str:
        if self.original_filename:
            return self.original_filename
        name = self.file.name or ""
        return name.rsplit("/", 1)[-1]


class EvidenceControlLink(models.Model):
    evidence = models.ForeignKey(Evidence, on_delete=models.CASCADE, related_name="control_links")
    control = models.ForeignKey("controls.Control", on_delete=models.CASCADE, related_name="evidence_links")
    linked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("evidence", "control")
        indexes = [
            models.Index(fields=["control", "evidence"]),
        ]

    def __str__(self) -> str:
        return f"{self.evidence_id} -> {self.control.code}"
