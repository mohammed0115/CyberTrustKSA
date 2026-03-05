"""
Unit tests for Organizations services: vendor questionnaire.
"""
import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings

from cybertrust.apps.organizations.models import (
    Organization,
    VendorAssessment,
    AssessmentQuestion,
)
from cybertrust.apps.organizations.services import (
    generate_assessment_questions,
    create_assessment_for_organization,
    submit_assessment_response,
    calculate_risk_score,
)


class AssessmentQuestionGenerationTests(TestCase):
    """Test dynamic assessment question generation."""

    @patch("cybertrust.apps.organizations.services.OpenAI")
    def test_generate_questions_with_openai(self, mock_openai):
        """Test generating questions using OpenAI."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps([
            {
                "question_ar": "هل تتعامل مع بيانات حساسة؟",
                "question_en": "Do you handle sensitive data?",
                "category": "data_protection",
                "order": 1
            },
            {
                "question_ar": "هل لديك بنية تحتية سحابية؟",
                "question_en": "Do you have cloud infrastructure?",
                "category": "infrastructure",
                "order": 2
            }
        ])
        mock_client.chat.completions.create.return_value = mock_response
        
        questions = generate_assessment_questions(num_questions=2)
        
        self.assertEqual(len(questions), 2)
        self.assertIn("question_ar", questions[0])
        self.assertIn("question_en", questions[0])
        self.assertEqual(questions[0]["category"], "data_protection")

    @override_settings(OPENAI_API_KEY=None)
    def test_generate_questions_without_api_key(self):
        """Test fallback to default questions when API key missing."""
        questions = generate_assessment_questions(num_questions=5)
        
        self.assertEqual(len(questions), 5)
        self.assertIn("question_ar", questions[0])
        self.assertIn("question_en", questions[0])

    @patch("cybertrust.apps.organizations.services.OpenAI")
    def test_generate_questions_api_error_fallback(self, mock_openai):
        """Test fallback to default questions on API error."""
        mock_openai.side_effect = Exception("API Error")
        
        questions = generate_assessment_questions(num_questions=3)
        
        self.assertEqual(len(questions), 3)
        self.assertIn("question_en", questions[0])

    @patch("cybertrust.apps.organizations.services.OpenAI")
    def test_generate_questions_with_categories(self, mock_openai):
        """Test that generated questions have proper categories."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps([
            {
                "question_ar": "Question about data?",
                "question_en": "Question about data?",
                "category": "data_protection",
                "order": 1
            }
        ])
        mock_client.chat.completions.create.return_value = mock_response
        
        questions = generate_assessment_questions()
        
        valid_categories = [
            "general", "data_protection", "infrastructure",
            "access_control", "incident_response"
        ]
        self.assertIn(questions[0]["category"], valid_categories)


class VendorAssessmentTests(TestCase):
    """Test vendor assessment workflow."""

    def setUp(self):
        self.org = Organization.objects.create(
            name="Test Vendor",
            slug="test-vendor"
        )

    def test_create_assessment(self):
        """Test creating assessment for organization."""
        assessment = create_assessment_for_organization(self.org)
        
        self.assertEqual(assessment.organization, self.org)
        self.assertEqual(assessment.status, VendorAssessment.STATUS_PENDING)

    def test_assessment_uniqueness(self):
        """Test that each org has only one pending assessment."""
        assessment1 = create_assessment_for_organization(self.org)
        assessment2 = create_assessment_for_organization(self.org)
        
        # Should return same assessment
        self.assertEqual(assessment1.id, assessment2.id)

    def test_submit_assessment_general_risk(self):
        """Test assessment result for GENERAL vendor (low risk)."""
        assessment = create_assessment_for_organization(self.org)
        
        # Submit responses with low risk indicators
        responses = {
            1: "no",      # No sensitive data
            2: "no",      # No cloud infrastructure
            3: "no",      # No government data
        }
        
        updated = submit_assessment_response(assessment, responses)
        
        self.assertEqual(updated.status, VendorAssessment.STATUS_COMPLETED)
        self.assertLess(updated.risk_score, 60)
        self.assertEqual(
            updated.vendor_type_determined,
            Organization.VENDOR_TYPE_GENERAL
        )

    def test_submit_assessment_high_risk(self):
        """Test assessment result for HIGH_RISK vendor."""
        assessment = create_assessment_for_organization(self.org)
        
        # Submit responses with high risk indicators
        responses = {
            1: "yes",     # Handles sensitive data
            2: "yes",     # Cloud infrastructure
            3: "yes",     # Government data
        }
        
        updated = submit_assessment_response(assessment, responses)
        
        self.assertEqual(updated.status, VendorAssessment.STATUS_COMPLETED)
        self.assertGreaterEqual(updated.risk_score, 60)
        self.assertEqual(
            updated.vendor_type_determined,
            Organization.VENDOR_TYPE_HIGH_RISK
        )

    def test_assessment_updates_organization_vendor_type(self):
        """Test that assessment updates organization vendor_type."""
        self.assertEqual(
            self.org.vendor_type,
            Organization.VENDOR_TYPE_GENERAL
        )
        
        assessment = create_assessment_for_organization(self.org)
        responses = {1: "yes", 2: "yes", 3: "yes"}
        submit_assessment_response(assessment, responses)
        
        # Refresh from database
        self.org.refresh_from_db()
        self.assertEqual(
            self.org.vendor_type,
            Organization.VENDOR_TYPE_HIGH_RISK
        )

    def test_assessment_completion_timestamp(self):
        """Test that completed_at is set on completion."""
        assessment = create_assessment_for_organization(self.org)
        self.assertIsNone(assessment.completed_at)
        
        responses = {1: "no", 2: "no", 3: "no"}
        updated = submit_assessment_response(assessment, responses)
        
        self.assertIsNotNone(updated.completed_at)


