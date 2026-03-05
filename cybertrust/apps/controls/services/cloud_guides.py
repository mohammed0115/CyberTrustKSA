"""Cloud Integration Guide Generator - Auto-generate cloud setup guides."""
from __future__ import annotations

from django.conf import settings


def generate_cloud_guide(
    provider: str, 
    requirement_type: str = "mfa",
    language: str = "en"
) -> dict:
    """
    Generate cloud integration guide for a specific provider and requirement.
    
    Args:
        provider: "aws", "azure", or "alibaba"
        requirement_type: "mfa", "encryption", "logging", "vpc", "backup"
        language: "ar" or "en"
    
    Returns:
        Dict with guide content
    """
    if not settings.OPENAI_API_KEY:
        return get_default_guide(provider, requirement_type, language)
    
    try:
        from openai import OpenAI
    except ImportError:
        return get_default_guide(provider, requirement_type, language)
    
    client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=30)
    
    lang_instruction = "Arabic" if language == "ar" else "English"
    
    prompt = f"""Generate a comprehensive integration guide for {provider.upper()} cloud platform to implement {requirement_type.upper()} for NCA compliance.

Include:
1. Prerequisites and setup steps
2. Configuration instructions (with examples)
3. Step-by-step walkthrough
4. Security best practices
5. Testing and verification
6. Code snippets where applicable

Language: {lang_instruction}
Format: Return as JSON with keys: title, description, prerequisites, steps (array), code_snippets (array), validation_steps

Make it practical and actionable for engineers."""

    try:
        response = client.chat.completions.create(
            model=getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=3000,
        )
        
        import json
        content = response.choices[0].message.content
        
        # Extract JSON from response
        start = content.find('{')
        end = content.rfind('}') + 1
        
        if start != -1 and end > start:
            guide = json.loads(content[start:end])
            guide["provider"] = provider
            guide["requirement_type"] = requirement_type
            guide["language"] = language
            return guide
        else:
            return get_default_guide(provider, requirement_type, language)
    
    except Exception:
        return get_default_guide(provider, requirement_type, language)


