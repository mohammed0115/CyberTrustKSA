# Deployment & OpenAI Monitoring Guide

This guide covers production deployment, OpenAI API monitoring, cost tracking, rate limiting, and health checks for the CyberTrust KSA platform.

## Pre-Deployment Checklist

### Environment Setup

- [ ] Database migration tested on staging
- [ ] All tests passing (run `pytest`)
- [ ] Environment variables configured
- [ ] Static files collected
- [ ] Secrets stored securely (not in git)
- [ ] ALLOWED_HOSTS configured
- [ ] CSRF settings configured
- [ ] CORS settings configured

### Code Quality

- [ ] Code coverage >80% (run `pytest --cov`)
- [ ] No security vulnerabilities (run `pip audit`)
- [ ] No deprecated packages (run `pip check`)
- [ ] Linting passed (run `flake8` or `pylint`)
- [ ] Type checking passed (run `mypy`)

### Performance

- [ ] Database queries optimized (test N+1 issues)
- [ ] Caching configured (Redis)
- [ ] Static files minified
- [ ] Images optimized
- [ ] CDN configured

### Documentation

- [ ] README.md updated
- [ ] API documentation generated
- [ ] Deployment runbook created
- [ ] Emergency procedures documented
- [ ] On-call rotation scheduled

## Production Settings Configuration

### Django Settings (cybertrust/config/settings/prod.py)

```python
# Base settings import
from cybertrust.config.settings.base import *

# ===== SECURITY SETTINGS =====

# SSL/HTTPS
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Security headers
SECURE_CONTENT_SECURITY_POLICY = {
    "default-src": ["'self'"],
    "script-src": ["'self'", "'unsafe-inline'"],
    "style-src": ["'self'", "'unsafe-inline'"],
}

# ===== SECRET KEY =====
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is required")

# ===== ALLOWED HOSTS =====
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')

# ===== DEBUG MODE =====
DEBUG = False

# ===== DATABASE =====
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST'),
        'PORT': os.environ.get('DB_PORT', '3306'),
        'CONN_MAX_AGE': 600,  # Connection pooling
        'OPTIONS': {
            'charset': 'utf8mb4',
            'use_unicode': True,
        }
    }
}

# ===== CACHING =====
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
        }
    }
}

# SESSION cache
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

# ===== OPENAI SETTINGS =====
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')
OPENAI_API_TIMEOUT = int(os.environ.get('OPENAI_API_TIMEOUT', '30'))

# ===== LOGGING =====
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
        'file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/cybertrust/django.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'ai_engine': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/cybertrust/ai_engine.log',
            'maxBytes': 1024 * 1024 * 50,  # 50MB
            'backupCount': 20,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
        },
        'ai_engine': {
            'handlers': ['ai_engine', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# ===== SENTRY ERROR TRACKING =====
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

sentry_sdk.init(
    dsn=os.environ.get('SENTRY_DSN'),
    integrations=[DjangoIntegration()],
    traces_sample_rate=0.1,
    send_default_pii=True,
)

# ===== EMAIL CONFIGURATION =====
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@cybertrust.sa')

# ===== MEDIA FILES =====
MEDIA_URL = os.environ.get('MEDIA_URL', '/media/')
MEDIA_ROOT = os.environ.get('MEDIA_ROOT', '/var/media/cybertrust/')

# ===== STATIC FILES =====
STATIC_URL = os.environ.get('STATIC_URL', '/static/')
STATIC_ROOT = os.environ.get('STATIC_ROOT', '/var/static/cybertrust/')
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

# ===== CORS SETTINGS =====
CORS_ALLOWED_ORIGINS = os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',')
CORS_ALLOW_CREDENTIALS = True

# ===== RATE LIMITING =====
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

class UserThrottle(UserRateThrottle):
    scope = 'user'
    THROTTLE_RATES = {
        'user': '1000/hour'
    }

class AnonThrottle(AnonRateThrottle):
    scope = 'anon'
    THROTTLE_RATES = {
        'anon': '100/hour'
    }

REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'cybertrust.config.settings.prod.UserThrottle',
        'cybertrust.config.settings.prod.AnonThrottle',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
}
```

## OpenAI API Monitoring Integration

### 1. Track API Calls in Views

