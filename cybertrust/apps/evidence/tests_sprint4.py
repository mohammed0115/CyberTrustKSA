"""
Sprint 4 Tests - Async AI Analysis & Compliance Scoring
Tests for:
- Evidence upload and status tracking
- Analysis triggering and progress
- Celery tasks
- Scoring calculations
- Dashboard API
"""
import json
from datetime import timedelta
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient, APITestCase
from rest_framework import status

from cybertrust.apps.evidence.models import Evidence, EvidenceControlLink
from cybertrust.apps.controls.models import Control, ControlCategory, ControlScoreSnapshot
from cybertrust.apps.ai_engine.models import AIAnalysisResult
from cybertrust.apps.organizations.models import Organization, UserOrganization
from cybertrust.apps.controls.services.scoring import (
    compute_control_score,
    compute_category_score,
    compute_overall_score,
    get_dashboard_kpis,
)

User = get_user_model()


class EvidenceUploadTestCase(APITestCase):
    """Tests for evidence file upload and validation."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create organization
        self.org = Organization.objects.create(
            name='Test Organization',
            slug='test-org',
            country='SA'
        )
        
        # Add user to organization
        UserOrganization.objects.create(
            user=self.user,
            organization=self.org,
            role='ADMIN'
        )
        
        self.client.force_authenticate(user=self.user)
    
    def test_upload_pdf_file(self):
        """Test uploading a valid PDF file."""
        pdf_file = SimpleUploadedFile(
            "document.pdf",
            b"file content",
            content_type="application/pdf"
        )
        
        response = self.client.post(
            f'/api/v1/organizations/{self.org.slug}/evidence/upload/',
            {'file': pdf_file},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertEqual(response.data['status'], 'UPLOADED')
    
    def test_upload_without_file(self):
        """Test upload fails when no file provided."""
        response = self.client.post(
            f'/api/v1/organizations/{self.org.slug}/evidence/upload/',
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_upload_invalid_extension(self):
        """Test upload fails with invalid file extension."""
        exe_file = SimpleUploadedFile(
            "malware.exe",
            b"executable",
            content_type="application/x-msdownload"
        )
        
        response = self.client.post(
            f'/api/v1/organizations/{self.org.slug}/evidence/upload/',
            {'file': exe_file},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_upload_oversized_file(self):
        """Test upload fails when file exceeds max size."""
        # Create a file larger than 25MB
        large_file = SimpleUploadedFile(
            "huge.pdf",
            b"x" * (26 * 1024 * 1024),  # 26MB
            content_type="application/pdf"
        )
        
        response = self.client.post(
            f'/api/v1/organizations/{self.org.slug}/evidence/upload/',
            {'file': large_file},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)


class EvidenceStatusTrackingTestCase(APITestCase):
    """Tests for evidence status pipeline tracking."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create organization
        self.org = Organization.objects.create(
            name='Test Organization',
            slug='test-org',
            country='SA'
        )
        
        UserOrganization.objects.create(
            user=self.user,
            organization=self.org,
            role='ADMIN'
        )
        
        # Create evidence
        self.evidence = Evidence.objects.create(
            organization=self.org,
            uploaded_by=self.user,
            original_filename='test.pdf',
            file_size=1024,
            file_type=Evidence.FILE_PDF,
            status=Evidence.STATUS_UPLOADED,
        )
        
        self.client.force_authenticate(user=self.user)
    
    def test_get_evidence_status(self):
        """Test getting evidence status."""
        response = self.client.get(
            f'/api/v1/organizations/{self.org.slug}/evidence/{self.evidence.id}/status/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'UPLOADED')
        self.assertEqual(response.data['progress'], 0)
    
    def test_status_progress_mapping(self):
        """Test that status maps to correct progress percentage."""
        status_progress = {
            Evidence.STATUS_UPLOADED: 0,
            Evidence.STATUS_EXTRACTING: 25,
            Evidence.STATUS_EXTRACTED: 25,
            Evidence.STATUS_ANALYZING: 75,
            Evidence.STATUS_ANALYZED: 100,
        }
        
        for status_val, expected_progress in status_progress.items():
            self.evidence.status = status_val
            self.evidence.save()
            
            response = self.client.get(
                f'/api/v1/organizations/{self.org.slug}/evidence/{self.evidence.id}/status/'
            )
            
            self.assertEqual(response.data['progress'], expected_progress)


class ControlLinkingTestCase(APITestCase):
    """Tests for linking controls to evidence."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create organization
        self.org = Organization.objects.create(
            name='Test Organization',
            slug='test-org',
            country='SA'
        )
        
        UserOrganization.objects.create(
            user=self.user,
            organization=self.org,
            role='ADMIN'
        )
        
        # Create category
        self.category = ControlCategory.objects.create(
            name_en='Access Control',
            name_ar='التحكم بالوصول',
            code='AC'
        )
        
        # Create control
        self.control = Control.objects.create(
            code='AC-001',
            category=self.category,
            title_en='User Access Management',
            title_ar='إدارة وصول المستخدم',
            risk_level='HIGH'
        )
        
        # Create evidence
        self.evidence = Evidence.objects.create(
            organization=self.org,
            uploaded_by=self.user,
            original_filename='test.pdf',
            file_size=1024,
            file_type=Evidence.FILE_PDF,
            status=Evidence.STATUS_UPLOADED,
        )
        
        self.client.force_authenticate(user=self.user)
    
    def test_link_control_to_evidence(self):
        """Test linking a control to evidence."""
        response = self.client.post(
            f'/api/v1/organizations/{self.org.slug}/evidence/{self.evidence.id}/link/',
            {'control_id': self.control.id},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['control_id'], self.control.id)
        
        # Verify link exists
        link = EvidenceControlLink.objects.get(
            evidence=self.evidence,
            control=self.control
        )
        self.assertIsNotNone(link)
    
    def test_link_already_exists(self):
        """Test linking control that's already linked."""
        # Create initial link
        EvidenceControlLink.objects.create(
            evidence=self.evidence,
            control=self.control
        )
        
        # Try to link again
        response = self.client.post(
            f'/api/v1/organizations/{self.org.slug}/evidence/{self.evidence.id}/link/',
            {'control_id': self.control.id},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('already linked', response.data['message'])


class ScoringCalculationTestCase(TestCase):
    """Tests for compliance scoring calculations."""
    
    def setUp(self):
        """Set up test data."""
        # Create organization
        self.org = Organization.objects.create(
            name='Test Organization',
            slug='test-org',
            country='SA'
        )
        
        # Create categories
        self.category_ac = ControlCategory.objects.create(
            name_en='Access Control',
            name_ar='التحكم بالوصول',
            code='AC'
        )
        
        # Create controls
        self.control_high_risk = Control.objects.create(
            code='AC-001',
            category=self.category_ac,
            title_en='High Risk Control',
            risk_level='HIGH'  # Weight: 1.5
        )
        
        self.control_low_risk = Control.objects.create(
            code='AC-002',
            category=self.category_ac,
            title_en='Low Risk Control',
            risk_level='LOW'  # Weight: 0.7
        )
    
    def test_control_score_compliant(self):
        """Test score calculation for COMPLIANT status."""
        # Create score snapshot
        ControlScoreSnapshot.objects.create(
            organization=self.org,
            control=self.control_high_risk,
            score=100,
            status='COMPLIANT'
        )
        
        result = compute_control_score(self.org, self.control_high_risk)
        
        self.assertEqual(result['score'], 100)
        self.assertEqual(result['status'], 'COMPLIANT')
    
    def test_control_score_partial(self):
        """Test score calculation for PARTIAL status."""
        ControlScoreSnapshot.objects.create(
            organization=self.org,
            control=self.control_high_risk,
            score=60,
            status='PARTIAL'
        )
        
        result = compute_control_score(self.org, self.control_high_risk)
        
        self.assertEqual(result['score'], 60)
        self.assertEqual(result['status'], 'PARTIAL')
    
    def test_category_score_weighted_average(self):
        """Test category score is weighted average of controls."""
        # Create scores for controls with different risk levels
        ControlScoreSnapshot.objects.create(
            organization=self.org,
            control=self.control_high_risk,  # HIGH=1.5 weight
            score=100,
            status='COMPLIANT'
        )
        
        ControlScoreSnapshot.objects.create(
            organization=self.org,
            control=self.control_low_risk,  # LOW=0.7 weight
            score=50,
            status='PARTIAL'
        )
        
        result = compute_category_score(self.org, self.category_ac)
        
        # Expected: (100*1.5 + 50*0.7) / (1.5 + 0.7) = 200/2.2 ≈ 90.9
        expected = (100 * 1.5 + 50 * 0.7) / (1.5 + 0.7)
        self.assertAlmostEqual(result['score'], expected, places=0)
    
    def test_overall_score_risk_level_high(self):
        """Test overall score categorizes as HIGH risk when < 50."""
        ControlScoreSnapshot.objects.create(
            organization=self.org,
            control=self.control_high_risk,
            score=30,
            status='NON_COMPLIANT'
        )
        
        result = compute_overall_score(self.org)
        
        self.assertLess(result, 50)  # Should indicate HIGH risk
    
    def test_overall_score_risk_level_low(self):
        """Test overall score categorizes as LOW risk when >= 80."""
        ControlScoreSnapshot.objects.create(
            organization=self.org,
            control=self.control_high_risk,
            score=90,
            status='COMPLIANT'
        )
        
        result = compute_overall_score(self.org)
        
        self.assertGreaterEqual(result, 80)  # Should indicate LOW risk


class DashboardAPITestCase(APITestCase):
    """Tests for compliance dashboard API."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create organization
        self.org = Organization.objects.create(
            name='Test Organization',
            slug='test-org',
            country='SA'
        )
        
        UserOrganization.objects.create(
            user=self.user,
            organization=self.org,
            role='ADMIN'
        )
        
        # Create category
        self.category = ControlCategory.objects.create(
            name_en='Access Control',
            name_ar='التحكم بالوصول',
            code='AC'
        )
        
        # Create control
        self.control = Control.objects.create(
            code='AC-001',
            category=self.category,
            title_en='Test Control',
            risk_level='HIGH'
        )
        
        # Create score
        ControlScoreSnapshot.objects.create(
            organization=self.org,
            control=self.control,
            score=75,
            status='PARTIAL'
        )
        
        self.client.force_authenticate(user=self.user)
    
    def test_get_dashboard(self):
        """Test getting dashboard KPIs."""
        response = self.client.get(
            f'/api/v1/organizations/{self.org.slug}/dashboard/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('overall_score', response.data)
        self.assertIn('risk_level', response.data)
        self.assertIn('controls_completed', response.data)
        self.assertIn('category_scores', response.data)
    
    def test_dashboard_risk_level_medium(self):
        """Test dashboard correctly identifies MEDIUM risk."""
        # Medium risk is 50 <= score < 80
        response = self.client.get(
            f'/api/v1/organizations/{self.org.slug}/dashboard/'
        )
        
        # With one 75 score control, should be MEDIUM
        score = response.data['overall_score']
        self.assertGreaterEqual(score, 50)
        self.assertLess(score, 80)


class AnalysisResultsTestCase(APITestCase):
    """Tests for analysis results and control details."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create organization
        self.org = Organization.objects.create(
            name='Test Organization',
            slug='test-org',
            country='SA'
        )
        
        UserOrganization.objects.create(
            user=self.user,
            organization=self.org,
            role='ADMIN'
        )
        
        # Create category and control
        self.category = ControlCategory.objects.create(
            name_en='Access Control',
            name_ar='التحكم بالوصول',
            code='AC'
        )
        
        self.control = Control.objects.create(
            code='AC-001',
            category=self.category,
            title_en='User Access Management',
            risk_level='HIGH'
        )
        
        # Create evidence
        self.evidence = Evidence.objects.create(
            organization=self.org,
            uploaded_by=self.user,
            original_filename='test.pdf',
            file_size=1024,
            file_type=Evidence.FILE_PDF,
            status=Evidence.STATUS_ANALYZED,
            extracted_text='Sample evidence text'
        )
        
        # Create analysis result
        self.analysis = AIAnalysisResult.objects.create(
            organization=self.org,
            evidence=self.evidence,
            control=self.control,
            status='COMPLIANT',
            score=100,
            confidence=95,
            summary_en='Evidence shows full compliance',
            summary_ar='تظهر الأدلة الامتثال الكامل',
            missing_points=['None'],
            recommendations=['Continue monitoring'],
            citations=['Evidence documentation']
        )
        
        # Create score snapshot
        ControlScoreSnapshot.objects.create(
            organization=self.org,
            control=self.control,
            score=100,
            status='COMPLIANT'
        )
        
        self.client.force_authenticate(user=self.user)
    
    def test_get_control_details(self):
        """Test getting control details with analysis results."""
        response = self.client.get(
            f'/api/v1/organizations/{self.org.slug}/controls/{self.control.id}/details/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('control', response.data)
        self.assertIn('score', response.data)
        self.assertIn('analysis_results', response.data)
        
        # Verify analysis result is included
        self.assertEqual(len(response.data['analysis_results']), 1)
        result = response.data['analysis_results'][0]
        self.assertEqual(result['status'], 'COMPLIANT')
        self.assertEqual(result['score'], 100)
    
    def test_control_details_with_multiple_analyses(self):
        """Test control details with multiple analysis results."""
        # Create another evidence and analysis
        evidence2 = Evidence.objects.create(
            organization=self.org,
            uploaded_by=self.user,
            original_filename='test2.pdf',
            file_size=2048,
            file_type=Evidence.FILE_PDF,
            status=Evidence.STATUS_ANALYZED,
        )
        
        analysis2 = AIAnalysisResult.objects.create(
            organization=self.org,
            evidence=evidence2,
            control=self.control,
            status='PARTIAL',
            score=60,
            confidence=85,
            summary_en='Partial compliance',
            summary_ar='امتثال جزئي'
        )
        
        response = self.client.get(
            f'/api/v1/organizations/{self.org.slug}/controls/{self.control.id}/details/'
        )
        
        # Should have both analyses (newest first)
        self.assertEqual(len(response.data['analysis_results']), 2)
        self.assertEqual(response.data['analysis_results'][0]['status'], 'PARTIAL')


class PermissionTestCase(APITestCase):
    """Tests for access control and permissions."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create users
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='admintestpass123'
        )
        
        self.viewer = User.objects.create_user(
            username='viewer',
            email='viewer@example.com',
            password='viewertestpass123'
        )
        
        # Create organizations
        self.org_admin = Organization.objects.create(
            name='Admin Org',
            slug='admin-org',
            country='SA'
        )
        
        self.org_viewer = Organization.objects.create(
            name='Viewer Org',
            slug='viewer-org',
            country='SA'
        )
        
        # Add admin to org_admin
        UserOrganization.objects.create(
            user=self.admin,
            organization=self.org_admin,
            role='ADMIN'
        )
        
        # Add viewer to org_viewer as AUDITOR
        UserOrganization.objects.create(
            user=self.viewer,
            organization=self.org_viewer,
            role='AUDITOR'
        )
        
        # Create evidence
        self.evidence = Evidence.objects.create(
            organization=self.org_admin,
            uploaded_by=self.admin,
            original_filename='test.pdf',
            file_size=1024,
            file_type=Evidence.FILE_PDF,
        )
    
    def test_user_cannot_access_other_org(self):
        """Test user cannot access evidence from org they don't belong to."""
        self.client.force_authenticate(user=self.viewer)
        
        response = self.client.get(
            f'/api/v1/organizations/admin-org/evidence/{self.evidence.id}/',
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_auditor_cannot_trigger_analysis(self):
        """Test AUDITOR role cannot trigger analysis."""
        self.client.force_authenticate(user=self.viewer)
        
        # Create category and control
        category = ControlCategory.objects.create(
            name_en='Test',
            name_ar='اختبار',
            code='T'
        )
        control = Control.objects.create(
            code='T-001',
            category=category,
            title_en='Test Control'
        )
        
        evidence = Evidence.objects.create(
            organization=self.org_viewer,
            uploaded_by=self.viewer,
            original_filename='test.pdf',
            file_size=1024,
            file_type=Evidence.FILE_PDF,
        )
        
        EvidenceControlLink.objects.create(
            evidence=evidence,
            control=control
        )
        
        response = self.client.post(
            f'/api/v1/organizations/viewer-org/evidence/{evidence.id}/analyze/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ============================================================================
# Run Tests
# ============================================================================
# python manage.py test cybertrust.apps.evidence.tests
# python manage.py test cybertrust.apps.controls.tests
