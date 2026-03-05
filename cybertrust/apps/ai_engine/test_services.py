"""
Unit tests for AI Engine services: chatbot, arabic_analysis, remediation.
"""
import json
from unittest.mock import patch, MagicMock, AsyncMock
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from cybertrust.apps.ai_engine.models import ChatMessage, AIAnalysisResult
from cybertrust.apps.ai_engine.services.chatbot import (
    chat_with_ciso,
    get_ciso_system_prompt,
    get_conversation_history,
    clear_conversation_history,
)
from cybertrust.apps.ai_engine.services.arabic_analysis import (
    analyze_evidence_arabic,
    create_bilingual_analysis_result,
    extract_and_analyze_arabic_document,
    get_arabic_compliance_report,
)
from cybertrust.apps.ai_engine.services.remediation import (
    generate_remediation_template,
    get_default_remediation,
    RemediationTracker,
)
from cybertrust.apps.organizations.models import Organization
from cybertrust.apps.controls.models import Control
from cybertrust.apps.evidence.models import Evidence

User = get_user_model()


class ChatbotServiceTests(TestCase):
    """Test Virtual CISO chatbot service."""

    def setUp(self):
        self.org = Organization.objects.create(name="Test Org", slug="test-org")
        self.user = User.objects.create_user(username="testuser", password="testpass")

    def test_get_ciso_system_prompt_english(self):
        """Test system prompt generation in English."""
        prompt = get_ciso_system_prompt("en")
        self.assertIn("Virtual CISO", prompt)
        self.assertIn("NCA", prompt)
        self.assertIn("English", prompt)

    def test_get_ciso_system_prompt_arabic(self):
        """Test system prompt generation in Arabic."""
        prompt = get_ciso_system_prompt("ar")
        self.assertIn("CISO", prompt)
        self.assertIn("NCA", prompt)
        self.assertIn("العربية", prompt)

    @patch("cybertrust.apps.ai_engine.services.chatbot.OpenAI")
    def test_chat_with_ciso_success(self, mock_openai):
        """Test successful chatbot response."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "This is a test response."
        mock_client.chat.completions.create.return_value = mock_response
        
        # Run async function with asyncio.run if available
        import asyncio
        result = asyncio.run(
            chat_with_ciso(
                user_message="How do I implement MFA?",
                organization=self.org,
                user=self.user,
                language="en"
            )
        )
        
        self.assertIn("response", result)
        self.assertEqual(result["response"], "This is a test response.")
        
        # Verify message was saved
        self.assertTrue(ChatMessage.objects.filter(organization=self.org).exists())

    @patch("cybertrust.apps.ai_engine.services.chatbot.OpenAI")
    def test_chat_with_ciso_with_context(self, mock_openai):
        """Test chatbot with conversation context."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Follow-up response"
        mock_client.chat.completions.create.return_value = mock_response
        
        context = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"}
        ]
        
        import asyncio
        result = asyncio.run(
            chat_with_ciso(
                user_message="Another question",
                conversation_context=context,
                language="en"
            )
        )
        
        self.assertIn("response", result)
        # Verify context was passed to OpenAI
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        self.assertGreater(len(messages), 2)  # system + context + current

    def test_get_conversation_history(self):
        """Test retrieving conversation history."""
        ChatMessage.objects.create(
            organization=self.org,
            user=self.user,
            role=ChatMessage.ROLE_USER,
            content="Question 1",
            language="en"
        )
        ChatMessage.objects.create(
            organization=self.org,
            user=self.user,
            role=ChatMessage.ROLE_ASSISTANT,
            content="Answer 1",
            language="en"
        )
        
        history = get_conversation_history(self.org, self.user)
        
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[1]["role"], "assistant")

    def test_clear_conversation_history(self):
        """Test clearing conversation history."""
        ChatMessage.objects.create(
            organization=self.org,
            user=self.user,
            role=ChatMessage.ROLE_USER,
            content="Question",
            language="en"
        )
        
        self.assertEqual(ChatMessage.objects.filter(organization=self.org).count(), 1)
        
        clear_conversation_history(self.org, self.user)
        
        self.assertEqual(ChatMessage.objects.filter(organization=self.org).count(), 0)

    @override_settings(OPENAI_API_KEY=None)
    @patch("cybertrust.apps.ai_engine.services.chatbot.OpenAI")
    def test_chat_without_api_key(self, mock_openai):
        """Test chatbot error handling without API key."""
        import asyncio
        with self.assertRaises(RuntimeError):
            asyncio.run(chat_with_ciso("Test message"))


