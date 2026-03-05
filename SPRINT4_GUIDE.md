# Sprint 4 Implementation Guide - Async AI Analysis & Compliance Scoring

This document outlines the complete implementation of Sprint 4 for CyberTrust KSA, including async AI analysis using Celery, compliance scoring engine, progress tracking, and enhanced dashboards.

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Setup Instructions](#setup-instructions)
3. [API Reference](#api-reference)
4. [Frontend Guide](#frontend-guide)
5. [Testing](#testing)
6. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

### Components
```
┌─────────────────────────────────────────────────────────┐
│           Django Web Application                        │
├─────────────────────────────────────────────────────────┤
│  API Endpoints ─────→ Views ─────→ Tasks/Services       │
│       ↓                               ↓                  │
│   Evidence Upload              Evidence Analysis        │
│   Progress Check               (Async via Celery)       │
│   Dashboard Fetch                   ↓                    │
│                         ┌─────────────────────┐          │
│                         │  Celery Worker      │          │
│                         │  + Redis Message    │          │
│                         │    Queue            │          │
│                         └─────────────────────┘          │
│                                ↓                         │
│                      OpenAI API (GPT-4o-mini)           │
│                         ↓                                │
│                  ControlScoreSnapshot                    │
│                  AIAnalysisResult                        │
│                         ↓                                │
│                   Dashboard Display                      │
└─────────────────────────────────────────────────────────┘
```

### Status Pipeline
```
UPLOADED
   ↓
EXTRACTING
   ↓
EXTRACTED
   ↓
ANALYZING
   ↓
ANALYZED ✓
   ↓
(on error) → FAILED
```

### Scoring Algorithm
```
COMPLIANT:     100 points (all requirements met)
PARTIAL:        60 points (most met, some gaps)
NON_COMPLIANT:   0 points (requirements not met)
UNKNOWN:        20 points (cannot determine)

Risk Level Calculation:
- Score ≥ 80: LOW risk
- Score ≥ 50: MEDIUM risk
- Score < 50: HIGH risk
```

---

## Setup Instructions

### 1. Prerequisites

ensure these packages are installed:
```bash
pip install celery redis openai django-celery-beat
```

### 2. Redis Setup

**Option A: Docker (Recommended)**
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

**Option B: Local Installation**
```bash
# Ubuntu/Debian
sudo apt-get install redis-server
redis-server

# macOS
brew install redis
redis-server
```

**Option C: From WSL/Linux**
```bash
# Install and start
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Check status
redis-cli ping  # Should return "PONG"
```

### 3. Environment Variables

Add to your `.env` file:
```bash
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
OPENAI_API_KEY=sk-your-api-key-here
MAX_UPLOAD_SIZE=26214400  # 25MB in bytes
AI_TEXT_MAX_CHARS=50000
```

### 4. Database Setup

```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Create Logs Directory

```bash
mkdir -p logs
```

---

## Running the System

### Terminal 1: Django Development Server
```bash
python manage.py runserver 0.0.0.0:8000
```

### Terminal 2: Celery Worker
```bash
celery -A cybertrust worker -l info
```

### Terminal 3 (Optional): Celery Flower (Task Monitoring)
```bash
pip install flower
celery -A cybertrust worker -l info --broker=redis://localhost:6379/0
flower -A cybertrust --port=5555
```
Access at: http://localhost:5555

---

## API Reference

### 1. Upload Evidence

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/organizations/test-org/evidence/upload/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@/path/to/document.pdf"
```

**Response:**
```json
{
  "id": 42,
  "organization": "test-org",
  "filename": "document.pdf",
  "status": "UPLOADED",
  "created_at": "2026-03-05T10:30:00Z"
}
```

### 2. Link Control to Evidence

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/organizations/test-org/evidence/42/link/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "control_id": 1
  }'
```

### 3. Start Analysis

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/organizations/test-org/evidence/42/analyze/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response:**
```json
{
  "task_id": "abc123...",
  "message": "Analysis queued successfully"
}
```

### 4. Check Progress (Polling)

**Request:**
```bash
curl http://localhost:8000/api/v1/organizations/test-org/evidence/42/status/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response:**
```json
{
  "id": 42,
  "status": "ANALYZING",
  "progress": 50,
  "message": "AI analysis in progress...",
  "extracted_text_length": 5420,
  "error_message": null
}
```

### 5. Get Dashboard

**Request:**
```bash
curl http://localhost:8000/api/v1/organizations/test-org/dashboard/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response:**
```json
{
  "overall_score": 72,
  "risk_level": "MEDIUM",
  "controls_completed": 42,
  "total_controls": 114,
  "evidence_pending": 3,
  "category_scores": [
    {
      "category": "Access Control",
      "score": 85,
      "status": "PARTIAL"
    }
  ],
  "top_missing_controls": [
    {
      "control_code": "AC-001",
      "control_title": "User Access Management",
      "score": 20,
      "status": "NON_COMPLIANT"
    }
  ]
}
```

### 6. Get Control Details + AI Results

**Request:**
```bash
curl http://localhost:8000/api/v1/organizations/test-org/controls/AC-001/details/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response:**
```json
{
  "control": {
    "code": "AC-001",
    "title": "User Access Management",
    "category": "Access Control",
    "risk_level": "HIGH"
  },
  "score": {
    "score": 20,
    "status": "NON_COMPLIANT",
    "computed_at": "2026-03-05T10:30:00Z"
  },
  "analysis_results": [
    {
      "id": 1,
      "evidence_id": 42,
      "status": "NON_COMPLIANT",
      "score": 0,
      "confidence": 95,
      "summary": "No evidence of user access management implementation.",
      "missing_points": [
        "No formal user access policies",
        "No role-based access control (RBAC)"
      ],
      "recommendations": [
        "Implement RBAC system",
        "Document and enforce access policies"
      ],
      "created_at": "2026-03-05T10:30:00Z"
    }
  ]
}
```

---

## Frontend Guide

### Evidence List with Progress

```html
<div class="evidence-list">
  {% for evidence in evidence_list %}
    <div class="evidence-item" data-evidence-id="{{ evidence.id }}">
      <h4>{{ evidence.original_filename }}</h4>
      
      <!-- Status Stepper -->
      <div class="stepper">
        <div class="step {% if evidence.status != 'UPLOADED' %}completed{% endif %}">
          📤 Upload
        </div>
        <div class="step {% if evidence.status not in 'UPLOADED,EXTRACTING' %}completed{% endif %}
                    {% if evidence.status == 'EXTRACTING' %}active{% endif %}">
          📄 Extract
        </div>
        <div class="step {% if evidence.status in 'ANALYZED' %}completed{% endif %}
                    {% if evidence.status == 'ANALYZING' %}active{% endif %}">
          🧠 Analyze
        </div>
        <div class="step {% if evidence.status == 'ANALYZED' %}completed{% endif %}">
          ✓ Done
        </div>
      </div>
      
      <!-- Progress Bar -->
      <div class="progress-bar" id="progress-{{ evidence.id }}">
        <div class="progress" style="width: {% if evidence.status == 'UPLOADED' %}0{% elif evidence.status == 'EXTRACTING' %}33{% elif evidence.status == 'ANALYZING' %}66{% else %}100{% endif %}%"></div>
      </div>
      
      <!-- Status Text -->
      <p class="status-text" id="status-{{ evidence.id }}">
        Status: {{ evidence.get_status_display }}
      </p>
      
      <!-- Error Message -->
      {% if evidence.error_message %}
        <div class="error-box">{{ evidence.error_message }}</div>
      {% endif %}
    </div>
  {% endfor %}
</div>
```

### JavaScript Polling (Alpine.js)

```html
<script>
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('[data-evidence-id]').forEach(el => {
    const evidenceId = el.dataset.evidenceId;
    const org_slug = '{{ org.slug }}';
    
    // Poll every 3 seconds
    setInterval(() => {
      fetch(`/api/v1/organizations/${org_slug}/evidence/${evidenceId}/status/`)
        .then(r => r.json())
        .then(data => {
          const progress = {
            'UPLOADED': 0,
            'EXTRACTING': 33,
            'EXTRACTED': 33,
            'ANALYZING': 66,
            'ANALYZED': 100,
            'FAILED': 100
          };
          
          document.querySelector(`#progress-${evidenceId} .progress`)
            .style.width = progress[data.status] + '%';
          document.querySelector(`#status-${evidenceId}`)
            .textContent = `Status: ${data.message}`;
        });
    }, 3000);
  });
});
</script>
```

### Dashboard Chart (Chart.js)

```html
<canvas id="complianceChart" width="300" height="100"></canvas>

