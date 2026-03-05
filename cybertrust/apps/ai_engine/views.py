"""AI Engine Views - Chatbot API endpoints."""
import asyncio
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from cybertrust.apps.ai_engine.services import (
    chat_with_ciso,
    get_conversation_history,
    clear_conversation_history,
)


@login_required
@require_http_methods(["POST"])
def chatbot_message(request, slug=None):
    """
    API endpoint for Virtual CISO chatbot.
    
    POST data:
    {
        "message": "Your question here",
        "language": "en" or "ar"
    }
    """
    try:
        import json
        data = json.loads(request.body)
        user_message = data.get("message", "").strip()
        language = data.get("language", "en")
        
        if not user_message:
            return JsonResponse({"error": "Message cannot be empty"}, status=400)
        
        if language not in ["ar", "en"]:
            language = "en"
        
        # Get organization if slug is provided
        organization = None
        if slug and hasattr(request, 'current_org'):
            organization = request.current_org
        
        # Get conversation context
        context = get_conversation_history(
            organization=organization,
            user=request.user,
            limit=10
        )
        
        # Convert context to OpenAI format
        context_messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in context
        ]
        
        # Send to chatbot (run async in sync context)
        try:
            result = asyncio.run(
                chat_with_ciso(
                    user_message=user_message,
                    organization=organization,
                    user=request.user,
                    language=language,
                    conversation_context=context_messages,
                )
            )
        except TypeError:
            # asyncio.run might not work in all contexts, fallback to sync call
            from cybertrust.apps.ai_engine.models import ChatMessage
            from django.conf import settings
            from openai import OpenAI
            
            if not settings.OPENAI_API_KEY:
                raise RuntimeError("OPENAI_API_KEY is not configured.")
            
            client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=30)
            
            messages = [
                {"role": "system", "content": _get_ciso_prompt(language)}
            ] + context_messages[-6:] + [
                {"role": "user", "content": user_message}
            ]
            
            response = client.chat.completions.create(
                model=getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
                messages=messages,
                temperature=0.7,
                max_tokens=1024,
            )
            
            assistant_response = response.choices[0].message.content
            
            # Save messages
            user_msg = ChatMessage.objects.create(
                organization=organization,
                user=request.user,
                role=ChatMessage.ROLE_USER,
                content=user_message,
                language=language,
            )
            
            assistant_msg = ChatMessage.objects.create(
                organization=organization,
                user=request.user,
                role=ChatMessage.ROLE_ASSISTANT,
                content=assistant_response,
                language=language,
            )
            
            result = {
                "response": assistant_response,
                "message_id": assistant_msg.id,
                "user_message_id": user_msg.id,
            }
        
        return JsonResponse({
            "success": True,
            "response": result["response"],
            "message_id": result["message_id"],
        })
    
    except Exception as exc:
        return JsonResponse({
            "error": str(exc)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def chatbot_history(request, slug=None):
    """Get conversation history."""
    try:
        organization = None
        if slug and hasattr(request, 'current_org'):
            organization = request.current_org
        
        limit = request.GET.get("limit", 20)
        try:
            limit = int(limit)
        except ValueError:
            limit = 20
        
        history = get_conversation_history(
            organization=organization,
            user=request.user,
            limit=limit
        )
        
        return JsonResponse({
            "success": True,
            "messages": history,
        })
    
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


@login_required
@require_http_methods(["POST"])
def chatbot_clear(request, slug=None):
    """Clear conversation history."""
    try:
        organization = None
        if slug and hasattr(request, 'current_org'):
            organization = request.current_org
        
        count = clear_conversation_history(
            organization=organization,
            user=request.user
        )
        
        return JsonResponse({
            "success": True,
            "cleared_count": count,
        })
    
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


def _get_ciso_prompt(language="en"):
    """Get system prompt for CISO."""
    if language == "ar":
        return """أنت مساعد أمان سيبراني متخصص يعمل كـ "CISO افتراضي" لتوجيه المؤسسات نحو الامتثال لضوابط NCA (الهيئة الوطنية للأمن السيبراني) السعودية."""
    return """You are a specialized Cybersecurity Assistant working as a "Virtual CISO" to guide organizations toward NCA (National Cybersecurity Authority - Saudi Arabia) compliance."""


# Remediation API Endpoints
@login_required
@require_http_methods(["GET"])
def get_remediation_template(request, control_id, slug=None):
    """Get remediation template for a control."""
    try:
        from cybertrust.apps.controls.models import Control
        from cybertrust.apps.ai_engine.services import (
            generate_remediation_template,
            RemediationTracker,
        )
        
        organization = None
        if slug and hasattr(request, 'current_org'):
            organization = request.current_org
        
        control = Control.objects.get(id=control_id)        
        language = request.GET.get("lang", "en")
        
        # Get latest analysis for this control
        status = RemediationTracker.get_remediation_status(control, organization) if organization else {}
        missing_points = status.get("missing_points", [])
        
        # Generate remediation template
        template = generate_remediation_template(
            control=control,
            missing_points=missing_points,
            organization=organization,
            language=language
        )
        
        return JsonResponse({
            "success": True,
            "template": template,
            "analysis_status": status,
        })
    
    except Control.DoesNotExist:
        return JsonResponse({"error": "Control not found"}, status=404)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


@login_required
@require_http_methods(["GET"])
def list_remediation_templates(request, control_id):
    """List pre-built remediation templates."""
    try:
        from cybertrust.apps.controls.models import Control
        from cybertrust.apps.ai_engine.services import get_remediation_templates
        
        control = Control.objects.get(id=control_id)
        language = request.GET.get("lang", "en")
        
        templates = get_remediation_templates(control, language)
        
        return JsonResponse({
            "success": True,
            "control_code": control.code,
            "templates": templates,
        })
    
    except Control.DoesNotExist:
        return JsonResponse({"error": "Control not found"}, status=404)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


@login_required
@require_http_methods(["POST"])
def track_remediation(request, control_id, slug=None):
    """Track remediation progress."""
    try:
        import json
        from cybertrust.apps.controls.models import Control
        from cybertrust.apps.ai_engine.services import RemediationTracker
        
        organization = None
        if slug and hasattr(request, 'current_org'):
            organization = request.current_org
        
        control = Control.objects.get(id=control_id)
        data = json.loads(request.body)
        
        completed_steps = data.get("completed_steps", 0)
        total_steps = data.get("total_steps", 0)
        notes = data.get("notes", "")
        
        progress = RemediationTracker.track_remediation_progress(
            control=control,
            organization=organization,
            completed_steps=completed_steps,
            total_steps=total_steps,
            notes=notes
        )
        
        return JsonResponse({
            "success": True,
            "progress": progress,
        })
    
    except Control.DoesNotExist:
        return JsonResponse({"error": "Control not found"}, status=404)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)
