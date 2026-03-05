"""Evidence Remediation Templates Service - Auto-generate fix suggestions."""
from __future__ import annotations

import json
from django.conf import settings
from django.utils import timezone

from cybertrust.apps.controls.models import Control
from cybertrust.apps.ai_engine.models import AIAnalysisResult


def generate_remediation_template(
    control: Control,
    missing_points: list[str],
    organization=None,
    language: str = "en"
) -> dict:
    """
    Generate remediation template for control compliance gaps.
    
    Args:
        control: Control instance with missing points
        missing_points: List of gaps identified in analysis
        organization: Organization context
        language: "ar" or "en"
    
    Returns:
        Dict with remediation steps and templates
    """
    if not settings.OPENAI_API_KEY:
        return get_default_remediation(control, missing_points, language)
    
    try:
        from openai import OpenAI
    except ImportError:
        return get_default_remediation(control, missing_points, language)
    
    client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=30)
    
    lang_suffix = " بالعربية" if language == "ar" else ""
    missing_text = "\n".join([f"- {point}" for point in missing_points[:5]])
    
    prompt = f"""Generate a remediation plan for the following NCA compliance gaps{lang_suffix}:

Control: {control.code} - {control.title_en}
Description: {control.description_en or ''}

Missing Points:
{missing_text}

Provide:
1. Step-by-step remediation actions (5-7 steps)
2. Estimated effort (hours)
3. Resources needed
4. Code/configuration snippets where applicable
5. Testing procedures to verify fix
6. Responsible team/role

Return as JSON with keys:
- steps (array): [{{order, description, effort_hours, accepted_by (role)}}]
- templates (array): [{{type, name, content}}]
- testing (array): verification steps
- timeline_days: estimated completion
- success_criteria: how to know it's done

Language: {"Arabic" if language == "ar" else "English"}"""

    try:
        response = client.chat.completions.create(
            model=getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=3000,
        )
        
        content = response.choices[0].message.content
        
        # Extract JSON from response
        start = content.find('{')
        end = content.rfind('}') + 1
        
        if start != -1 and end > start:
            template = json.loads(content[start:end])
            template["control_code"] = control.code
            template["language"] = language
            template["missing_points"] = missing_points
            return template
        else:
            return get_default_remediation(control, missing_points, language)
    
    except Exception:
        return get_default_remediation(control, missing_points, language)


def get_default_remediation(control: Control, missing_points: list, language: str) -> dict:
    """Get default remediation if OpenAI fails."""
    if language == "ar":
        return {
            "control_code": control.code,
            "language": "ar",
            "missing_points": missing_points,
            "steps": [
                {
                    "order": 1,
                    "description": "تحديد المسؤول: عيّن شخصاً مسؤولاً عن تنفيذ الإجراء",
                    "effort_hours": 1,
                    "accepted_by": "Security Officer"
                },
                {
                    "order": 2,
                    "description": "توثيق العملية الحالية",
                    "effort_hours": 2,
                    "accepted_by": "IT Manager"
                },
                {
                    "order": 3,
                    "description": "إعداد خطة التطبيق",
                    "effort_hours": 4,
                    "accepted_by": "Project Manager"
                },
                {
                    "order": 4,
                    "description": "تطبيق التحسينات في بيئة الاختبار",
                    "effort_hours": 8,
                    "accepted_by": "IT Team"
                },
                {
                    "order": 5,
                    "description": "الاختبار والتحقق",
                    "effort_hours": 4,
                    "accepted_by": "QA Team"
                },
                {
                    "order": 6,
                    "description": "نقل التغييرات إلى الإنتاج",
                    "effort_hours": 2,
                    "accepted_by": "IT Manager"
                }
            ],
            "timeline_days": 7,
            "testing": [
                "التحقق من تطبيق الإجراء",
                "اختبار الأداء والأمان",
                "توثيق النتائج"
            ]
        }
    
    return {
        "control_code": control.code,
        "language": "en",
        "missing_points": missing_points,
        "steps": [
            {
                "order": 1,
                "description": "Assign responsible party for remediation",
                "effort_hours": 1,
                "accepted_by": "Security Officer"
            },
            {
                "order": 2,
                "description": "Document current process",
                "effort_hours": 2,
                "accepted_by": "Process Owner"
            },
            {
                "order": 3,
                "description": "Create remediation plan",
                "effort_hours": 4,
                "accepted_by": "Project Manager"
            },
            {
                "order": 4,
                "description": "Implement in test environment",
                "effort_hours": 8,
                "accepted_by": "IT Team"
            },
            {
                "order": 5,
                "description": "Test and verify",
                "effort_hours": 4,
                "accepted_by": "QA Team"
            },
            {
                "order": 6,
                "description": "Deploy to production",
                "effort_hours": 2,
                "accepted_by": "IT Manager"
            }
        ],
        "timeline_days": 7,
        "testing": [
            "Verify implementation",
            "Performance and security testing",
            "Documentation review"
        ]
    }


