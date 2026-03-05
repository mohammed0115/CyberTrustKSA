"""
Production Deployment & OpenAI Monitoring Guide

This module provides utilities for monitoring OpenAI API usage,
tracking costs, implementing rate limiting, and health checks.

Usage:
    # Track API usage
    from cybertrust.apps.ai_engine.monitoring import track_api_call
    track_api_call(
        feature="chatbot",
        tokens_used=150,
        cost_usd=0.001,
        success=True
    )
    
    # Get cost reports
    from cybertrust.apps.ai_engine.monitoring import get_openai_cost_report
    report = get_openai_cost_report(days=30)
    
    # Check service health
    from cybertrust.apps.ai_engine.monitoring import check_service_health
    status = check_service_health()
"""

from datetime import datetime, timedelta
from django.core.cache import cache
from django.db import models
from django.utils import timezone
import json
import logging

logger = logging.getLogger("ai_engine")


# ===== Models for Cost Tracking =====

class APICallLog(models.Model):
    """Log all API calls for monitoring and cost analysis."""
    
    FEATURE_CHOICES = (
        ("chatbot", "Virtual CISO Chatbot"),
        ("assessment", "Vendor Assessment"),
        ("remediation", "Remediation Generator"),
        ("cloud_guide", "Cloud Integration Guide"),
        ("analysis", "Evidence Analysis"),
    )
    
    STATUS_CHOICES = (
        ("success", "Success"),
        ("failure", "Failure"),
        ("timeout", "Timeout"),
        ("rate_limited", "Rate Limited"),
    )
    
    feature = models.CharField(max_length=50, choices=FEATURE_CHOICES)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="api_calls",
        null=True,
        blank=True
    )
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="api_calls",
        null=True,
        blank=True
    )
    
    # API details
    model_used = models.CharField(max_length=100, default="gpt-4o-mini")
    tokens_prompt = models.IntegerField(default=0)
    tokens_completion = models.IntegerField(default=0)
    tokens_total = models.IntegerField(default=0)
    
    # Cost tracking
    cost_usd = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=0.000001
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    error_message = models.TextField(blank=True, null=True)
    
    # Response time
    duration_ms = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["feature", "created_at"]),
            models.Index(fields=["organization", "created_at"]),
            models.Index(fields=["created_at"]),
        ]
    
    def __str__(self):
        return f"{self.feature} - {self.status} - ${self.cost_usd}"


# ===== Monitoring Functions =====

def track_api_call(
    feature: str,
    organization=None,
    user=None,
    tokens_prompt: int = 0,
    tokens_completion: int = 0,
    cost_usd: float = 0.0,
    status: str = "success",
    error_message: str = "",
    duration_ms: int = 0,
    model: str = "gpt-4o-mini"
) -> APICallLog:
    """
    Track an API call for monitoring and cost analysis.
    
    Args:
        feature: Feature name from FEATURE_CHOICES
        organization: Organization making the call
        user: User making the call
        tokens_prompt: Tokens used in prompt
        tokens_completion: Tokens used in completion
        cost_usd: Cost in USD
        status: Status of the call
        error_message: Error message if failed
        duration_ms: Duration in milliseconds
        model: Model used
    
    Returns:
        APICallLog instance
    """
    log = APICallLog.objects.create(
        feature=feature,
        organization=organization,
        user=user,
        model_used=model,
        tokens_prompt=tokens_prompt,
        tokens_completion=tokens_completion,
        tokens_total=tokens_prompt + tokens_completion,
        cost_usd=cost_usd,
        status=status,
        error_message=error_message,
        duration_ms=duration_ms
    )
    
    # Invalidate cache to update reports
    cache.delete(f"api_cost_report_{7}d")
    cache.delete(f"api_cost_report_{30}d")
    
    logger.info(
        f"API Call: {feature} | "
        f"Tokens: {log.tokens_total} | "
        f"Cost: ${cost_usd} | "
        f"Status: {status}"
    )
    
    return log


