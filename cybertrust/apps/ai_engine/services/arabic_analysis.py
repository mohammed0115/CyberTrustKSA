"""Enhanced Arabic NLP Analysis Service."""
from __future__ import annotations

import json
import logging
from django.conf import settings
from django.db import transaction

from cybertrust.apps.controls.models import Control
from cybertrust.apps.ai_engine.models import AIAnalysisResult
from cybertrust.apps.evidence.models import Evidence

logger = logging.getLogger("ai_engine")


def get_arabic_analysis_prompt() -> str:
    """Get optimized system prompt for Arabic NLP analysis."""
    return """أنت محلل امتثال متخصص في إطار NCA (الهيئة الوطنية للأمن السيبراني) السعودي.

مهمتك تحليل الأدلة المقدمة وتقييم مدى امتثالها لضوابط الأمن السيبراني المحددة.

يجب عليك:
1. قراءة ومحاليل الأدلة بعناية
2. مقارنتها مع متطلبات الضابط
3. تحديد نقاط الامتثال والفجوات
4. تقديم درجة امتثال من 0-100
5. كتابة ملخص واضح بالعربية
6. تقديم توصيات عملية للتحسين

الإجابة يجب أن تكون JSON فقط بالصيغة التالية:
{
  "status": "COMPLIANT|PARTIAL|NON_COMPLIANT|UNKNOWN",
  "score": 0-100,
  "confidence": 0-100,
  "missing_points": ["...", "..."],
  "recommendations": ["...", "..."],
  "citations": [{"quote":"...","source":"..."}],
  "summary_ar": "ملخص شامل للتطابق والفجوات",
  "summary_en": "English summary for reference"
}"""


def analyze_evidence_arabic(
    evidence_text: str,
    control: Control,
    model_name: str | None = None
) -> dict:
    """
    Enhanced Arabic NLP analysis for control compliance.
    """
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai package is required for AI analysis")
    
    client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=30)
    model = model_name or getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")
    
    # Build Arabic-optimized messages
    messages = [
        {"role": "system", "content": get_arabic_analysis_prompt()},
        {
            "role": "user",
            "content": _build_arabic_analysis_prompt(control, evidence_text)
        }
    ]
    
    last_error = None
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            
            content = response.choices[0].message.content or "{}"
            
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                # Try to extract JSON from response
                start = content.find("{")
                end = content.rfind("}") + 1
                if start != -1 and end > start:
                    data = json.loads(content[start:end])
                else:
                    raise ValueError("Could not parse JSON response")
            
            # Ensure Arabic summary is present
            if not data.get("summary_ar"):
                data["summary_ar"] = _generate_fallback_summary_ar(data)
            
            data["model_name"] = model
            return data
        
        except Exception as exc:
            last_error = exc
            logger.exception("Arabic analysis attempt %s failed", attempt + 1)
            import time
            time.sleep(2 ** attempt)
    
    raise RuntimeError(f"Arabic analysis failed: {last_error}")


def _build_arabic_analysis_prompt(control: Control, evidence_text: str) -> str:
    """Build Arabic-optimized analysis prompt."""
    return f"""
ضابط السيطرة (NCA Control):
الكود: {control.code}
العنوان: {control. title_ar}
الوصف: {control.description_ar or ''}
البيانات المطلوبة: {control.required_evidence}

نص الدليل:
{evidence_text}

يرجى تحليل الدليل المقدم وتقييم مدى امتثاله لمتطلبات الضابط المحددة أعلاه.
"""


def _generate_fallback_summary_ar(analysis_data: dict) -> str:
    """Generate fallback Arabic summary if missing."""
    status = analysis_data.get("status", "UNKNOWN")
    score = analysis_data.get("score", 0)
    
    status_mapping = {
        "COMPLIANT": "متطابق تماماً",
        "PARTIAL": "متطابق جزئياً",
        "NON_COMPLIANT": "غير متطابق",
        "UNKNOWN": "غير محدد"
    }
    
    summary = f"الحالة: {status_mapping.get(status, status)}. الدرجة: {score}/100. "
    
    if analysis_data.get("missing_points"):
        summary += f"النقاط المفقودة: {', '.join(analysis_data['missing_points'][:3])}. "
    
    if analysis_data.get("recommendations"):
        summary += f"التوصيات: {', '.join(analysis_data['recommendations'][:2])}"
    
    return summary


def create_bilingual_analysis_result(
    organization,
    evidence: Evidence,
    control: Control,
    analysis_data: dict
) -> AIAnalysisResult:
    """Create bilingual analysis result."""
    result = AIAnalysisResult.objects.create(
        organization=organization,
        evidence=evidence,
        control=control,
        model_name=analysis_data.get("model_name", "openai"),
        score=analysis_data.get("score", 0),
        status=analysis_data.get("status", AIAnalysisResult.STATUS_UNKNOWN),
        confidence=analysis_data.get("confidence", 0),
        missing_points=analysis_data.get("missing_points", []),
        recommendations=analysis_data.get("recommendations", []),
        citations=analysis_data.get("citations", []),
        summary_ar=analysis_data.get("summary_ar", ""),
        summary_en=analysis_data.get("summary_en", ""),
        raw_json=analysis_data,
    )
    
    return result


def extract_and_analyze_arabic_document(file_path: str, control: Control) -> dict:
    """Extract text from document and perform Arabic analysis."""
    from cybertrust.apps.ai_engine.services import (
        extract_text_from_pdf,
        extract_text_from_docx,
        extract_text_from_image,
    )
    
    # Determine file type and extract text
    if file_path.endswith('.pdf'):
        text = extract_text_from_pdf(file_path)
    elif file_path.endswith(('.docx', '.doc')):
        text = extract_text_from_docx(file_path)
    elif file_path.endswith(('.png', '.jpg', '.jpeg')):
        text = extract_text_from_image(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_path}")
    
    # Perform Arabic analysis
    analysis = analyze_evidence_arabic(text, control)
    
    return analysis


def get_arabic_compliance_report(organization) -> dict:
    """Generate Arabic compliance report for organization."""
    from cybertrust.apps.controls.models import Control
    
    results = AIAnalysisResult.objects.filter(
        organization=organization
    ).select_related("control").order_by("control__code")
    
    compliant_count = results.filter(status=AIAnalysisResult.STATUS_COMPLIANT).count()
    partial_count = results.filter(status=AIAnalysisResult.STATUS_PARTIAL).count()
    non_compliant_count = results.filter(status=AIAnalysisResult.STATUS_NON_COMPLIANT).count()
    
    total_controls = Control.objects.filter(is_active=True).count()
    assessed_controls = results.values("control").distinct().count()
    
    report = {
        "organization": organization.name,
        "language": "ar",
        "total_controls": total_controls,
        "assessed_controls": assessed_controls,
        "compliance_summary": {
            "متطابق": compliant_count,
            "متطابق_جزئي": partial_count,
            "غير_متطابق": non_compliant_count,
        },
        "controls": []
    }
    
    for result in results:
        report["controls"].append({
            "code": result.control.code,
            "title": result.control.title_ar,
            "status": _translate_status_ar(result.status),
            "score": result.score,
            "summary": result.summary_ar,
            "recommendations": result.recommendations,
        })
    
    return report


def _translate_status_ar(status: str) -> str:
    """Translate status to Arabic."""
    mapping = {
        "COMPLIANT": "متطابق",
        "PARTIAL": "متطابق جزئياً",
        "NON_COMPLIANT": "غير متطابق",
        "UNKNOWN": "غير محدد"
    }
    return mapping.get(status, status)
