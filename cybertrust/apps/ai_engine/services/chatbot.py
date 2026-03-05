"""Virtual CISO Chatbot Service - AI-powered guidance for vendors."""
from __future__ import annotations

import json
from decouple import config
from django.conf import settings

from cybertrust.apps.ai_engine.models import ChatMessage


def get_ciso_system_prompt(language: str = "en") -> str:
    """Get the system prompt for Virtual CISO based on language."""
    if language == "ar":
        return """أنت مساعد أمان سيبراني متخصص يعمل كـ "CISO افتراضي" لتوجيه المؤسسات نحو الامتثال لضوابط NCA (الهيئة الوطنية للأمن السيبراني) السعودية.

دورك:
1. الإجابة على أسئلة حول ضوابط الأمن السيبراني والامتثال لـ NCA
2. توفير إرشادات عملية لتحسين موقف الأمن
3. اقتراح أفضل الممارسات والحلول
4. تقديم شرح واضح للمتطلبات المعقدة
5. توجيه المستخدمين خطوة بخطوة

اللغة: الإجابة بالعربية فقط ما لم يطلب خلاف ذلك
التوازن: كن ودياً لكن احترافياً
التركيز: NCA, التشريعات السعودية، أمثلة محلية"""
    else:
        return """You are a specialized Cybersecurity Assistant working as a "Virtual CISO" to guide organizations toward NCA (National Cybersecurity Authority - Saudi Arabia) compliance.

Your role:
1. Answer questions about cybersecurity controls and NCA compliance
2. Provide practical guidance for improving security posture
3. Suggest best practices and solutions
4. Explain complex requirements clearly
5. Guide users step-by-step through compliance challenges

Language: Respond in English only unless otherwise requested
Tone: Friendly but professional
Focus: NCA controls, Saudi regulations, local examples"""


async def chat_with_ciso(
    user_message: str,
    organization=None,
    user=None,
    language: str = "en",
    conversation_context: list = None,
) -> dict:
    """
    Send a message to Virtual CISO and get a response.
    
    Args:
        user_message: The user's question/statement
        organization: Organization object (optional)
        user: User object (optional)
        language: "ar" or "en"
        conversation_context: List of previous messages for context
    
    Returns:
        Dict with 'response' and 'message_id'
    """
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai package is required for chatbot")
    
    client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=30)
    
    # Build conversation messages
    messages = [
        {"role": "system", "content": get_ciso_system_prompt(language)}
    ]
    
    # Add conversation context if provided
    if conversation_context:
        messages.extend(conversation_context[-6:])  # Last 6 messages for context window
    
    # Add current user message
    messages.append({"role": "user", "content": user_message})
    
    try:
        response = client.chat.completions.create(
            model=getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
        )
        
        assistant_response = response.choices[0].message.content
        
        # Save user message
        user_msg = ChatMessage.objects.create(
            organization=organization,
            user=user,
            role=ChatMessage.ROLE_USER,
            content=user_message,
            language=language,
        )
        
        # Save assistant response
        assistant_msg = ChatMessage.objects.create(
            organization=organization,
            user=user,
            role=ChatMessage.ROLE_ASSISTANT,
            content=assistant_response,
            language=language,
        )
        
        return {
            "response": assistant_response,
            "message_id": assistant_msg.id,
            "user_message_id": user_msg.id,
        }
    
    except Exception as exc:
        raise RuntimeError(f"Chatbot error: {str(exc)}") from exc


def get_conversation_history(organization=None, user=None, limit: int = 10) -> list:
    """Get recent conversation history."""
    query = ChatMessage.objects.all()
    
    if organization:
        query = query.filter(organization=organization)
    if user:
        query = query.filter(user=user)
    
    messages = list(query.order_by("-created_at")[:limit][::-1])
    
    return [
        {
            "role": msg.role,
            "content": msg.content,
            "timestamp": msg.created_at.isoformat(),
        }
        for msg in messages
    ]


def clear_conversation_history(organization=None, user=None) -> int:
    """Clear chatbot conversation history."""
    query = ChatMessage.objects.all()
    
    if organization:
        query = query.filter(organization=organization)
    if user:
        query = query.filter(user=user)
    
    count, _ = query.delete()
    return count
