import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from cybertrust.apps.accounts.models import User
from cybertrust.apps.controls.models import Control, ControlCategory
from cybertrust.apps.evidence.models import Evidence
from cybertrust.apps.evidence.services import create_evidence
from cybertrust.apps.organizations.models import Membership, Organization
from cybertrust.apps.ai_engine.models import AIAnalysisResult

TEMP_MEDIA_ROOT = Path(tempfile.mkdtemp())


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT, CELERY_TASK_ALWAYS_EAGER=True)
class WebuiEvidenceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Org", slug="org")
        self.admin_user = User.objects.create_user(email="admin@example.com", password="pass12345")
        self.viewer_user = User.objects.create_user(email="viewer@example.com", password="pass12345")
        Membership.objects.create(user=self.admin_user, organization=self.org, role=Membership.ROLE_ADMIN)
        Membership.objects.create(user=self.viewer_user, organization=self.org, role=Membership.ROLE_VIEWER)

        self.category = ControlCategory.objects.create(name_ar="الفئة", name_en="Category", order=1)
        self.control = Control.objects.create(
            category=self.category,
            code="NCA-ECC-1.1",
            title_ar="ضابط",
            title_en="Control",
            risk_level=Control.RISK_LOW,
            required_evidence="Policy",
        )

    def _pdf_file(self, name="sample.pdf"):
        return SimpleUploadedFile(name, b"%PDF-1.4 sample content", content_type="application/pdf")

    def test_upload_creates_evidence(self):
        self.client.force_login(self.admin_user)
        url = reverse("webui:evidence_upload", kwargs={"slug": self.org.slug})
        response = self.client.post(url, {"file": self._pdf_file(), "control_id": str(self.control.id)})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Evidence.objects.filter(organization=self.org).exists())

    def test_analyze_endpoint_creates_result(self):
        evidence = create_evidence(
            organization=self.org,
            uploaded_by=self.admin_user,
            file_obj=self._pdf_file(),
            control_ids=[self.control.id],
        )
        evidence.extracted_text = "A" * 80
        evidence.save(update_fields=["extracted_text"])

        with patch("cybertrust.apps.ai_engine.services.analyze_control.analyze_control_text") as mock_ai:
            mock_ai.return_value = {
                "status": "COMPLIANT",
                "score": 95,
                "confidence": 90,
                "missing_points": [],
                "recommendations": [],
                "citations": [],
                "summary_ar": "",
                "summary_en": "",
                "model_name": "test",
            }
            self.client.force_login(self.admin_user)
            url = reverse(
                "webui:evidence_analyze",
                kwargs={"slug": self.org.slug, "evidence_id": evidence.id, "control_id": self.control.id},
            )
            response = self.client.post(url)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(AIAnalysisResult.objects.filter(evidence=evidence, control=self.control).exists())

    def test_viewer_cannot_upload_or_analyze(self):
        self.client.force_login(self.viewer_user)
        url = reverse("webui:evidence_upload", kwargs={"slug": self.org.slug})
        response = self.client.post(url, {"file": self._pdf_file()})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Evidence.objects.filter(organization=self.org).exists())

        evidence = create_evidence(
            organization=self.org,
            uploaded_by=self.admin_user,
            file_obj=self._pdf_file("viewer.pdf"),
            control_ids=[self.control.id],
        )
        analyze_url = reverse(
            "webui:evidence_analyze",
            kwargs={"slug": self.org.slug, "evidence_id": evidence.id, "control_id": self.control.id},
        )
        response = self.client.post(analyze_url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AIAnalysisResult.objects.filter(evidence=evidence).exists())