def get_openai_cost_report(days: int = 30) -> dict:
    """
    Generate cost report for OpenAI API usage.
    
    Args:
        days: Number of days to analyze
    
    Returns:
        Dict with cost analysis
    """
    # Try cache first
    cache_key = f"api_cost_report_{days}d"
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    cutoff_date = timezone.now() - timedelta(days=days)
    logs = APICallLog.objects.filter(
        created_at__gte=cutoff_date,
        status="success"
    )
    
    total_cost = sum(log.cost_usd for log in logs)
    total_tokens = sum(log.tokens_total for log in logs)
    total_calls = logs.count()
    
    # Calculate by feature
    by_feature = {}
    for feature, _ in APICallLog.FEATURE_CHOICES:
        feature_logs = logs.filter(feature=feature)
        by_feature[feature] = {
            "calls": feature_logs.count(),
            "tokens": sum(log.tokens_total for log in feature_logs),
            "cost": float(sum(log.cost_usd for log in feature_logs)),
            "avg_duration_ms": sum(log.duration_ms for log in feature_logs) /
                              (feature_logs.count() or 1)
        }
    
    # Calculate by organization
    by_org = {}
    for log in logs:
        org_name = log.organization.name if log.organization else "Unknown"
        if org_name not in by_org:
            by_org[org_name] = {
                "calls": 0,
                "tokens": 0,
                "cost": 0.0
            }
        by_org[org_name]["calls"] += 1
        by_org[org_name]["tokens"] += log.tokens_total
        by_org[org_name]["cost"] += float(log.cost_usd)
    
    report = {
        "period_days": days,
        "date_start": (timezone.now() - timedelta(days=days)).isoformat(),
        "date_end": timezone.now().isoformat(),
        "summary": {
            "total_cost_usd": float(total_cost),
            "total_tokens": total_tokens,
            "total_calls": total_calls,
            "avg_cost_per_call": float(total_cost / (total_calls or 1)),
            "avg_tokens_per_call": int(total_tokens / (total_calls or 1)) if total_calls else 0
        },
        "by_feature": by_feature,
        "by_organization": by_org,
        "cost_trend": get_cost_trend(days)
    }
    
    # Cache for 1 hour
    cache.set(cache_key, report, 3600)
    
    return report


def get_cost_trend(days: int = 30) -> list:
    """
    Get daily cost trend over specified days.
    
    Returns:
        List of dicts with date and cost
    """
    trend = []
    for d in range(days, 0, -1):
        day_start = timezone.now() - timedelta(days=d)
        day_end = day_start + timedelta(days=1)
        
        daily_logs = APICallLog.objects.filter(
            created_at__gte=day_start,
            created_at__lt=day_end,
            status="success"
        )
        
        daily_cost = sum(log.cost_usd for log in daily_logs)
        
        trend.append({
            "date": day_start.date().isoformat(),
            "cost_usd": float(daily_cost),
            "calls": daily_logs.count()
        })
    
    return trend


def get_error_report(days: int = 7) -> dict:
    """
    Generate error report for API failures.
    
    Returns:
        Dict with error metrics
    """
    cutoff_date = timezone.now() - timedelta(days=days)
    error_logs = APICallLog.objects.filter(
        created_at__gte=cutoff_date
    ).exclude(status="success")
    
    by_status = {}
    for status, _ in APICallLog.STATUS_CHOICES:
        logs = error_logs.filter(status=status)
        by_status[status] = {
            "count": logs.count(),
            "percentage": (logs.count() / (error_logs.count() or 1)) * 100
        }
    
    by_feature = {}
    for feature, _ in APICallLog.FEATURE_CHOICES:
        logs = error_logs.filter(feature=feature)
        by_feature[feature] = {
            "count": logs.count(),
            "latest_error": logs.first().error_message if logs.exists() else None
        }
    
    return {
        "period_days": days,
        "total_errors": error_logs.count(),
        "by_status": by_status,
        "by_feature": by_feature,
        "error_rate_percent": (error_logs.count() / (
            APICallLog.objects.filter(created_at__gte=cutoff_date).count() or 1
        )) * 100
    }


# ===== Rate Limiting =====

class RateLimiter:
    """
    Rate limiter for OpenAI API calls.
    
    Usage:
        limiter = RateLimiter(feature="chatbot", calls_per_minute=60)
        if limiter.is_allowed("user_123"):
            # Make API call
        else:
            # Return rate limit error
    """
    
    def __init__(self, feature: str, calls_per_minute: int = 60):
        self.feature = feature
        self.calls_per_minute = calls_per_minute
        self.window_seconds = 60
    
    def is_allowed(self, key: str) -> bool:
        """
        Check if API call is allowed for key.
        
        Args:
            key: User ID or organization ID
        
        Returns:
            True if allowed, False if rate limited
        """
        cache_key = f"rate_limit:{self.feature}:{key}"
        call_count = cache.get(cache_key, 0)
        
        if call_count >= self.calls_per_minute:
            logger.warning(
                f"Rate limit exceeded for {self.feature} by {key}"
            )
            return False
        
        # Increment counter
        cache.set(
            cache_key,
            call_count + 1,
            self.window_seconds
        )
        
        return True
    
    def get_remaining(self, key: str) -> int:
        """Get remaining calls for key."""
        cache_key = f"rate_limit:{self.feature}:{key}"
        call_count = cache.get(cache_key, 0)
        return max(0, self.calls_per_minute - call_count)


# ===== Health Checks =====

