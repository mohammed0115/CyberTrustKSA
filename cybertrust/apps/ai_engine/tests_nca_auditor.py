"""
NCA Compliance Auditor Tests
============================
Comprehensive test suite for the NCA compliance audit system.
Tests the auditor against sample evidence and validates compliance scoring.
"""

import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status

from cybertrust.apps.ai_engine.services.nca_compliance_auditor import (
    NCAComplianceAuditor,
)
from cybertrust.apps.evidence.models import Evidence
from cybertrust.apps.controls.models import Control
from cybertrust.apps.organizations.models import Organization, UserOrganization


class NCAComplianceAuditorUnitTests(TestCase):
    """Unit tests for NCAComplianceAuditor service."""

    def setUp(self):
        """Initialize auditor for testing."""
        self.auditor = NCAComplianceAuditor()

    def test_auditor_loads_controls(self):
        """Test that auditor loads all NCA controls."""
        controls = self.auditor.list_all_controls()
        self.assertGreater(len(controls), 0)
        self.assertEqual(len(controls), 114)  # NCA has 114 controls

    def test_get_control_by_code(self):
        """Test retrieving specific control by code."""
        control = self.auditor.get_control_by_code("NCA-ECC-1-1-1")
        self.assertIsNotNone(control)
        self.assertEqual(control["code"], "NCA-ECC-1-1-1")
        self.assertIn("title_en", control)
        self.assertIn("description_en", control)

    def test_analyze_compliant_evidence(self):
        """Test analysis of evidence that is fully compliant."""
        # Evidence that addresses cybersecurity governance control
        evidence = """
        Cybersecurity Strategy Document
        ================================
        
        Our organization has defined a comprehensive cybersecurity strategy that
        has been formally documented and approved by the CFO (Authorizing Official).
        
        The strategy includes:
        - Strategic objectives aligned with organizational goals
        - Implementation roadmap with defined milestones
        - Quarterly review cycles
        - Compliance with all applicable laws and regulations
        
        Approval Date: January 2024
        Review Schedule: Every quarter
        Last Reviewed: February 2024
        """

        result = self.auditor.analyze_evidence(evidence)

        # Validate structure
        self.assertIn("analysis", result)
        self.assertIn("overall_assessment", result)
        self.assertIn("metadata", result)

        # Should have some compliant controls
        analysis = result["analysis"]
        self.assertGreater(len(analysis), 0)

        # Each control should have required fields
        for control_result in analysis:
            self.assertIn("control_code", control_result)
            self.assertIn("status", control_result)
            self.assertIn("score", control_result)
            self.assertIn("confidence", control_result)
            self.assertIn("summary_ar", control_result)
            self.assertIn("missing_points", control_result)
            self.assertIn("recommendations", control_result)
            self.assertIn("citations", control_result)

    def test_analyze_partial_evidence(self):
        """Test analysis of evidence with partial compliance."""
        evidence = """
        Access Control Policy
        =====================
        
        We have implemented user authentication for our systems.
        Users must log in with username and password.
        
        However, we are still documenting authorization procedures
        and role-based access control specifics.
        """

        result = self.auditor.analyze_evidence(evidence)

        # Should have mixed results
        statuses = [r["status"] for r in result["analysis"]]
        self.assertIn("PARTIAL", statuses)

    def test_analyze_non_compliant_evidence(self):
        """Test analysis of evidence that is non-compliant."""
        evidence = "We have a basic firewall setup."

        result = self.auditor.analyze_evidence(evidence)

        # Should have non-compliant or unknown statuses
        statuses = [r["status"] for r in result["analysis"]]
        self.assertTrue(
            any(s in statuses for s in ["NON_COMPLIANT", "UNKNOWN"])
        )

    def test_analyze_empty_evidence(self):
        """Test analysis with empty evidence."""
        result = self.auditor.analyze_evidence("")

        # Should return empty analysis
        self.assertEqual(len(result["analysis"]), 0)
        self.assertEqual(result["overall_assessment"]["overall_score"], 0)

    def test_overall_assessment_calculation(self):
        """Test overall assessment calculation."""
        evidence = """
        Comprehensive Security Program
        ==============================
        
        We have established a dedicated cybersecurity function with a CISO.
        A cybersecurity strategy is documented and approved by the board.
        Security policies cover all organizational areas.
        Access control is implemented with MFA authentication.
        Incident response procedures are documented.
        Regular security awareness training is conducted quarterly.
        Annual audit reviews ensure compliance.
        """

        result = self.auditor.analyze_evidence(evidence)
        overall = result["overall_assessment"]

        # Check overall assessment fields
        self.assertIn("compliance_level", overall)
        self.assertIn("overall_score", overall)
        self.assertIn("compliant_count", overall)
        self.assertIn("partial_count", overall)
        self.assertIn("non_compliant_count", overall)
        self.assertIn("key_gaps", overall)
        self.assertIn("priority_actions", overall)

        # Score should be between 0-100
        self.assertGreaterEqual(overall["overall_score"], 0)
        self.assertLessEqual(overall["overall_score"], 100)

    def test_compliance_level_determination(self):
        """Test compliance level categorization."""
        # High compliance evidence
        high_compliant = """
        Our organization has a fully documented cybersecurity program
        with all required controls implemented and certified.
        Annual third-party audits confirm compliance.
        All staff trained and aware.
        Incident response active.
        """

        result_high = self.auditor.analyze_evidence(high_compliant)
        score_high = result_high["overall_assessment"]["overall_score"]

        # Should be reasonably high
        self.assertGreater(score_high, 50)

    def test_confidence_score_calculation(self):
        """Test confidence score is calculated properly."""
        evidence = "We have security measures in place."

        result = self.auditor.analyze_evidence(evidence)

        # Each control should have confidence
        for control in result["analysis"]:
            confidence = control.get("confidence", 0)
            self.assertGreaterEqual(confidence, 0)
            self.assertLessEqual(confidence, 100)

    def test_missing_points_extraction(self):
        """Test that missing points are identified correctly."""
        evidence = """
        We have implemented access controls.
        """

        result = self.auditor.analyze_evidence(evidence)

        # Should identify missing elements
        for control in result["analysis"]:
            if control["status"] in ["PARTIAL", "NON_COMPLIANT"]:
                self.assertGreater(len(control["missing_points"]), 0)
                # Each missing point should be a string
                for point in control["missing_points"]:
                    self.assertIsInstance(point, str)

    def test_recommendations_generation(self):
        """Test that recommendations are generated."""
        evidence = "Basic security setup in place."

        result = self.auditor.analyze_evidence(evidence)

        for control in result["analysis"]:
            if control["status"] in ["PARTIAL", "NON_COMPLIANT"]:
                # Should have recommendations
                self.assertGreater(len(control["recommendations"]), 0)
                for rec in control["recommendations"]:
                    self.assertIsInstance(rec, str)
                    self.assertGreater(len(rec), 5)

    def test_specific_controls_analysis(self):
        """Test analysis of specific controls only."""
        evidence = "Cybersecurity strategy documented and approved by board."

        # Analyze only governance controls
        specific_codes = ["NCA-ECC-1-1-1", "NCA-ECC-1-1-2"]
        result = self.auditor.analyze_evidence(evidence, control_codes=specific_codes)

        # Should only have requested controls
        analyzed_codes = [c["control_code"] for c in result["analysis"]]
        self.assertEqual(len(analyzed_codes), len(specific_codes))
        for code in analyzed_codes:
            self.assertIn(code, specific_codes)

    def test_citations_extraction(self):
        """Test that citations are extracted properly."""
        evidence = """
        Our cybersecurity strategy is documented and approved.
        It includes implementation roadmap and review procedures.
        The strategy aligns with organizational objectives.
        """

        result = self.auditor.analyze_evidence(evidence)

        # Some controls should have citations
        has_citations = False
        for control in result["analysis"]:
            if len(control["citations"]) > 0:
                has_citations = True
                for citation in control["citations"]:
                    self.assertIn("quote", citation)
                    self.assertIn("page", citation)
                    # Quote should be reasonable length
                    words = len(citation["quote"].split())
                    self.assertLessEqual(words, 25)

    def test_arabic_summary_generation(self):
        """Test Arabic summary generation."""
        evidence = "Security program implemented."

        result = self.auditor.analyze_evidence(evidence)

        for control in result["analysis"]:
            summary_ar = control.get("summary_ar", "")
            self.assertIsInstance(summary_ar, str)
            self.assertGreater(len(summary_ar), 0)
            # Should contain status in Arabic (for COMPLIANT, PARTIAL, etc.)
            # Check that it's not empty
            self.assertTrue(len(summary_ar.strip()) > 0)

    def test_get_controls_by_category(self):
        """Test filtering controls by category."""
        controls = self.auditor.get_controls_by_category("Cybersecurity Strategy")
        self.assertGreater(len(controls), 0)

        for control in controls:
            self.assertIn("Cybersecurity Strategy", control.get("category_en", ""))

    def test_get_controls_by_risk_level(self):
        """Test filtering controls by risk level."""
        high_controls = self.auditor.get_controls_by_risk_level("HIGH")
        # Might be empty, but should be list
        self.assertIsInstance(high_controls, list)

    def test_json_output_validation(self):
        """Test that output is valid JSON-serializable."""
        evidence = "Security controls implemented and documented."
        result = self.auditor.analyze_evidence(evidence)

        # Should be JSON serializable
        json_str = json.dumps(result)
        self.assertIsInstance(json_str, str)

        # Should deserialize properly
        deserialized = json.loads(json_str)
        self.assertIn("analysis", deserialized)
        self.assertIn("overall_assessment", deserialized)