class RiskScoringTests(TestCase):
    """Test risk score calculation."""

    def test_calculate_risk_score_no_responses(self):
        """Test risk score with no responses."""
        score = calculate_risk_score({})
        self.assertEqual(score, 0)

    def test_calculate_risk_score_all_yes(self):
        """Test risk score with all yes/high responses."""
        responses = {
            1: "yes",
            2: "yes",
            3: "yes",
            4: "no",  # MFA implemented (negative risk)
        }
        score = calculate_risk_score(responses)
        self.assertGreater(score, 60)

    def test_calculate_risk_score_all_no(self):
        """Test risk score with all no/low responses."""
        responses = {
            1: "no",
            2: "no",
            3: "no",
            4: "yes",  # MFA implemented
            5: "yes",  # Incident response plan
        }
        score = calculate_risk_score(responses)
        self.assertLess(score, 60)

    def test_calculate_risk_score_numeric_ratings(self):
        """Test risk score with numeric rating responses."""
        # Responses might be numeric (1-10 scale)
        responses = {
            1: 3,  # Low on security measure
            2: 8,  # High on security measure
            3: 5,  # Medium
        }
        score = calculate_risk_score(responses)
        self.assertIsInstance(score, int)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_boundary_score_60(self):
        """Test risk score at boundary (60 = HIGH_RISK)."""
        # Create assessment that scores exactly 60
        assessment = VendorAssessment.objects.create(
            organization=Organization.objects.create(
                name="Boundary Org",
                slug="boundary-org"
            ),
            risk_score=60,
            vendor_type_determined=Organization.VENDOR_TYPE_HIGH_RISK,
            status=VendorAssessment.STATUS_COMPLETED
        )
        
        self.assertEqual(assessment.risk_score, 60)
        self.assertEqual(
            assessment.vendor_type_determined,
            Organization.VENDOR_TYPE_HIGH_RISK
        )


class AssessmentPersistenceTests(TestCase):
    """Test assessment data persistence."""

    def setUp(self):
        self.org = Organization.objects.create(
            name="Test Org",
            slug="test-org"
        )

    def test_responses_persisted_as_json(self):
        """Test that responses are properly stored as JSON."""
        assessment = create_assessment_for_organization(self.org)
        
        responses = {
            1: "yes",
            2: "no",
            3: "sometimes"
        }
        
        updated = submit_assessment_response(assessment, responses)
        
        # Fetch from database and verify JSON preservation
        fetched = VendorAssessment.objects.get(id=updated.id)
        self.assertEqual(fetched.responses["1"], "yes")
        self.assertEqual(fetched.responses["2"], "no")

    def test_assessment_queryset_filtering(self):
        """Test filtering assessments by status."""
        assessment1 = create_assessment_for_organization(self.org)
        
        org2 = Organization.objects.create(name="Org 2", slug="org-2")
        assessment2 = create_assessment_for_organization(org2)
        submit_assessment_response(assessment2, {1: "yes"})
        
        pending = VendorAssessment.objects.filter(
            status=VendorAssessment.STATUS_PENDING
        )
        self.assertEqual(pending.count(), 1)
        self.assertEqual(pending.first().organization, self.org)
        
        completed = VendorAssessment.objects.filter(
            status=VendorAssessment.STATUS_COMPLETED
        )
        self.assertEqual(completed.count(), 1)