def get_remediation_templates(control: Control, language: str = "en") -> list[dict]:
    """Get pre-built remediation templates for common control types."""
    templates = {
        "access_control": [
            {
                "name": "MFA Implementation",
                "type": "configuration",
                "description": "Enable multi-factor authentication",
                "snippet": """# Enable MFA in system
# Step 1: Install MFA module
pip install pyotp

# Step 2: Configure in settings.py
MFA_ENABLED = True
MFA_PROVIDER = 'google_authenticator'

# Step 3: Create backup codes
python manage.py create_backup_codes
"""
            },
            {
                "name": "Role-Based Access Control",
                "type": "code",
                "description": "Implement RBAC",
                "snippet": """# Define roles
ROLES = {
    'admin': ['read', 'write', 'delete'],
    'user': ['read'],
    'guest': ['read_public']
}

# Check access
def has_permission(user, action):
    role = user.role
    return action in ROLES.get(role, [])
"""
            }
        ],
        "data_protection": [
            {
                "name": "Data Encryption",
                "type": "configuration",
                "description": "Enable encryption at rest",
                "snippet": """# Encrypt sensitive data
from cryptography.fernet import Fernet

def encrypt_field(value):
    cipher = Fernet(settings.ENCRYPTION_KEY)
    return cipher.encrypt(value.encode())

def decrypt_field(encrypted_value):
    cipher = Fernet(settings.ENCRYPTION_KEY)
    return cipher.decrypt(encrypted_value).decode()
"""
            }
        ],
        "logging": [
            {
                "name": "Audit Logging",
                "type": "configuration",
                "description": "Enable comprehensive audit logging",
                "snippet": """# Configure audit logging
LOGGING = {
    'version': 1,
    'handlers': {
        'audit': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'audit.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
        }
    },
    'loggers': {
        'audit': {'handlers': ['audit'], 'level': 'INFO'}
    }
}
"""
            }
        ]
    }
    
    # Find templates for control type
    control_keywords = [control.code.lower(), control.category.name_en.lower() if hasattr(control.category, 'name_en') else '']
    
    matching_templates = []
    for category, template_list in templates.items():
        if any(keyword.startswith(category[:5]) for keyword in control_keywords):
            matching_templates.extend(template_list)
    
    return matching_templates[:3]  # Return top 3 templates


class RemediationTracker:
    """Track remediation progress for controls."""
    
    @staticmethod
    def create_remediation_task(
        control: Control,
        organization,
        assigned_to,
        template: dict,
        due_date=None
    ) -> dict:
        """Create a remediation task."""
        return {
            "control_code": control.code,
            "organization": organization.name,
            "assigned_to": assigned_to,
            "status": "pending",
            "template": template.get("control_code", ""),
            "steps_completed": 0,
            "total_steps": len(template.get("steps", [])),
            "due_date": due_date,
            "created_at": str(timezone.now()),
        }
    
    @staticmethod
    def get_remediation_status(control: Control, organization) -> dict:
        """Get remediation status for a control."""
        # Get latest analysis
        latest = (
            AIAnalysisResult.objects
            .filter(organization=organization, control=control)
            .order_by("-created_at")
            .first()
        )
        
        if not latest:
            return {"status": "not_started"}
        
        return {
            "control_code": control.code,
            "last_score": latest.score,
            "last_status": latest.status,
            "missing_points": latest.missing_points,
            "recommendations": latest.recommendations,
            "last_analysis": str(latest.created_at),
        }
    
    @staticmethod
    def track_remediation_progress(
        control: Control,
        organization,
        completed_steps: int,
        total_steps: int,
        notes: str = ""
    ) -> dict:
        """Update remediation progress."""
        progress_percent = (completed_steps / total_steps * 100) if total_steps > 0 else 0
        
        return {
            "control_code": control.code,
            "progress_percent": int(progress_percent),
            "completed_steps": completed_steps,
            "total_steps": total_steps,
            "status": "in_progress" if progress_percent < 100 else "completed",
            "notes": notes,
            "updated_at": str(timezone.now()),
        }