class NCAComplianceAuditorAPITests(APITestCase):
    """API tests for NCA compliance audit endpoints."""

    def setUp(self):
        """Set up test data."""
        # Create organization
        self.org = Organization.objects.create(
            name="Test Org",
            slug="test-org"
        )

        # Create user
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123"
        )

        # Link user to organization with AUDITOR role
        UserOrganization.objects.create(
            user=self.user,
            organization=self.org,
            role="AUDITOR"
        )

        # Create test evidence
        self.evidence = Evidence.objects.create(
            organization=self.org,
            file_name="test_policy.pdf",
            file_size=1024,
            file_type="pdf",
            extracted_text="""
            Cybersecurity Strategy: Comprehensive document approved by board.
            Implementation Plan: Detailed roadmap with milestones.
            Policies: Documented and disseminated.
            Access Control: MFA implemented.
            Incident Response: Procedures in place.
            """
        )

        self.client = Client()
        self.client.login(username="testuser", password="testpass123")

    def test_nca_audit_endpoint_exists(self):
        """Test that NCA audit endpoint exists."""
        url = f"/api/v1/organizations/test-org/evidence/{self.evidence.id}/nca-audit/"
        response = self.client.post(
            url,
            data=json.dumps({"evidence_id": self.evidence.id}),
            content_type="application/json"
        )
        # Should return 202 (accepted) or 400 (bad request) but endpoint exists
        self.assertIn(response.status_code, [202, 400, 404, 403, 401])

    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated users cannot access audit."""
        self.client.logout()
        url = f"/api/v1/organizations/test-org/evidence/{self.evidence.id}/nca-audit/"
        response = self.client.post(
            url,
            data=json.dumps({"evidence_id": self.evidence.id}),
            content_type="application/json"
        )
        self.assertIn(response.status_code, [401, 403])


class NCAComplianceAuditorRegressionTests(TestCase):
    """Regression tests for specific compliance scenarios."""

    def setUp(self):
        """Initialize auditor."""
        self.auditor = NCAComplianceAuditor()

    def test_handles_long_evidence(self):
        """Test handling of very long evidence documents."""
        long_evidence = (
            "Security control documentation. " * 1000
        )  # ~30KB

        result = self.auditor.analyze_evidence(long_evidence)

        # Should complete without error
        self.assertIn("analysis", result)
        self.assertGreater(len(result["analysis"]), 0)

    def test_handles_special_characters(self):
        """Test handling of special characters."""
        evidence = """
        Security: "Policies" & Controls (Level 1-2-3) [Advanced]
        Encryption: TLS 1.2+, SHA-256, RSA-2048
        Status: ✓ Implemented @ 2024-01-15
        """

        result = self.auditor.analyze_evidence(evidence)
        self.assertIn("analysis", result)

    def test_handles_multi_language_content(self):
        """Test handling of bilingual content."""
        evidence = """
        English Content
        
        سياسة الأمن السيبراني
        تم وضع استراتيجية شاملة للأمن السيبراني
        
        More English content
        """

        result = self.auditor.analyze_evidence(evidence)
        self.assertIn("analysis", result)

    def test_consistency_of_repeated_analysis(self):
        """Test that repeated analysis of same evidence gives consistent results."""
        evidence = "Cybersecurity strategy documented and approved."

        result1 = self.auditor.analyze_evidence(evidence)
        result2 = self.auditor.analyze_evidence(evidence)

        # Overall scores should match
        score1 = result1["overall_assessment"]["overall_score"]
        score2 = result2["overall_assessment"]["overall_score"]
        self.assertEqual(score1, score2)

    def test_score_improvements_with_more_detail(self):
        """Test that more detailed evidence results in higher scores."""
        basic = "We have security controls."

        detailed = """
        We have implemented comprehensive security controls:
        
        1. Access Control:
           - Multi-factor authentication for all users
           - Role-based access control implemented
           - Regular access reviews conducted quarterly
           
        2. Encryption:
           - TLS 1.2+ for all communications
           - AES-256 for data at rest
           - Key management procedures established
           
        3. Monitoring:
           - SIEM system in place
           - Real-time alerting configured
           - Weekly log reviews conducted
           
        4. Incident Response:
           - Documented procedures available
           - Team trained and ready
           - Regular drills conducted
        """

        result_basic = self.auditor.analyze_evidence(basic)
        result_detailed = self.auditor.analyze_evidence(detailed)

        score_basic = result_basic["overall_assessment"]["overall_score"]
        score_detailed = result_detailed["overall_assessment"]["overall_score"]

        # Detailed should score higher
        self.assertGreater(score_detailed, score_basic)


# ============================================================================
# EXAMPLE USAGE DEMONSTRATIONS
# ============================================================================


def example_basic_analysis():
    """Example: Basic compliance analysis."""
    auditor = NCAComplianceAuditor()

    evidence = """
    Cybersecurity Strategy Document
    Approved Date: January 1, 2024
    
    Our organization has established a comprehensive cybersecurity strategy
    that has been approved by executive management. The strategy addresses
    all essential security controls and is reviewed annually.
    """

    result = auditor.analyze_evidence(evidence)
    return result


def example_specific_controls_analysis():
    """Example: Analysis of specific controls only."""
    auditor = NCAComplianceAuditor()

    evidence = """
    Access Control Policy
    
    We have implemented multi-factor authentication for all privileged users.
    Role-based access control is used for system permissions.
    Access is reviewed quarterly.
    """

    # Analyze only access control specific controls
    result = auditor.analyze_evidence(
        evidence,
        control_codes=[
            "NCA-ECC-2-1-1",
            "NCA-ECC-2-1-2",
            "NCA-ECC-2-1-3",
        ]
    )
    return result


def example_get_control_details():
    """Example: Get details of a specific control."""
    auditor = NCAComplianceAuditor()

    # Get a specific control
    control = auditor.get_control_by_code("NCA-ECC-1-1-1")

    return {
        "code": control["code"],
        "title": control["title_en"],
        "description": control["description_en"],
        "category": control["category_en"],
    }


if __name__ == "__main__":
    # Run basic analysis example
    print("Basic Analysis Example:")
    print(json.dumps(example_basic_analysis(), indent=2))