class ArabicAnalysisServiceTests(TestCase):
    """Test Arabic NLP analysis service."""

    def setUp(self):
        self.org = Organization.objects.create(name="Test Org", slug="test-org")
        self.control = Control.objects.create(
            code="AC-001",
            title_en="Access Control",
            title_ar="التحكم بالوصول"
        )

    @patch("cybertrust.apps.ai_engine.services.arabic_analysis.OpenAI")
    def test_analyze_evidence_arabic(self, mock_openai):
        """Test Arabic evidence analysis."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "status": "PARTIAL",
            "score": 75,
            "missing_points": ["تحديث كلمات المرور"],
            "summary_ar": "التحكم جزئياً فعال"
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        result = analyze_evidence_arabic(
            "This is test evidence",
            self.control,
            language="ar"
        )
        
        self.assertIn("status", result)
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["score"], 75)

    def test_create_bilingual_analysis_result(self):
        """Test creating bilingual analysis result."""
        evidence = Evidence.objects.create(
            name="Test Evidence",
            organization=self.org,
            file_path="/test/path.pdf"
        )
        
        analysis_data = {
            "status": "COMPLIANT",
            "score": 95,
            "missing_points": [],
            "summary_ar": "ممتثل تماماً",
            "summary_en": "Fully compliant"
        }
        
        result = create_bilingual_analysis_result(
            organization=self.org,
            evidence=evidence,
            control=self.control,
            analysis_data=analysis_data,
            model_name="gpt-4o-mini"
        )
        
        self.assertEqual(result.status, AIAnalysisResult.STATUS_COMPLIANT)
        self.assertEqual(result.score, 95)
        self.assertEqual(result.summary_ar, "ممتثل تماماً")

    @patch("cybertrust.apps.ai_engine.services.arabic_analysis.OpenAI")
    def test_extract_and_analyze_arabic_document(self, mock_openai):
        """Test document extraction and analysis."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "extracted_text": "Sample text",
            "analysis": {"status": "PARTIAL", "score": 80}
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        result = extract_and_analyze_arabic_document(
            "/path/to/document.pdf",
            self.control
        )
        
        self.assertIn("extracted_text", result)

    def test_get_arabic_compliance_report(self):
        """Test generating Arabic compliance report."""
        evidence = Evidence.objects.create(
            name="Test Evidence",
            organization=self.org,
            file_path="/test/path.pdf"
        )
        
        AIAnalysisResult.objects.create(
            organization=self.org,
            evidence=evidence,
            control=self.control,
            status=AIAnalysisResult.STATUS_PARTIAL,
            score=75,
            summary_ar="التقرير الجزئي",
            summary_en="Partial Report"
        )
        
        report = get_arabic_compliance_report(self.org)
        
        self.assertIn("summary", report)
        self.assertIn("controls_analyzed", report)
        self.assertGreater(len(report["controls_analyzed"]), 0)


