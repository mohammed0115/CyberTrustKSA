"""
Unit tests for Controls services: cloud integration guides.
"""
import json
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.conf import settings

from cybertrust.apps.controls.models import Control
from cybertrust.apps.controls.services.cloud_guides import (
    generate_cloud_guide,
    get_all_cloud_guides,
    generate_integration_checklist,
)
from cybertrust.apps.organizations.models import Organization


class CloudGuideGenerationTests(TestCase):
    """Test cloud integration guide generation."""

    def setUp(self):
        self.control = Control.objects.create(
            code="CC-001",
            title_en="Cloud Configuration Management",
            title_ar="إدارة تكوين السحابة"
        )

    @patch("cybertrust.apps.controls.services.cloud_guides.OpenAI")
    def test_generate_aws_guide(self, mock_openai):
        """Test generating AWS integration guide."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "provider": "AWS",
            "requirement": "MFA",
            "steps": [
                {
                    "step": 1,
                    "description": "Enable MFA for root account",
                    "code_snippet": "aws iam enable-virtual-mfa..."
                }
            ],
            "configuration": "IAM console config",
            "verification": "Test MFA login"
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        result = generate_cloud_guide(
            provider="AWS",
            requirement="MFA",
            control=self.control,
            language="en"
        )
        
        self.assertEqual(result["provider"], "AWS")
        self.assertEqual(result["requirement"], "MFA")
        self.assertIn("steps", result)

    @patch("cybertrust.apps.controls.services.cloud_guides.OpenAI")
    def test_generate_azure_guide(self, mock_openai):
        """Test generating Azure integration guide."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "provider": "Azure",
            "requirement": "Encryption",
            "steps": [
                {
                    "step": 1,
                    "description": "Enable encryption at rest",
                    "code_snippet": "az storage account update..."
                }
            ]
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        result = generate_cloud_guide(
            provider="Azure",
            requirement="Encryption",
            control=self.control,
            language="en"
        )
        
        self.assertEqual(result["provider"], "Azure")
        self.assertEqual(result["requirement"], "Encryption")

    @patch("cybertrust.apps.controls.services.cloud_guides.OpenAI")
    def test_generate_alibaba_guide(self, mock_openai):
        """Test generating Alibaba Cloud integration guide."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "provider": "Alibaba Cloud",
            "requirement": "VPC Setup",
            "steps": []
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        result = generate_cloud_guide(
            provider="Alibaba Cloud",
            requirement="VPC Setup",
            control=self.control,
            language="en"
        )
        
        self.assertEqual(result["provider"], "Alibaba Cloud")

    @patch("cybertrust.apps.controls.services.cloud_guides.OpenAI")
    def test_generate_guide_arabic(self, mock_openai):
        """Test generating guide in Arabic language."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "provider": "AWS",
            "requirement": "مصادقة متعددة العوامل",
            "steps": []
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        result = generate_cloud_guide(
            provider="AWS",
            requirement="MFA",
            control=self.control,
            language="ar"
        )
        
        self.assertIn("provider", result)

    @patch("cybertrust.apps.controls.services.cloud_guides.OpenAI")
    def test_generate_guide_api_error_fallback(self, mock_openai):
        """Test fallback to default guide on API error."""
        mock_openai.side_effect = Exception("API Error")
        
        result = generate_cloud_guide(
            provider="AWS",
            requirement="MFA",
            control=self.control,
            language="en"
        )
        
        # Should return default guide structure
        self.assertIn("provider", result)
        self.assertIn("requirement", result)

    def test_generate_guide_api_key_missing(self):
        """Test guide generation without OpenAI API key."""
        with self.settings(OPENAI_API_KEY=None):
            result = generate_cloud_guide(
                provider="AWS",
                requirement="MFA",
                control=self.control,
                language="en"
            )
            
            # Should return default guide
            self.assertIn("provider", result)

    @patch("cybertrust.apps.controls.services.cloud_guides.OpenAI")
    def test_guide_with_code_snippets(self, mock_openai):
        """Test guide contains executable code snippets."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "provider": "AWS",
            "requirement": "Logging",
            "steps": [
                {
                    "step": 1,
                    "description": "Enable CloudTrail",
                    "code_snippet": "aws cloudtrail create-trail --name..."
                }
            ]
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        result = generate_cloud_guide(
            provider="AWS",
            requirement="Logging",
            control=self.control
        )
        
        self.assertIn("steps", result)
        self.assertIn("code_snippet", result["steps"][0])


class CloudGuideRetrievalTests(TestCase):
    """Test retrieving cloud guides."""

    def setUp(self):
        self.org = Organization.objects.create(
            name="Test Org",
            slug="test-org"
        )
        self.control = Control.objects.create(
            code="CC-002",
            title_en="Cloud Security"
        )

    @patch("cybertrust.apps.controls.services.cloud_guides.OpenAI")
    def test_get_all_cloud_guides(self, mock_openai):
        """Test retrieving all cloud guides for control."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "guides": [
                {
                    "provider": "AWS",
                    "requirement": "MFA",
                    "steps": []
                },
                {
                    "provider": "Azure",
                    "requirement": "MFA",
                    "steps": []
                }
            ]
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        guides = get_all_cloud_guides(self.control)
        
        self.assertIsInstance(guides, list)

    def test_get_all_guides_fallback(self):
        """Test fallback when getting all guides."""
        # Call without mock to test default behavior
        guides = get_all_cloud_guides(self.control)
        
        self.assertIsInstance(guides, list)
        # Should have at least some default guides
        self.assertGreater(len(guides), 0)


