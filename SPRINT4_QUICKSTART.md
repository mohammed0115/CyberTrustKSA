# Sprint 4 Quick Start Guide

This guide will get you up and running with Sprint 4 (Async AI Analysis & Compliance Scoring Engine) in 15 minutes.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Quick Setup (5 minutes)](#quick-setup-5-minutes)
3. [Test the System (5 minutes)](#test-the-system-5-minutes)
4. [Common Commands](#common-commands)
5. [Troubleshooting](#troubleshooting)

---

## Prerequisites

**Required:**
- Python 3.8+
- Django 5.1
- Redis (for Celery broker)
- OpenAI API Key

**Check what's installed:**
```bash
python --version
redis-cli --version
```

---

## Quick Setup (5 minutes)

### Step 1: Install Dependencies (1 min)

```bash
cd /home/mohamed/Desktop/CyberTrustKSA

# Install Python packages
pip install celery redis openai django-celery-beat requests

# Or use requirements.txt if updated:
# pip install -r requirements.txt
```

### Step 2: Start Redis (1 min)

**Option A: Docker** (Easiest)
```bash
docker run -d -p 6379:6379 --name cybertrust-redis redis:7-alpine
```

**Option B: Systemd** (Linux)
```bash
sudo systemctl start redis-server
redis-cli ping  # Should return: PONG
```

**Option C: Manual**
```bash
redis-server
# In another terminal, test:
redis-cli ping  # Should return: PONG
```

### Step 3: Configure Environment (1 min)

Edit `.env` file (create if doesn't exist):
```bash
cat > .env << 'EOF'
DEBUG=True
SECRET_KEY=your-secret-key-here
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
OPENAI_API_KEY=sk-your-api-key-here
MAX_UPLOAD_SIZE=26214400
AI_TEXT_MAX_CHARS=50000
EOF
```

### Step 4: Database & Migrations (1 min)

```bash
python manage.py makemigrations
python manage.py migrate
```

### Step 5: Create Test User (1 min)

```bash
python manage.py createsuperuser
# Follow prompts to create admin user
```

---

## Test the System (5 minutes)

### Terminal 1: Django Server
```bash
python manage.py runserver 0.0.0.0:8000
```
Django running at: http://localhost:8000

### Terminal 2: Celery Worker
```bash
celery -A cybertrust worker -l info
```
You should see: `Ready to accept tasks`

### Terminal 3: Test It Out

```bash
# Get your auth token
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "your_password"
  }'

# Save token: export TOKEN="your-token-here"

# 1. Upload evidence
curl -X POST http://localhost:8000/api/v1/organizations/test-org/evidence/upload/ \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@sample.pdf"

# Example response:
# {
#   "id": 1,
#   "original_filename": "sample.pdf",
#   "status": "UPLOADED",
#   "message": "Evidence uploaded successfully"
# }

# 2. Link control to evidence
curl -X POST http://localhost:8000/api/v1/organizations/test-org/evidence/1/link/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "control_id": 1
  }'

# 3. Trigger analysis
curl -X POST http://localhost:8000/api/v1/organizations/test-org/evidence/1/analyze/ \
  -H "Authorization: Bearer $TOKEN"

# Example response:
# {
#   "message": "Analysis queued successfully",
#   "task_ids": ["abc-123"],
#   "controls_count": 1
# }

# 4. Monitor progress (poll this endpoint)
curl http://localhost:8000/api/v1/organizations/test-org/evidence/1/status/ \
  -H "Authorization: Bearer $TOKEN"

# Example response:
# {
#   "id": 1,
#   "status": "ANALYZING",
#   "progress": 75,
#   "message": "AI analysis in progress...",
#   "extracted_text_length": 5420
# }

# 5. Get dashboard
curl http://localhost:8000/api/v1/organizations/test-org/dashboard/ \
  -H "Authorization: Bearer $TOKEN"

# Example response:
# {
#   "overall_score": 72,
#   "risk_level": "MEDIUM",
#   "controls_completed": 42,
#   "total_controls": 114
# }
```

### Optional: Flower (Task Monitoring)

```bash
# In Terminal 3 (or new terminal)
pip install flower
flower -A cybertrust --port=5555

# Visit: http://localhost:5555
```

---

## Common Commands

### View Active Celery Tasks
```bash
celery -A cybertrust inspect active
```

### Purge All Tasks (⚠️ only in dev)
```bash
celery -A cybertrust purge  # Type: y to confirm
```

### Run Tests
```bash
# All tests
python manage.py test

# Specific test file
python manage.py test cybertrust.apps.evidence.tests_sprint4

# With coverage report
pip install coverage
coverage run --source='.' manage.py test
coverage report
```

### Create Test Organization

```bash
python manage.py shell

>>> from cybertrust.apps.organizations.models import Organization
>>> org = Organization.objects.create(
...     name='Test Organization',
...     slug='test-org',
...     country='SA'
... )
>>> exit()
```

### Create Test Controls

```bash
python manage.py loaddata cybertrust/apps/controls/data/controls.json
```

### Check Celery Configuration
```bash
python manage.py shell

>>> from django.conf import settings
>>> print(settings.CELERY_BROKER_URL)
>>> print(settings.CELERY_RESULT_BACKEND)
```

---

## Project Structure

```
cybertrust/
├── apps/
│   ├── evidence/
│   │   ├── views.py          # Upload, status, linking APIs
│   │   ├── urls.py           # API routes
│   │   ├── models.py         # Evidence + status pipeline
│   │   └── tests_sprint4.py  # Comprehensive tests
│   │
│   ├── ai_engine/
│   │   ├── tasks.py          # Celery tasks (enhanced)
│   │   ├── services/
│   │   │   ├── analyze_control.py    # Main analysis orchestration
│   │   │   ├── openai_client.py      # OpenAI integration
│   │   │   └── extractors.py         # PDF, DOCX, image extraction
│   │   └── models.py         # AIAnalysisResult
│   │
│   ├── controls/
│   │   ├── views.py          # Dashboard + control details APIs
│   │   ├── urls.py           # Dashboard routes
│   │   ├── models.py         # Control + ControlScoreSnapshot
│   │   └── services/
│   │       └── scoring.py    # Compliance scoring engine
│   │
│   └── organizations/
│       └── models.py         # Organization + UserOrganization
│
├── config/
│   ├── celery.py             # Celery app setup
│   └── settings/
│       └── base.py           # Django settings (Celery, Redis, OpenAI)
│
└── Dockerfile, docker-compose.yml
```

---

## API Endpoints Summary

### Evidence Endpoints
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/v1/organizations/{slug}/evidence/upload/` | Upload file |
| GET | `/api/v1/organizations/{slug}/evidence/` | List evidence |
| GET | `/api/v1/organizations/{slug}/evidence/{id}/` | Get details |
| GET | `/api/v1/organizations/{slug}/evidence/{id}/status/` | Check progress |
| POST | `/api/v1/organizations/{slug}/evidence/{id}/link/` | Link control |
| POST | `/api/v1/organizations/{slug}/evidence/{id}/analyze/` | Start analysis |

### Dashboard Endpoints
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/organizations/{slug}/dashboard/` | Get KPIs |
| GET | `/api/v1/organizations/{slug}/controls/` | List controls |
| GET | `/api/v1/organizations/{slug}/controls/{id}/details/` | Control + results |

---

## Status Pipeline Visualization

```
User Upload
    ↓
[UPLOADED] ────→ (Manual trigger or auto-queue)
    ↓
[EXTRACTING] ────→ (Extract text from file)
    ↓
[EXTRACTED] ────→ (Text extraction done)
    ↓
[ANALYZING] ────→ (AI analysis in progress)
    ↓
[ANALYZED] ✓ ────→ (Analysis complete, results stored)
    
⚠️ Errors:
[*] ────→ [FAILED] (error_message populated)
```

---

## Performance Tips

### 1. Increase Celery Concurrency
```bash
# Process 10 tasks in parallel
celery -A cybertrust worker -l info -c 10
```

### 2. Enable Caching
Add to your views:
```python
from django.views.decorators.cache import cache_page

@cache_page(5 * 60)  # Cache for 5 minutes
def get_dashboard(request):
    ...
```

### 3. Database Indexes
Make sure these are indexed:
```python
# In your model
class Evidence(models.Model):
    status = models.CharField(db_index=True)  # Add db_index=True
    created_at = models.DateTimeField(db_index=True)
```

### 4. Batch Processing
```bash
# Extract all pending evidence
curl -X POST http://localhost:8000/api/v1/organizations/{slug}/evidence/extract-all/ \
  -H "Authorization: Bearer $TOKEN"
```

---

## Authentication

The API uses Token-based authentication. Include in all requests:

```bash
-H "Authorization: Bearer YOUR_TOKEN"
```

Get token:
```bash
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin_username",
    "password": "admin_password"
  }'
```

---

## Troubleshooting

### ❌ "Redis connection refused"
```bash
# Start Redis
redis-server
# or with Docker:
docker run -d -p 6379:6379 redis:7-alpine
```

### ❌ "Celery worker not processing tasks"
```bash
# 1. Check worker is running
celery -A cybertrust inspect active

# 2. Check broker URL
python manage.py shell
>>> from django.conf import settings
>>> settings.CELERY_BROKER_URL

# 3. Check for errors in worker terminal
```

### ❌ "OpenAI API Error"
```bash
# Verify API key is set
python -c "from django.conf import settings; print(settings.OPENAI_API_KEY)"

# Check API key is valid: https://platform.openai.com/api-keys
```

### ❌ "File upload fails"
```bash
# Check content type
file sample.pdf  # Should show: PDF document

# Check file size (max 25MB)
ls -lh sample.pdf
```

### ❌ "Tests failing"
```bash
# Make sure test database is fresh
python manage.py test --no-migrations

# Run specific failing test with verbose output
python manage.py test cybertrust.apps.evidence.tests_sprint4.EvidenceUploadTestCase -v 2
```

---

## Next Steps

1. **Customize Scoring Weights**
   - Edit `RISK_WEIGHTS` in `cybertrust/apps/controls/services/scoring.py`

2. **Integrate with SIEM**
   - Add webhooks to send alerts to your security tools

3. **Add Custom Extractions**
   - Extend extractors in `cybertrust/apps/ai_engine/services/extractors.py`

4. **Implement Remediation**
   - Add recommendation actions based on analysis results

5. **Add Mobile App**
   - Build Flutter/React Native app consuming these APIs

---

## Support Resources

- **API Documentation:** See [SPRINT4_GUIDE.md](./SPRINT4_GUIDE.md)
- **Example cURL requests:** See section "Test the System" above
- **Code examples:** Check tests in `cybertrust/apps/evidence/tests_sprint4.py`
- **Issues:** Review logs in `logs/` directory

---

## Summary

You now have:
✅ Async AI analysis with Celery + Redis
✅ Real-time progress tracking  
✅ Compliance scoring engine with weighted calculations
✅ RESTful API for integration
✅ Comprehensive test suite
✅ Dashboard with KPIs

**Start building! 🚀**
