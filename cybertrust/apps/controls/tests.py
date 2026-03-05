import tempfile
from pathlib import Path

from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from cybertrust.apps.ai_engine.models import AIAnalysisResult
from cybertrust.apps.controls.models import Control, ControlCategory
from cybertrust.apps.controls.services import compute_overall_score
from cybertrust.apps.evidence.models import Evidence
from cybertrust.apps.organizations.models import Organization
from cybertrust.apps.accounts.models import User

TEMP_MEDIA_ROOT = Path(tempfile.mkdtemp())


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class ControlsImportTests(TestCase):
    def test_import_nca_controls_idempotent(self):
        path = "cybertrust/apps/controls/data/nca_controls_seed.json"
        call_command("import_nca_controls", source=path)
        first_count = Control.objects.count()
        self.assertGreater(first_count, 0)
        call_command("import_nca_controls", source=path)
        second_count = Control.objects.count()
        self.assertEqual(first_count, second_count)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class ScoringTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Org", slug="org")
        self.user = User.objects.create_user(email="user@example.com", password="pass12345")
        self.category = ControlCategory.objects.create(name_ar="الفئة", name_en="Category", order=1)
        self.control = Control.objects.create(
            category=self.category,
            code="NCA-ECC-1.1",
            title_ar="ضابط",
            title_en="Control",
            risk_level=Control.RISK_HIGH,
            required_evidence="Policy",
        )
        file_obj = SimpleUploadedFile("evidence.txt", b"sample text")
        self.evidence = Evidence.objects.create(
            organization=self.org,
            uploaded_by=self.user,
            file=file_obj,
            file_type=Evidence.FILE_OTHER,
            status=Evidence.STATUS_UPLOADED,
        )
        AIAnalysisResult.objects.create(
            organization=self.org,
            evidence=self.evidence,
            control=self.control,
            model_name="mock",
            score=80,
            status=AIAnalysisResult.STATUS_COMPLIANT,
            confidence=90,
        )

    def test_compute_overall_score(self):
        score = compute_overall_score(self.org)
        self.assertEqual(score, 100)