class AssessmentQuestionModelTests(TestCase):
    """Test AssessmentQuestion model."""

    def setUp(self):
        self.assessment = VendorAssessment.objects.create(
            organization=Organization.objects.create(
                name="Test Org",
                slug="test-org"
            ),
            status=VendorAssessment.STATUS_PENDING
        )

    def test_create_assessment_question(self):
        """Test creating assessment question."""
        question = AssessmentQuestion.objects.create(
            assessment=self.assessment,
            question_ar="هل تتعامل مع بيانات حساسة؟",
            question_en="Do you handle sensitive data?",
            category="data_protection",
            order=1
        )
        
        self.assertEqual(question.assessment, self.assessment)
        self.assertEqual(question.category, "data_protection")

    def test_question_ordering(self):
        """Test questions maintain order."""
        AssessmentQuestion.objects.create(
            assessment=self.assessment,
            question_ar="Q1 AR",
            question_en="Q1 EN",
            category="category1",
            order=1
        )
        AssessmentQuestion.objects.create(
            assessment=self.assessment,
            question_ar="Q2 AR",
            question_en="Q2 EN",
            category="category2",
            order=2
        )
        
        questions = self.assessment.questions.all()
        self.assertEqual(questions[0].order, 1)
        self.assertEqual(questions[1].order, 2)

    def test_question_categories(self):
        """Test valid question categories."""
        valid_categories = [
            "general",
            "data_protection",
            "infrastructure",
            "access_control",
            "incident_response"
        ]
        
        for idx, cat in enumerate(valid_categories, 1):
            AssessmentQuestion.objects.create(
                assessment=self.assessment,
                question_ar="Q AR",
                question_en="Q EN",
                category=cat,
                order=idx
            )
        
        self.assertEqual(self.assessment.questions.count(), len(valid_categories))


class VendorAssessmentModelTests(TestCase):
    """Test VendorAssessment model."""

    def setUp(self):
        self.org = Organization.objects.create(
            name="Test Org",
            slug="test-org"
        )

    def test_create_vendor_assessment(self):
        """Test creating vendor assessment."""
        assessment = VendorAssessment.objects.create(
            organization=self.org,
            status=VendorAssessment.STATUS_PENDING
        )
        
        self.assertEqual(assessment.organization, self.org)
        self.assertIsNone(assessment.completed_at)

    def test_assessment_status_choices(self):
        """Test assessment status choices."""
        assessment = VendorAssessment.objects.create(
            organization=self.org,
            status=VendorAssessment.STATUS_IN_PROGRESS
        )
        
        self.assertIn(
            assessment.status,
            [VendorAssessment.STATUS_PENDING, VendorAssessment.STATUS_IN_PROGRESS]
        )

    def test_risk_score_range(self):
        """Test risk score is within valid range."""
        assessment = VendorAssessment.objects.create(
            organization=self.org,
            risk_score=50
        )
        
        self.assertGreaterEqual(assessment.risk_score, 0)
        self.assertLessEqual(assessment.risk_score, 100)

    def test_vendor_type_determined(self):
        """Test vendor type determination."""
        assessment = VendorAssessment.objects.create(
            organization=self.org,
            risk_score=75,
            vendor_type_determined=Organization.VENDOR_TYPE_HIGH_RISK
        )
        
        self.assertEqual(
            assessment.vendor_type_determined,
            Organization.VENDOR_TYPE_HIGH_RISK
        )


class IntegrationTests(TestCase):
    """Integration tests for questionnaire workflow."""

    def setUp(self):
        self.org = Organization.objects.create(
            name="Test Vendor",
            slug="test-vendor"
        )

    @patch("cybertrust.apps.organizations.services.OpenAI")
    def test_full_assessment_workflow(self, mock_openai):
        """Test complete assessment workflow from creation to completion."""
        # Generate questions
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps([
            {
                "question_ar": "Q1 AR",
                "question_en": "Q1 EN",
                "category": "data_protection",
                "order": 1
            }
        ])
        mock_client.chat.completions.create.return_value = mock_response
        
        questions = generate_assessment_questions(num_questions=1)
        self.assertEqual(len(questions), 1)
        
        # Create assessment
        assessment = create_assessment_for_organization(self.org)
        self.assertIsNotNone(assessment)
        
        # Submit responses
        responses = {1: "yes"}
        updated = submit_assessment_response(assessment, responses)
        
        self.assertEqual(updated.status, VendorAssessment.STATUS_COMPLETED)
        self.assertIsNotNone(updated.completed_at)

    def test_vendor_type_categorization_workflow(self):
        """Test vendor categorization based on responses."""
        assessment = create_assessment_for_organization(self.org)
        
        # First assessment - low risk
        responses = {1: "no", 2: "no"}
        submit_assessment_response(assessment, responses)
        
        self.org.refresh_from_db()
        self.assertEqual(
            self.org.vendor_type,
            Organization.VENDOR_TYPE_GENERAL
        )
        
        # Create new org for high-risk test
        org2 = Organization.objects.create(
            name="High Risk Vendor",
            slug="high-risk-vendor"
        )
        assessment2 = create_assessment_for_organization(org2)
        responses2 = {1: "yes", 2: "yes", 3: "yes"}
        submit_assessment_response(assessment2, responses2)
        
        org2.refresh_from_db()
        self.assertEqual(
            org2.vendor_type,
            Organization.VENDOR_TYPE_HIGH_RISK
        )