def get_default_guide(provider: str, requirement_type: str, language: str) -> dict:
    """Get default guide if OpenAI generation fails."""
    guides = {
        "aws": {
            "mfa": {
                "ar": {
                    "title": "دليل AWS MFA - التحقق متعدد العوامل",
                    "description": "إعداد المصادقة متعددة العوامل على AWS لتحقيق نمعايير NCA",
                    "prerequisites": ["AWS IAM Admin Access", "معرفة بـ AWS Console"],
                    "steps": [
                        "1. انتقل إلى IAM Dashboard في AWS Console",
                        "2. اختر Users من القائمة الجانبية",
                        "3. اختر المستخدم الذي تريد تفعيل MFA له",
                        "4. اذهب إلى Security Credentials tab",
                        "5. في 'Multi-factor authentication (MFA)' اضغط على 'Assign MFA device'",
                        "6. اختر نوع الجهاز (Virtual, Hardware, U2F)",
                        "7. اتبع خطوات المصادقة"
                    ],
                    "code_snippets": [
                        "# AWS CLI لتفعيل MFA\naws iam enable-mfa-device --user-name username --serial-number arn:aws:iam::123456789:mfa/device-name --authentication-code1 123456 --authentication-code2 789012"
                    ],
                    "validation_steps": ["اختبر تسجيل الدخول باستخدام MFA", "تحقق من تقارير الوصول"]
                },
                "en": {
                    "title": "AWS MFA Setup Guide - Multi-Factor Authentication",
                    "description": "Configure multi-factor authentication on AWS to meet NCA compliance requirements",
                    "prerequisites": ["AWS IAM Admin Access", "Knowledge of AWS Console"],
                    "steps": [
                        "1. Navigate to IAM Dashboard in AWS Console",
                        "2. Select Users from the left sidebar",
                        "3. Click on the user you want to enable MFA for",
                        "4. Go to the Security Credentials tab",
                        "5. Under 'Multi-factor authentication (MFA)' click 'Assign MFA device'",
                        "6. Choose device type (Virtual, Hardware, U2F)",
                        "7. Follow authentication steps"
                    ],
                    "code_snippets": [
                        "# AWS CLI to enable MFA\naws iam enable-mfa-device --user-name username --serial-number arn:aws:iam::123456789:mfa/device-name --authentication-code1 123456 --authentication-code2 789012"
                    ],
                    "validation_steps": ["Test login with MFA enabled", "Review access reports"]
                }
            },
            "encryption": {
                "en": {
                    "title": "AWS Encryption Guide",
                    "description": "Enable encryption at rest and in transit for AWS resources",
                    "prerequisites": ["AWS KMS access", "S3/RDS management permissions"],
                    "steps": [
                        "1. Create or select AWS KMS customer-managed key",
                        "2. For S3: Enable default encryption with KMS",
                        "3. For RDS: Enable encryption with KMS",
                        "4. For EBS: Create snapshots with encryption enabled",
                        "5. Configure TLS 1.2+ for data in transit"
                    ],
                    "code_snippets": [
                        "# S3 bucket encryption\naws s3api put-bucket-encryption --bucket mybucket --server-side-encryption-configuration 'Rules=[{ApplyServerSideEncryptionByDefault={SSEAlgorithm=aws:kms,KMSMasterKeyID=arn:aws:kms:region:account:key/id}}]'"
                    ],
                    "validation_steps": ["Verify encryption settings in AWS Console", "Test key rotation"]
                }
            }
        },
        "azure": {
            "mfa": {
                "en": {
                    "title": "Azure MFA Configuration",
                    "description": "Enable MFA across your Azure subscription",
                    "prerequisites": ["Azure AD tenant access", "User management rights"],
                    "steps": [
                        "1. Go to Azure AD > Security > MFA Server",
                        "2. Enable Azure MFA for users",
                        "3. Register MFA methods (phone, app, security key)",
                        "4. Configure enforcement policy",
                        "5. Enable conditional access rules"
                    ],
                    "code_snippets": [
                        "# PowerShell to enable MFA\nSet-AzureADUser -ObjectId user@domain.com -StrongAuthenticationRequirements @([Microsoft.Online.Administration.StrongAuthenticationRequirement]::new())"
                    ],
                    "validation_steps": ["Test MFA login", "Review MFA adoption reports"]
                }
            }
        }
    }
    
    if provider in guides and requirement_type in guides[provider]:
        return guides[provider][requirement_type].get(language, guides[provider][requirement_type].get("en", {}))
    
    return {
        "title": f"{provider.upper()} Setup Guide",
        "description": f"Setup {requirement_type} for {provider.upper()}",
        "steps": ["Contact support for detailed guidance"],
        "provider": provider,
        "requirement_type": requirement_type,
        "language": language
    }


def get_all_cloud_guides(organization=None) -> list[dict]:
    """Get all available cloud integration guides."""
    providers = ["aws", "azure", "alibaba"]
    requirements = ["mfa", "encryption", "logging", "vpc", "backup"]
    languages = ["en", "ar"]
    
    guides = []
    for provider in providers:
        for req in requirements:
            for lang in languages:
                guides.append({
                    "provider": provider,
                    "requirement": req,
                    "language": lang,
                    "url": f"/api/cloud-guides/{provider}/{req}/?lang={lang}"
                })
    
    return guides


def generate_integration_checklist(provider: str, organization=None, language: str = "en") -> dict:
    """
    Generate full integration checklist for a cloud provider.
    """
    requirements = ["mfa", "encryption", "logging", "vpc", "backup", "access_control", "incident_response"]
    
    checklist = {
        "provider": provider,
        "organization": organization.name if organization else "N/A",
        "language": language,
        "created_at": str(__import__('django.utils.timezone', fromlist=['now']).now()),
        "items": []
    }
    
    for req in requirements:
        guide = generate_cloud_guide(provider, req, language)
        checklist["items"].append({
            "requirement": req,
            "status": "pending",
            "guide_title": guide.get("title", ""),
            "description": guide.get("description", ""),
            "estimated_hours": 2 if req != "mfa" else 1
        })
    
    return checklist
