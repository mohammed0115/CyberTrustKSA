"""Vendor Questionnaire Service - Dynamic assessment generation."""
from __future__ import annotations

import json
from django.conf import settings
from django.utils import timezone

from cybertrust.apps.organizations.models import VendorAssessment, AssessmentQuestion, Organization


def generate_assessment_questions(num_questions: int = 5) -> list[dict]:
    """Generate initial assessment questions using OpenAI."""
    if not settings.OPENAI_API_KEY:
        return _get_default_questions(num_questions)
    
    try:
        from openai import OpenAI
    except ImportError:
        return _get_default_questions(num_questions)
    
    client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=30)
    
    prompt = f"""Generate {num_questions} assessment questions to determine if a vendor/organization should be classified as "General Services" or "High-Risk Services" for NCA compliance.

Requirements:
- Questions should be in both Arabic and English
- Focus on: data sensitivity, infrastructure type, handling of critical data, vulnerability to cyber attacks
- Make them yes/no or rating-based questions
- Return as JSON array with this structure:
[
  {{
    "question_ar": "...",
    "question_en": "...",
    "category": "general|data_protection|infrastructure|access_control|incident_response",
    "order": 1
  }},
  ...
]

Return ONLY the JSON array, no other text."""

    try:
        response = client.chat.completions.create(
            model=getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=2000,
        )
        
        content = response.choices[0].message.content
        # Extract JSON from response
        start = content.find('[')
        end = content.rfind(']') + 1
        
        if start != -1 and end > start:
            questions = json.loads(content[start:end])
            return questions
        else:
            return _get_default_questions(num_questions)
    
    except Exception:
        return _get_default_questions(num_questions)


def _get_default_questions(num_questions: int = 5) -> list[dict]:
    """Get default assessment questions if OpenAI fails."""
    default_questions = [
        {
            "question_ar": "هل تتعامل مؤسستك مع بيانات شخصية أو حساسة؟",
            "question_en": "Does your organization process personal or sensitive data?",
            "category": "data_protection",
            "order": 1
        },
        {
            "question_ar": "هل لديك بنية تحتية سحابية أو على الإنترنت مكشوفة؟",
            "question_en": "Do you have cloud or internet-exposed infrastructure?",
            "category": "infrastructure",
            "order": 2
        },
        {
            "question_ar": "هل تتعامل مع معلومات حكومية أو حساسة جداً؟",
            "question_en": "Do you handle government or highly sensitive information?",
            "category": "data_protection",
            "order": 3
        },
        {
            "question_ar": "هل لديك نظام مصادقة متعدد العوامل (MFA)؟",
            "question_en": "Do you implement multi-factor authentication (MFA)?",
            "category": "access_control",
            "order": 4
        },
        {
            "question_ar": "هل لديك خطة استجابة للحوادث الأمنية؟",
            "question_en": "Do you have an incident response plan?",
            "category": "incident_response",
            "order": 5
        },
    ]
    
    return default_questions[:num_questions]


def create_assessment_for_organization(organization: Organization) -> VendorAssessment:
    """Create a new assessment for an organization."""
    assessment, created = VendorAssessment.objects.get_or_create(
        organization=organization,
        defaults={"status": VendorAssessment.STATUS_PENDING}
    )
    return assessment


def submit_assessment_response(
    assessment: VendorAssessment,
    responses: dict
) -> VendorAssessment:
    """
    Submit assessment responses and determine vendor type.
    
    Args:
        assessment: VendorAssessment instance
        responses: Dict of question_id -> answer (e.g., {1: "yes", 2: 8})
    
    Returns:
        Updated VendorAssessment
    """
    assessment.responses = responses
    risk_score = calculate_risk_score(responses)
    assessment.risk_score = risk_score
    
    # Determine vendor type based on risk score
    if risk_score >= 60:
        assessment.vendor_type_determined = Organization.VENDOR_TYPE_HIGH_RISK
        assessment.organization.vendor_type = Organization.VENDOR_TYPE_HIGH_RISK
    else:
        assessment.vendor_type_determined = Organization.VENDOR_TYPE_GENERAL
        assessment.organization.vendor_type = Organization.VENDOR_TYPE_GENERAL
    
    assessment.status = VendorAssessment.STATUS_COMPLETED
    assessment.completed_at = timezone.now()
    assessment.save()
    assessment.organization.save()
    
    return assessment


def calculate_risk_score(responses: dict) -> int:
    """
    Calculate risk score from assessment responses.
    Scores towards 100 = higher risk = should be HIGH_RISK category.
    """
    if not responses:
        return 0
    
    risk_indicators = {
        "processes_personal_data": 20,
        "cloud_infrastructure": 15,
        "government_data": 35,
        "no_mfa": 20,
        "no_incident_response": 15,
    }
    
    score = 0
    
    # Simple scoring based on response keys
    for key, risk_points in risk_indicators.items():
        if responses.get(key) in [True, "yes", "YES", 1, "1"]:
            score += risk_points
        elif key.startswith("no_") and responses.get(key) not in [True, "yes", "YES"]:
            score += risk_points
    
    return min(score, 100)  # Cap at 100


def get_next_required_controls(organization: Organization) -> list:
    """Get NCA controls required based on vendor type."""
    from cybertrust.apps.controls.models import Control
    
    if organization.vendor_type == Organization.VENDOR_TYPE_HIGH_RISK:
        # High-risk vendors need all controls
        return Control.objects.filter(is_active=True).order_by("code")[:20]
    else:
        # General vendors need essential controls
        return Control.objects.filter(
            is_active=True,
            risk_level__in=[Control.RISK_HIGH, Control.RISK_MEDIUM]
        ).order_by("code")[:15]
