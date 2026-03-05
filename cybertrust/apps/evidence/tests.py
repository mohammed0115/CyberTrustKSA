import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from cybertrust.apps.controls.models import Control, ControlCategory
from cybertrust.apps.evidence.models import EvidenceControlLink
from cybertrust.apps.evidence.services import create_evidence
from cybertrust.apps.organizations.models import Organization
from cybertrust.apps.accounts.models import User

TEMP_MEDIA_ROOT = Path(tempfile.mkdtemp())


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class EvidenceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Org", slug="org")
        self.user = User.objects.create_user(email="user@example.com", password="pass12345")
        self.category = ControlCategory.objects.create(name_ar="الفئة", name_en="Category", order=1)
        self.control = Control.objects.create(
            category=self.category,
            code="NCA-ECC-1.1",
            title_ar="ضابط",
            title_en="Control",
            risk_level=Control.RISK_LOW,
            required_evidence="Policy",
        )

    def test_create_evidence_and_link(self):
        file_obj = SimpleUploadedFile("evidence.pdf", b"%PDF-1.4 sample evidence", content_type="application/pdf")
        evidence = create_evidence(
            organization=self.org,
            uploaded_by=self.user,
            file_obj=file_obj,
            control_ids=[self.control.id],
        )
        self.assertIsNotNone(evidence.id)
        self.assertEqual(EvidenceControlLink.objects.count(), 1)