<script>
const ctx = document.getElementById('complianceChart').getContext('2d');

fetch('/api/v1/organizations/{{ org.slug }}/dashboard/')
  .then(r => r.json())
  .then(data => {
    new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['Compliant', 'Partial', 'Non-Compliant'],
        datasets: [{
          data: [
            data.compliant_count,
            data.partial_count,
            data.non_compliant_count
          ],
          backgroundColor: ['#10b981', '#f59e0b', '#ef4444']
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: { position: 'bottom' }
        }
      }
    });
  });
</script>
```

---

## Testing

### Run Tests

```bash
# All tests
python manage.py test

# Specific test
python manage.py test cybertrust.apps.ai_engine.tests.TestAnalysisTask

# With coverage
pip install coverage
coverage run --source='.' manage.py test
coverage report
coverage html
```

### Manual Testing Checklist

- [ ] Upload PDF evidence file
- [ ] Check extraction extracts text correctly
- [ ] Trigger analysis task
- [ ] Monitor task progress in Flower
- [ ] Verify AIAnalysisResult created
- [ ] Check ControlScoreSnapshot computed
- [ ] Verify Evidence status updated to ANALYZED
- [ ] Check Dashboard reflects new score
- [ ] View Control Details with analysis
- [ ] Verify RBAC works (AUDITOR cannot link)

---

## Troubleshooting

### Issue: "Redis connection refused"

**Solution:**
```bash
# Check Redis running
redis-cli ping