```python
# In your view functions
from cybertrust.apps.ai_engine.monitoring import track_api_call
import time

@handle_api_errors
def chatbot_message(request):
    """Send message to Virtual CISO."""
    start_time = time.time()
    
    try:
        user_message = request.data.get("message")
        language = request.data.get("language", "en")
        
        # Make API call
        result = asyncio.run(
            chat_with_ciso(
                user_message=user_message,
                organization=request.user.get_primary_organization(),
                user=request.user,
                language=language
            )
        )
        
        # Calculate tokens (rough estimate)
        tokens_prompt = len(user_message.split()) * 1.3
        
        # Track successful call
        track_api_call(
            feature="chatbot",
            organization=request.user.get_primary_organization(),
            user=request.user,
            tokens_prompt=int(tokens_prompt),
            tokens_completion=len(result["response"].split()) * 1.3,
            cost_usd=0.00005,  # Estimate for gpt-4o-mini
            status="success",
            duration_ms=int((time.time() - start_time) * 1000)
        )
        
        return Response(result)
    
    except Exception as e:
        # Track failed call
        track_api_call(
            feature="chatbot",
            organization=request.user.get_primary_organization(),
            user=request.user,
            status="failure",
            error_message=str(e),
            duration_ms=int((time.time() - start_time) * 1000)
        )
        raise
```

### 2. Rate Limiting Implementation

```python
# In views.py
from cybertrust.apps.ai_engine.monitoring import RateLimiter

rate_limiter = RateLimiter(
    feature="chatbot",
    calls_per_minute=60  # Tune based on OpenAI plan
)

@handle_api_errors
def chatbot_message(request):
    """Send message to Virtual CISO with rate limiting."""
    user_key = f"user_{request.user.id}"
    
    if not rate_limiter.is_allowed(user_key):
        remaining = rate_limiter.get_remaining(user_key)
        return Response(
            {
                "error": "Rate limit exceeded",
                "remaining_calls": remaining,
                "reset_in_seconds": 60
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS
        )
    
    # ... continue with API call
```

### 3. Health Check Endpoint

```python
# In urls.py
path('api/health/', views.health_check, name='health_check'),

# In views.py
from cybertrust.apps.ai_engine.monitoring import check_service_health
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Check service health."""
    health = check_service_health()
    
    status_code = 200 if health['overall_status'] == 'healthy' else 503
    return Response(health, status=status_code)
```

### 4. Cost Monitoring Dashboard

```python
# In views.py
from cybertrust.apps.ai_engine.monitoring import (
    get_openai_cost_report,
    get_error_report,
    check_cost_threshold,
    check_error_rate_threshold
)

@login_required
def monitoring_dashboard(request):
    """Display OpenAI monitoring dashboard."""
    if not request.user.is_superuser:
        raise PermissionDenied
    
    context = {
        'cost_7days': get_openai_cost_report(days=7),
        'cost_30days': get_openai_cost_report(days=30),
        'error_report': get_error_report(days=7),
        'over_cost_threshold': check_cost_threshold(threshold_usd=500),
        'high_error_rate': check_error_rate_threshold(threshold_percent=5),
    }
    
    return render(request, 'admin/monitoring.html', context)
```

## Deployment Process

### 1. Pre-Deployment

```bash
# Run all tests
pytest --cov

# Check for security issues
pip audit

# Run migrations locally
python manage.py migrate --dry-run

# Collect static files (test)
python manage.py collectstatic --dry-run

# Build Docker image
docker build -t cybertrust:latest .
```

### 2. Staging Deployment

```bash
# Push to staging environment
git push staging main

# SSH into staging server
ssh deploy@staging.cybertrust.sa

# Pull code
cd /var/www/cybertrust
git pull

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Run tests
pytest

# Restart services
sudo systemctl restart cybertrust-web
sudo systemctl restart cybertrust-worker
```

### 3. Production Deployment

```bash
# Create backup
sudo systemctl stop cybertrust-web
sudo pg_dump cybertrust > /backups/cybertrust_$(date +%Y%m%d_%H%M%S).sql
sudo systemctl start cybertrust-web

# Blue-Green deployment
# Run new version on separate port
DJANGO_SETTINGS_MODULE=cybertrust.config.settings.prod \
python manage.py runserver 8001

# Switch load balancer if tests pass
sudo systemctl reload nginx

# Monitor logs
tail -f /var/log/cybertrust/django.log
```

### 4. Post-Deployment

```bash
# Verify deployment
curl https://api.cybertrust.sa/api/health/

# Monitor error rates
python manage.py monitoring_report

# Check OpenAI costs
python manage.py openai_cost_report --days=1

# Ensure tasks are running
celery inspect active

# Database integrity check
python manage.py dbshell "CHECK TABLE users;"
```

## Monitoring & Alerting

### 1. Metrics to Monitor

- **API Response Time**: <1 second for 95th percentile
- **Error Rate**: <1% of all requests
- **Database Latency**: <100ms for 95th percentile
- **Cache Hit Rate**: >80%
- **OpenAI Cost**: <$500/day (adjust based on usage)
- **Rate Limit Hits**: <5% of requests
- **Sentry Error Count**: <50 errors/day

### 2. Alert Thresholds