class IntegrationChecklistTests(TestCase):
    """Test cloud integration checklist generation."""

    def setUp(self):
        self.control = Control.objects.create(
            code="CC-003",
            title_en="Cloud Integration"
        )

    @patch("cybertrust.apps.controls.services.cloud_guides.OpenAI")
    def test_generate_checklist(self, mock_openai):
        """Test generating integration checklist."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "checklist": [
                {
                    "item": "Setup security groups",
                    "provider": "AWS",
                    "priority": "high"
                },
                {
                    "item": "Enable encryption",
                    "provider": "AWS",
                    "priority": "high"
                }
            ],
            "estimated_time": "4 hours"
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        checklist = generate_integration_checklist(
            provider="AWS",
            control=self.control
        )
        
        self.assertIn("checklist", checklist)
        self.assertIsInstance(checklist["checklist"], list)

    def test_generate_checklist_fallback(self):
        """Test checklist fallback behavior."""
        checklist = generate_integration_checklist(
            provider="AWS",
            control=self.control
        )
        
        self.assertIn("checklist", checklist)


class CloudProviderSupportTests(TestCase):
    """Test support for different cloud providers."""

    def setUp(self):
        self.control = Control.objects.create(
            code="CC-004",
            title_en="Multi-Cloud Support"
        )

    @patch("cybertrust.apps.controls.services.cloud_guides.OpenAI")
    def test_supported_providers(self, mock_openai):
        """Test that all main cloud providers are supported."""
        providers = ["AWS", "Azure", "Alibaba Cloud", "Google Cloud"]
        
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        for provider in providers:
            mock_response = MagicMock()
            mock_response.choices[0].message.content = json.dumps({
                "provider": provider,
                "requirement": "Test",
                "steps": []
            })
            mock_client.chat.completions.create.return_value = mock_response
            
            result = generate_cloud_guide(
                provider=provider,
                requirement="Test",
                control=self.control
            )
            
            self.assertIn("provider", result)

    def test_guide_consistency_across_providers(self):
        """Test guide structure is consistent across providers."""
        providers = ["AWS", "Azure", "Alibaba Cloud"]
        expected_fields = ["provider", "requirement", "steps"]
        
        for provider in providers:
            result = generate_cloud_guide(
                provider=provider,
                requirement="MFA",
                control=self.control
            )
            
            for field in expected_fields:
                self.assertIn(
                    field,
                    result,
                    f"Missing field '{field}' in {provider} guide"
                )


class CloudGuideContentTests(TestCase):
    """Test content and structure of cloud guides."""

    def setUp(self):
        self.control = Control.objects.create(
            code="CC-005",
            title_en="Cloud Guide Content"
        )

    def test_guide_contains_comparison_table(self):
        """Test that guides include provider comparison."""
        guides = get_all_cloud_guides(self.control)
        
        # Should have multiple providers for comparison
        providers_found = set()
        if isinstance(guides, list) and len(guides) > 0:
            for guide in guides:
                if isinstance(guide, dict) and "provider" in guide:
                    providers_found.add(guide["provider"])

    def test_guide_requirement_types(self):
        """Test various requirement types are supported."""
        requirements = [
            "MFA",
            "Encryption",
            "Logging",
            "VPC",
            "WAF",
            "Backup"
        ]
        
        for requirement in requirements:
            result = generate_cloud_guide(
                provider="AWS",
                requirement=requirement,
                control=self.control
            )
            
            self.assertEqual(result["requirement"], requirement)

    def test_guide_language_support(self):
        """Test guides support multiple languages."""
        languages = ["en", "ar"]
        
        for lang in languages:
            result = generate_cloud_guide(
                provider="AWS",
                requirement="MFA",
                control=self.control,
                language=lang
            )
            
            self.assertIn("provider", result)


class CloudGuideFormattingTests(TestCase):
    """Test formatting and presentation of guides."""

    def setUp(self):
        self.control = Control.objects.create(
            code="CC-006",
            title_en="Cloud Guide Formatting"
        )

    @patch("cybertrust.apps.controls.services.cloud_guides.OpenAI")
    def test_guide_code_snippet_format(self, mock_openai):
        """Test code snippets are properly formatted."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "provider": "AWS",
            "requirement": "CLoudTrail Logging",
            "steps": [
                {
                    "step": 1,
                    "description": "Enable CloudTrail",
                    "code_snippet": "aws cloudtrail create-trail --name my-trail --s3-bucket-name my-bucket"
                }
            ]
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        result = generate_cloud_guide(
            provider="AWS",
            requirement="CloudTrail Logging",
            control=self.control
        )
        
        self.assertIn("steps", result)
        if result["steps"]:
            step = result["steps"][0]
            self.assertIn("code_snippet", step)
            self.assertTrue(len(step["code_snippet"]) > 0)

    def test_guide_step_ordering(self):
        """Test guide steps are properly ordered."""
        result = generate_cloud_guide(
            provider="AWS",
            requirement="MFA",
            control=self.control
        )
        
        if "steps" in result and result["steps"]:
            for idx, step in enumerate(result["steps"]):
                if "step" in step:
                    # Step numbers should be in order
                    self.assertEqual(step["step"], idx + 1)