def check_service_health() -> dict:
    """
    Check health of AI services.
    
    Returns:
        Dict with service status
    """
    health = {
        "timestamp": timezone.now().isoformat(),
        "services": {},
        "overall_status": "healthy"
    }
    
    # Check database
    try:
        APICallLog.objects.count()
        health["services"]["database"] = "healthy"
    except Exception as e:
        health["services"]["database"] = "unhealthy"
        health["overall_status"] = "degraded"
        logger.error(f"Database health check failed: {e}")
    
    # Check OpenAI API (simple connectivity test)
    health["services"]["openai_api"] = check_openai_connectivity()
    if health["services"]["openai_api"] != "healthy":
        health["overall_status"] = "degraded"
    
    # Check recent error rate
    error_report = get_error_report(days=1)
    if error_report["error_rate_percent"] > 10:  # >10% error rate
        health["services"]["error_rate"] = "warning"
        health["overall_status"] = "degraded"
    else:
        health["services"]["error_rate"] = "healthy"
    
    # Check response times
    recent_logs = APICallLog.objects.filter(
        created_at__gte=timezone.now() - timedelta(hours=1),
        status="success"
    )
    if recent_logs.exists():
        avg_duration = sum(log.duration_ms for log in recent_logs) / recent_logs.count()
        if avg_duration > 5000:  # >5 seconds
            health["services"]["response_time"] = "warning"
        else:
            health["services"]["response_time"] = "healthy"
    
    return health


def check_openai_connectivity() -> str:
    """
    Check OpenAI API connectivity.
    
    Returns:
        "healthy" or "unhealthy"
    """
    try:
        from openai import OpenAI
        from django.conf import settings
        
        client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=5)
        
        # Simple API call to check connectivity
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=1
        )
        
        return "healthy"
    except Exception as e:
        logger.error(f"OpenAI connectivity check failed: {e}")
        return "unhealthy"


# ===== Alerts =====

def check_cost_threshold(threshold_usd: float = 100.0) -> bool:
    """
    Check if daily cost exceeds threshold.
    
    Args:
        threshold_usd: Daily cost threshold
    
    Returns:
        True if exceeded
    """
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_logs = APICallLog.objects.filter(
        created_at__gte=today_start,
        status="success"
    )
    
    daily_cost = sum(log.cost_usd for log in today_logs)
    
    if daily_cost > threshold_usd:
        logger.warning(
            f"Daily cost threshold exceeded: ${daily_cost:.2f} > ${threshold_usd:.2f}"
        )
        return True
    
    return False


def check_error_rate_threshold(threshold_percent: float = 5.0, hours: int = 1) -> bool:
    """
    Check if error rate exceeds threshold.
    
    Args:
        threshold_percent: Error rate threshold percentage
        hours: Time window in hours
    
    Returns:
        True if exceeded
    """
    cutoff_date = timezone.now() - timedelta(hours=hours)
    all_logs = APICallLog.objects.filter(created_at__gte=cutoff_date)
    error_logs = all_logs.exclude(status="success")
    
    if all_logs.count() == 0:
        return False
    
    error_rate = (error_logs.count() / all_logs.count()) * 100
    
    if error_rate > threshold_percent:
        logger.warning(
            f"Error rate threshold exceeded: {error_rate:.2f}% > {threshold_percent}%"
        )
        return True
    
    return False


# ===== Management Command Integration =====

def get_monitoring_summary() -> str:
    """
    Get formatted monitoring summary.
    
    Returns:
        Formatted string for display
    """
    health = check_service_health()
    cost_report = get_openai_cost_report(days=7)
    error_report = get_error_report(days=7)
    
    summary = f"""
╔══════════════════════════════════════════════════════════╗
║         OpenAI API Monitoring Summary                    ║
╚══════════════════════════════════════════════════════════╝

🏥 SERVICE HEALTH: {health['overall_status'].upper()}
  • Database: {health['services'].get('database', 'unknown')}
  • OpenAI API: {health['services'].get('openai_api', 'unknown')}
  • Error Rate: {health['services'].get('error_rate', 'unknown')}
  • Response Time: {health['services'].get('response_time', 'unknown')}

💰 COST ANALYSIS (Last 7 Days)
  • Total Cost: ${cost_report['summary']['total_cost_usd']:.2f}
  • Total Calls: {cost_report['summary']['total_calls']}
  • Total Tokens: {cost_report['summary']['total_tokens']:,}
  • Avg Cost/Call: ${cost_report['summary']['avg_cost_per_call']:.6f}

❌ ERROR REPORT (Last 7 Days)
  • Total Errors: {error_report['total_errors']}
  • Error Rate: {error_report['error_rate_percent']:.2f}%

📊 TOP FEATURES BY COST:
"""
    
    for feature, metrics in cost_report['by_feature'].items():
        if metrics['cost'] > 0:
            summary += f"  • {feature}: ${metrics['cost']:.2f} ({metrics['calls']} calls)\n"
    
    return summary
