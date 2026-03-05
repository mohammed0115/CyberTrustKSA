# CyberTrustKSA

## Quick Start

1. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

2. Apply migrations:

```bash
python manage.py migrate
```

3. (Optional) Parse NCA PDF and regenerate seed files:

```bash
python cybertrust/apps/controls/tools/parse_nca_pdf.py --pdf "Docs/114 NCA.pdf"
```

4. Import NCA controls (idempotent):

```bash
python manage.py import_nca_controls --source json
```

5. Run the server:

```bash
python manage.py runserver
```

## Sprint 3/4: Evidence Upload + AI Analysis (Async)

- Upload evidence: `/org/<slug>/evidence/upload/`
- Supported types: PDF, DOCX, PNG, JPG (max 25MB)
- After upload, open the evidence detail page and click **Analyze** to run AI.
- Ensure `OPENAI_API_KEY` is set in `.env`.

## Celery + Redis

1. Start Redis:

```bash
# Docker
docker run -p 6379:6379 redis:7
```

2. Run Celery worker:

```bash
celery -A cybertrust.config.celery worker -l info
```

## Reports

- Reports list: `/org/<slug>/reports/`
- Generate a report (ADMIN/SECURITY_OFFICER only), then download the PDF from the list.

## Tests

```bash
python manage.py test
```
"# CyberTrustKSA" 