class RemediationServiceTests(TestCase):
    """Test remediation templates service."""

    def setUp(self):
        self.org = Organization.objects.create(name="Test Org", slug="test-org")
        self.control = Control.objects.create(
            code="AC-002",
            title_en="User Access Management",
            title_ar="إدارة وصول المستخدمين"
        )

    @patch("cybertrust.apps.ai_engine.services.remediation.OpenAI")
    def test_generate_remediation_template(self, mock_openai):
        """Test remediation template generation."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "steps": [
                {
                    "order": 1,
                    "description": "Implement MFA",
                    "effort_hours": 8,
                    "accepted_by": "Security Team"
                }
            ],
            "templates": [],
            "testing": ["Test login"],
            "timeline_days": 1,
            "success_criteria": "MFA enforced"
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        result = generate_remediation_template(
            self.control,
            ["Missing MFA implementation"],
            self.org,
            language="en"
        )
        
        self.assertIn("steps", result)
        self.assertEqual(len(result["steps"]), 1)
        self.assertEqual(result["control_code"], "AC-002")

    def test_get_default_remediation(self):
        """Test default remediation fallback."""
        result = get_default_remediation(
            self.control,
            ["Missing points"],
            "en"
        )
        
        self.assertIn("steps", result)
        self.assertIn("timeline_days", result)
        self.assertEqual(result["control_code"], "AC-002")

    def test_remediation_tracker_create(self):
        """Test RemediationTracker creation."""
        tracker = RemediationTracker.create(
            control=self.control,
            organization=self.org,
            assigned_to_role="Security Team"
        )
        
        self.assertIsNotNone(tracker)
        self.assertEqual(tracker.control.code, "AC-002")

    def test_remediation_tracker_progress(self):
        """Test remediation progress tracking."""
        tracker = RemediationTracker.create(
            control=self.control,
            organization=self.org
        )
        
        # Simulate 50% progress
        tracker.track_progress(percent_complete=50)
        
        self.assertEqual(tracker.percent_complete, 50)
        self.assertEqual(tracker.status, "in_progress")

    def test_remediation_tracker_completion(self):
        """Test remediation completion."""
        tracker = RemediationTracker.create(
            control=self.control,
            organization=self.org
        )
        
        tracker.track_progress(percent_complete=100)
        
        self.assertEqual(tracker.percent_complete, 100)
        self.assertEqual(tracker.status, "completed")
        self.assertIsNotNone(tracker.completed_at)


class ChatMessageModelTests(TestCase):
    """Test ChatMessage model."""

    def setUp(self):
        self.org = Organization.objects.create(name="Test Org", slug="test-org")
        self.user = User.objects.create_user(username="testuser", password="testpass")

    def test_create_user_message(self):
        """Test creating a user message."""
        msg = ChatMessage.objects.create(
            organization=self.org,
            user=self.user,
            role=ChatMessage.ROLE_USER,
            content="How do I implement access control?",
            language="en"
        )
        
        self.assertEqual(msg.role, ChatMessage.ROLE_USER)
        self.assertEqual(msg.organization, self.org)
        self.assertIsNotNone(msg.created_at)

    def test_create_assistant_message(self):
        """Test creating an assistant message."""
        msg = ChatMessage.objects.create(
            organization=self.org,
            user=self.user,
            role=ChatMessage.ROLE_ASSISTANT,
            content="Access control can be implemented...",
            language="en"
        )
        
        self.assertEqual(msg.role, ChatMessage.ROLE_ASSISTANT)

    def test_message_ordering(self):
        """Test messages are ordered by creation time."""
        msg1 = ChatMessage.objects.create(
            organization=self.org,
            role=ChatMessage.ROLE_USER,
            content="First"
        )
        msg2 = ChatMessage.objects.create(
            organization=self.org,
            role=ChatMessage.ROLE_ASSISTANT,
            content="Second"
        )
        
        messages = list(ChatMessage.objects.filter(organization=self.org))
        self.assertEqual(messages[0].content, "First")
        self.assertEqual(messages[1].content, "Second")

    def test_arabic_language_support(self):
        """Test Arabic language support."""
        msg = ChatMessage.objects.create(
            organization=self.org,
            role=ChatMessage.ROLE_USER,
            content="كيف أطبق التحكم بالوصول؟",
            language="ar"
        )
        
        self.assertEqual(msg.language, "ar")
        self.assertEqual(msg.content, "كيف أطبق التحكم بالوصول؟")


class AIAnalysisResultModelTests(TestCase):
    """Test AIAnalysisResult model."""

    def setUp(self):
        self.org = Organization.objects.create(name="Test Org", slug="test-org")
        self.control = Control.objects.create(
            code="AC-001",
            title_en="Access Control"
        )
        self.evidence = Evidence.objects.create(
            name="Test Evidence",
            organization=self.org,
            file_path="/test/path.pdf"
        )

    def test_create_analysis_result(self):
        """Test creating analysis result."""
        result = AIAnalysisResult.objects.create(
            organization=self.org,
            evidence=self.evidence,
            control=self.control,
            model_name="gpt-4o-mini",
            score=85,
            status=AIAnalysisResult.STATUS_PARTIAL,
            confidence=92
        )
        
        self.assertEqual(result.score, 85)
        self.assertEqual(result.status, AIAnalysisResult.STATUS_PARTIAL)
        self.assertEqual(result.confidence, 92)

    def test_analysis_with_recommendations(self):
        """Test analysis result with recommendations."""
        recommendations = [
            "Implement MFA",
            "Update access policies"
        ]
        
        result = AIAnalysisResult.objects.create(
            organization=self.org,
            evidence=self.evidence,
            control=self.control,
            model_name="gpt-4o-mini",
            recommendations=recommendations,
            status=AIAnalysisResult.STATUS_NON_COMPLIANT
        )
        
        self.assertIn("Implement MFA", result.recommendations)

    def test_bilingual_summaries(self):
        """Test storing bilingual summaries."""
        result = AIAnalysisResult.objects.create(
            organization=self.org,
            evidence=self.evidence,
            control=self.control,
            model_name="gpt-4o-mini",
            summary_en="Access control is partially implemented",
            summary_ar="التحكم بالوصول مطبق جزئياً"
        )
        
        self.assertEqual(result.summary_en, "Access control is partially implemented")
        self.assertEqual(result.summary_ar, "التحكم بالوصول مطبق جزئياً")


class ErrorHandlingTests(TestCase):
    """Test error handling in services."""

    def setUp(self):
        self.org = Organization.objects.create(name="Test Org", slug="test-org")

    @patch("cybertrust.apps.ai_engine.services.chatbot.OpenAI")
    def test_openai_api_timeout(self, mock_openai):
        """Test handling of OpenAI API timeout."""
        mock_openai.side_effect = TimeoutError("API timeout")
        
        import asyncio
        with self.assertRaises(TimeoutError):
            asyncio.run(chat_with_ciso("Test message"))

    @patch("cybertrust.apps.ai_engine.services.remediation.OpenAI")
    def test_json_parsing_error_fallback(self, mock_openai):
        """Test fallback when JSON parsing fails."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        # Return invalid JSON
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Invalid JSON response"
        mock_client.chat.completions.create.return_value = mock_response
        
        control = Control.objects.create(code="TEST", title_en="Test")
        result = generate_remediation_template(control, ["gap"], self.org)
        
        # Should return default remediation instead of crashing
        self.assertIn("steps", result)
        self.assertEqual(result["control_code"], "TEST")