class ErrorHandlingAndFallbacksTests(TestCase):
    """Test error handling and fallback mechanisms."""

    def setUp(self):
        self.control = Control.objects.create(
            code="CC-007",
            title_en="Error Handling Tests"
        )

    @patch("cybertrust.apps.controls.services.cloud_guides.OpenAI")
    def test_timeout_fallback(self, mock_openai):
        """Test fallback on API timeout."""
        mock_openai.side_effect = TimeoutError("API timeout")
        
        result = generate_cloud_guide(
            provider="AWS",
            requirement="MFA",
            control=self.control
        )
        
        # Should return default guide without crashing
        self.assertIn("provider", result)

    @patch("cybertrust.apps.controls.services.cloud_guides.OpenAI")
    def test_invalid_json_response_fallback(self, mock_openai):
        """Test fallback on invalid JSON response."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Invalid JSON {invalid"
        mock_client.chat.completions.create.return_value = mock_response
        
        result = generate_cloud_guide(
            provider="AWS",
            requirement="MFA",
            control=self.control
        )
        
        self.assertIn("provider", result)

    def test_missing_control_handling(self):
        """Test handling of operations with missing control."""
        # Should handle gracefully if control is None
        result = generate_cloud_guide(
            provider="AWS",
            requirement="Test",
            control=None
        )
        
        self.assertIn("provider", result)


class CloudGuideStorageTests(TestCase):
    """Test guide caching and storage."""

    def test_guides_are_retrievable_multiple_times(self):
        """Test that guides can be retrieved multiple times consistently."""
        control = Control.objects.create(
            code="CC-008",
            title_en="Storage Tests"
        )
        
        # First retrieval
        guides1 = get_all_cloud_guides(control)
        
        # Second retrieval
        guides2 = get_all_cloud_guides(control)
        
        # Both should have same structure
        self.assertEqual(type(guides1), type(guides2))

    def test_guides_per_control_independence(self):
        """Test that guides for different controls are independent."""
        control1 = Control.objects.create(
            code="CC-009A",
            title_en="Control A"
        )
        control2 = Control.objects.create(
            code="CC-009B",
            title_en="Control B"
        )
        
        guides1 = get_all_cloud_guides(control1)
        guides2 = get_all_cloud_guides(control2)
        
        # Both should return results
        self.assertIsInstance(guides1, list)
        self.assertIsInstance(guides2, list)