# If not running, start:
redis-server
# or with Docker:
docker run -d -p 6379:6379 redis:7-alpine
```

### Issue: "Task always shows PENDING"

**Solution:**
```bash
# Check Celery worker is running
celery -A cybertrust worker -l info

# Check broker is configured correctly in settings:
print(settings.CELERY_BROKER_URL)  # Should be redis://...
```

### Issue: "OpenAI API key not found"

**Solution:**
```bash
# Check .env file has:
OPENAI_API_KEY=sk-your-key

# Reload settings:
python manage.py shell
>>> from django.conf import settings
>>> settings.OPENAI_API_KEY
```

### Issue: "File extraction failed - Tesseract not found"

**Solution:**
```bash
# Install Tesseract-OCR
# Ubuntu:
sudo apt install tesseract-ocr tesseract-ocr-all

# macOS:
brew install tesseract

# Verify:
tesseract --version
```

### Issue: "CORS error on API calls"

**Solution:**
Add to Django settings:
```python
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
```

---

## Performance Optimization

### Database Indexes
```python
# Make sure these are indexed:
- Evidence.status
- Evidence.organization_id
- Evidence.created_at
- ControlScoreSnapshot.organization_id
- ControlScoreSnapshot.control_id
- AIAnalysisResult.organization_id
```

### Caching
```python
# Cache dashboard for 5 minutes
from django.views.decorators.cache import cache_page

@cache_page(5 * 60)
def dashboard(request, org_slug):
    ...
```

### Celery Optimization
```python
# Process 10 tasks in parallel
celery -A cybertrust worker -l info -c 10

# Dedicated queue for analysis
celery -A cybertrust worker -Q analysis --concurrency=4
```

---

## Security Considerations

### File Upload Restrictions
- Max file size: 25MB (configurable via MAX_UPLOAD_SIZE)
- Allowed extensions: PDF, DOCX, PNG, JPG
- Files scanned for malware (optional: integrate VirusTotal API)

### RBAC Permissions
```python
# Analysis permissions
ADMIN: Can trigger analysis, view all results
SECURITY_OFFICER: Can trigger analysis, view results
AUDITOR: Can only view results
VIEWER: Read-only access

# Enforce with @permission_required decorator
```

### API Rate Limiting
```python
# Limit API calls per user
# 100 requests per hour for analysis endpoints
```

---

## Monitoring & Observability

### Celery Task Monitoring
```bash
# View worker stats
celery -A cybertrust inspect active

# View scheduled tasks
celery -A cybertrust inspect scheduled

# View registered tasks
celery -A cybertrust inspect registered
```

### Logs Location
- AI Analysis: `logs/ai_engine.log`
- Chatbot: `logs/chatbot.log`
- General: console output

### Key Metrics to Monitor
- Average analysis time per evidence
- Task failure rate
- OpenAI API call costs
- Evidence pending count
- Overall compliance trend

---

## Next Steps

After Sprint 4 is complete:

1. **Sprint 5:** Advanced Reporting (PDF export, trend analysis)
2. **Sprint 6:** Automated Remediation Recommendations
3. **Sprint 7:** Integration with external systems (SIEM, ticketing)
4. **Sprint 8:** Machine Learning models for risk prediction
5. **Sprint 9:** Mobile application
6. **Sprint 10:** Multi-tenancy and white-labeling

---

## Support

For questions or issues:
- Check logs: `logs/ai_engine.log`
- Review test cases in `cybertrust/apps/ai_engine/tests.py`
- Check GitHub issues and PRs
- Contact: dev@cybertrust.sa

---

**Last Updated:** March 2026  
**Version:** Sprint 4.0  
**Status:** Ready for Production
