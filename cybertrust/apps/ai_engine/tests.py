import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from cybertrust.apps.ai_engine.models import AIAnalysisResult
from cybertrust.apps.ai_engine.services.analyze_control import analyze_evidence_against_control
from cybertrust.apps.ai_engine.tasks import analyze_evidence_for_control
from cybertrust.apps.controls.models import Control, ControlCategory, ControlScoreSnapshot
from cybertrust.apps.evidence.models import Evidence, EvidenceControlLink
from cybertrust.apps.evidence.services import create_evidence
from cybertrust.apps.organizations.models import Organization
from cybertrust.apps.accounts.models import User

TEMP_MEDIA_ROOT = Path(tempfile.mkdtemp())


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class AIAnalysisTaskTests(TestCase):
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
        file_obj = SimpleUploadedFile("evidence.txt", b"sample evidence text")
        self.evidence = Evidence.objects.create(
            organization=self.org,
            uploaded_by=self.user,
            file=file_obj,
            file_type=Evidence.FILE_OTHER,
            status=Evidence.STATUS_UPLOADED,
        )
        EvidenceControlLink.objects.create(evidence=self.evidence, control=self.control, linked_by=self.user)

    def test_task_creates_analysis_result(self):
        analyze_evidence_for_control(self.evidence.id, self.control.id)
        self.assertTrue(AIAnalysisResult.objects.filter(evidence=self.evidence, control=self.control).exists())
        self.assertTrue(ControlScoreSnapshot.objects.filter(control=self.control, organization=self.org).exists())
        self.evidence.refresh_from_db()
        self.assertEqual(self.evidence.status, Evidence.STATUS_ANALYZED)

    def test_docx_extraction_sets_text(self):
        try:
            import docx
        except Exception:  # pragma: no cover
            self.skipTest("python-docx not available")

        doc = docx.Document()
        doc.add_paragraph("Policy statement for access control.")
        doc_path = TEMP_MEDIA_ROOT / "sample.docx"
        doc.save(doc_path)

        file_obj = SimpleUploadedFile("sample.docx", doc_path.read_bytes(), content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        evidence = create_evidence(
            organization=self.org,
            uploaded_by=self.user,
            file_obj=file_obj,
            control_ids=[self.control.id],
        )

        with patch("cybertrust.apps.ai_engine.services.analyze_control.analyze_control_text") as mock_ai:
            mock_ai.return_value = {
                "status": "COMPLIANT",
                "score": 90,
                "confidence": 80,
                "missing_points": [],
                "recommendations": [],
                "citations": [],
                "summary_ar": "",
                "summary_en": "",
                "model_name": "test",
            }
            analyze_evidence_against_control(evidence.id, self.control.id)

        evidence.refresh_from_db()
        self.assertTrue(evidence.extracted_text)