```python
# Configure in settings
MONITORING_ALERTS = {
    'response_time_p95_ms': 1000,
    'error_rate_percent': 1.0,
    'database_latency_p95_ms': 100,
    'openai_daily_cost_usd': 500,
    'rate_limit_percent': 5.0,
}
```

### 3. Alert Channels

```python
# Send alerts via email
from django.core.mail import send_mail

def alert_high_cost(daily_cost):
    send_mail(
        subject='[ALERT] High OpenAI Cost',
        message=f'Daily cost: ${daily_cost:.2f}',
        from_email='alerts@cybertrust.sa',
        recipient_list=['devops@cybertrust.sa'],
    )

# Send to Slack
import requests

def alert_to_slack(message):
    requests.post(
        os.environ.get('SLACK_WEBHOOK_URL'),
        json={'text': message}
    )
```

### 4. Management Commands

```bash
# Run monitoring checks
python manage.py monitoring_check

# Generate cost report
python manage.py openai_cost_report --days=30 --export=csv

# Generate error report
python manage.py error_report --days=7

# Export metrics for dashboard
python manage.py export_metrics --format=prometheus
```

## Docker Deployment

### Dockerfile Example

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Create non-root user
RUN useradd -m appuser
USER appuser

EXPOSE 8000

CMD ["gunicorn", "cybertrust.config.wsgi:application", "--bind", "0.0.0.0:8000"]
```

### Docker Compose Production Example

```yaml
version: '3.8'

services:
  web:
    image: cybertrust:latest
    ports:
      - "8000:8000"
    environment:
      DJANGO_SETTINGS_MODULE: cybertrust.config.settings.prod
      DATABASE_URL: mysql://user:pass@db:3306/cybertrust
      REDIS_URL: redis://redis:6379/1
      OPENAI_API_KEY: ${OPENAI_API_KEY}
    depends_on:
      - db
      - redis
      - celery
    healthcheck:
      test: curl --fail http://localhost:8000/api/health/ || exit 1
      interval: 30s
      timeout: 10s
      retries: 3

  celery:
    image: cybertrust:latest
    command: celery -A cybertrust.config worker -l info
    environment:
      DJANGO_SETTINGS_MODULE: cybertrust.config.settings.prod
      REDIS_URL: redis://redis:6379/1
    depends_on:
      - db
      - redis

  db:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: ${DB_ROOT_PASSWORD}
      MYSQL_DATABASE: cybertrust
      MYSQL_USER: ${DB_USER}
      MYSQL_PASSWORD: ${DB_PASSWORD}
    volumes:
      - db_data:/var/lib/mysql

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  db_data:
  redis_data:
```

## Rollback Procedure

```bash
# Identify issue in logs
tail -f /var/log/cybertrust/django.log

# Check recent deployments
git log --oneline | head -5

# Rollback to previous version
git revert HEAD
git push production

# SSH and restart
ssh deploy@prod.cybertrust.sa
cd /var/www/cybertrust
git pull
python manage.py migrate --no-input
sudo systemctl restart cybertrust-web

# Verify rollback
curl https://api.cybertrust.sa/api/health/
```

## Performance Tuning

### Database Optimization

```sql
-- Add indexes for common queries
CREATE INDEX idx_org_created ON organizations_organization(created_at);
CREATE INDEX idx_api_call_feature ON ai_engine_apicalllog(feature, created_at);
CREATE INDEX idx_api_call_org ON ai_engine_apicalllog(organization_id, created_at);

-- Analyze query performance
EXPLAIN SELECT * FROM ai_engine_apicalllog WHERE created_at > NOW() - INTERVAL 7 DAY;
```

### Caching Strategy

```python
# Cache assessment results
from django.views.decorators.cache import cache_page

@cache_page(3600)  # Cache for 1 hour
def get_assessment_results(request, assessment_id):
    ...

# Cache OpenAI responses
from django.core.cache import cache

def chat_with_ciso_cached(user_message, language):
    cache_key = f"ciso_response:{user_message[:50]}:{language}"
    
    result = cache.get(cache_key)
    if result is None:
        result = expensive_api_call()
        cache.set(cache_key, result, 3600)  # Cache for 1 hour
    
    return result
```

### Query Optimization

```python
# Use select_related and prefetch_related
from django.db.models import Prefetch

assessments = VendorAssessment.objects.select_related(
    'organization'
).prefetch_related(
    Prefetch('questions')
).filter(
    status='completed'
)

# Use only() to limit fields
logs = APICallLog.objects.only(
    'feature', 'cost_usd', 'created_at'
).filter(
    created_at__gte=cutoff_date
)
```

## Conclusion

This deployment and monitoring guide provides a complete framework for:
- Running production workloads safely
- Tracking OpenAI API costs in detail
- Implementing rate limiting
- Monitoring service health
- Responding to incidents

For questions or issues, contact the DevOps team at devops@cybertrust.sa
