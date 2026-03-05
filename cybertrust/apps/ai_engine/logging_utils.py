"""AI Engine Logging & Error Handling Utilities."""
import logging
import functools
import traceback
from typing import Callable, Any
from django.http import JsonResponse
from django.conf import settings

# Configure loggers
ai_logger = logging.getLogger("ai_engine")
chatbot_logger = logging.getLogger("chatbot")
remediation_logger = logging.getLogger("remediation")
assessment_logger = logging.getLogger("assessment")


class AIEngineException(Exception):
    """Base exception for AI Engine errors."""
    def __init__(self, message: str, error_code: str = "AI_ERROR", details: dict = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)
    
    def to_dict(self) -> dict:
        return {
            "error": self.message,
            "error_code": self.error_code,
            "details": self.details
        }


class ChatbotException(AIEngineException):
    """Chatbot-specific exception."""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, "CHATBOT_ERROR", details)


class RemediationException(AIEngineException):
    """Remediation-specific exception."""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, "REMEDIATION_ERROR", details)


class AnalysisException(AIEngineException):
    """Analysis-specific exception."""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, "ANALYSIS_ERROR", details)


def log_api_call(logger: logging.Logger) -> Callable:
    """Decorator to log API calls with request/response data."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            request = next((arg for arg in args if hasattr(arg, 'user')), None)
            user_email = request.user.email if request and request.user else "anonymous"
            
            # Log request
            logger.info(
                f"API Call: {func.__name__}",
                extra={
                    "user": user_email,
                    "function": func.__name__,
                    "kwargs": str(kwargs)[:100],  # Truncate for security
                }
            )
            
            try:
                result = func(*args, **kwargs)
                logger.info(f"API Success: {func.__name__}", extra={"user": user_email})
                return result
            
            except Exception as e:
                logger.error(
                    f"API Error: {func.__name__}",
                    exc_info=True,
                    extra={
                        "user": user_email,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                )
                raise
        
        return wrapper
    return decorator


def handle_api_errors(func: Callable) -> Callable:
    """Decorator to handle API errors and return JSON responses."""
    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        try:
            return func(request, *args, **kwargs)
        
        except AIEngineException as e:
            logging.error(
                f"AI Engine Error: {e.error_code}",
                exc_info=True,
                extra={"details": e.details}
            )
            return JsonResponse({
                "success": False,
                **e.to_dict()
            }, status=400)
        
        except ValueError as e:
            logging.warning(f"Validation Error: {str(e)}")
            return JsonResponse({
                "success": False,
                "error": "Invalid input",
                "error_code": "VALIDATION_ERROR",
                "details": {"message": str(e)}
            }, status=400)
        
        except Exception as e:
            logging.error(
                f"Unexpected Error: {type(e).__name__}",
                exc_info=True,
                extra={"error": str(e)}
            )
            
            # Don't expose internal errors in production
            error_msg = str(e) if settings.DEBUG else "An error occurred processing your request"
            
            return JsonResponse({
                "success": False,
                "error": error_msg,
                "error_code": "INTERNAL_ERROR"
            }, status=500)
    
    return wrapper


def log_ai_analysis(control_code: str, org_name: str, status: str, score: int) -> None:
    """Log AI analysis results."""
    ai_logger.info(
        f"Analysis Complete: {control_code}",
        extra={
            "organization": org_name,
            "control_code": control_code,
            "status": status,
            "score": score,
            "timestamp": str(__import__('django.utils.timezone', fromlist=['now']).now())
        }
    )


def log_chatbot_interaction(user_email: str, org_name: str, message_len: int, language: str) -> None:
    """Log chatbot interactions."""
    chatbot_logger.info(
        f"Chatbot Message",
        extra={
            "user": user_email,
            "organization": org_name,
            "message_length": message_len,
            "language": language
        }
    )


def log_assessment_submission(org_name: str, vendor_type: str, risk_score: int) -> None:
    """Log assessment submissions."""
    assessment_logger.info(
        f"Assessment Submitted",
        extra={
            "organization": org_name,
            "vendor_type": vendor_type,
            "risk_score": risk_score
        }
    )


def log_remediation_progress(org_name: str, control_code: str, progress: int) -> None:
    """Log remediation progress."""
    remediation_logger.info(
        f"Remediation Progress",
        extra={
            "organization": org_name,
            "control_code": control_code,
            "progress_percent": progress
        }
    )


def get_error_response(error: Exception, logger: logging.Logger = None) -> dict:
    """Get standardized error response."""
    if logger:
        logger.error(
            f"Error: {type(error).__name__}",
            exc_info=True,
            extra={"error": str(error)}
        )
    
    if isinstance(error, AIEngineException):
        return error.to_dict()
    
    return {
        "error": str(error),
        "error_code": "ERROR",
        "details": {"type": type(error).__name__}
    }


# Configure logging handlers
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/ai_engine.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "formatter": "verbose",
        },
        "chatbot_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/chatbot.log",
            "maxBytes": 5242880,  # 5MB
            "backupCount": 3,
            "formatter": "verbose",
        },
        "analysis_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/analysis.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "formatter": "verbose",
        },
    },
    "loggers": {
        "ai_engine": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "chatbot": {
            "handlers": ["console", "chatbot_file"],
            "level": "INFO",
            "propagate": False,
        },
        "analysis": {
            "handlers": ["console", "analysis_file"],
            "level": "INFO",
            "propagate": False,
        },
    }
}
