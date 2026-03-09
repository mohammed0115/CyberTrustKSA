# CyberTrustKSA

CyberTrustKSA is a Django application with Celery, Redis, OCR support, and AI-assisted analysis workflows.

## Local Development

1. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

2. Apply migrations:

```bash
python manage.py migrate
```

3. Import NCA controls if needed:

```bash
python manage.py import_nca_controls --source json
```

4. Run the development server:

```bash
python manage.py runserver 0.0.0.0:8000
```

5. Run a Celery worker if you want async evidence analysis:

```bash
celery -A cybertrust worker -l info
```

## Ubuntu Deployment

This repository now includes an Ubuntu deployment script at `scripts/deploy_ubuntu.sh`.

Target deployment:

- Public IP: `76.13.143.149`
- Public URL: `http://76.13.143.149:8000`
- Public port: `8000`
- Internal gunicorn bind: `127.0.0.1:8001`

The deployment script configures Nginx on port `8000`, proxies requests to gunicorn, keeps Redis local for Celery, and prepares the Django app in the current repository directory.

### What the Script Configures

- Installs Ubuntu packages: `python3`, `python3-venv`, `python3-dev`, `build-essential`, `pkg-config`, `default-libmysqlclient-dev`, `redis-server`, `nginx`, `tesseract-ocr`
- Creates a Python virtual environment at `./.venv`
- Installs Python dependencies from `requirements.txt`
- Creates `logs/`, `media/`, and `staticfiles/`
- Creates `.env` if it does not already exist
- Runs `python manage.py migrate`
- Runs `python manage.py collectstatic --noinput`
- Runs `python manage.py check`
- Creates systemd services:
  - `cybertrust-gunicorn.service`
  - `cybertrust-celery.service`
- Creates Nginx site config:
  - `/etc/nginx/sites-available/cybertrustksa-8000`
  - `/etc/nginx/sites-enabled/cybertrustksa-8000`
- Enables and restarts `redis-server`, `nginx`, `cybertrust-gunicorn`, and `cybertrust-celery`
- Opens `8000/tcp` in UFW if UFW is installed

### Deploy on Ubuntu

1. Clone the repository on the Ubuntu server.

2. Change into the project directory.

```bash
cd /path/to/CyberTrustKSA
```

3. Run the deployment script.

```bash
chmod +x scripts/deploy_ubuntu.sh
./scripts/deploy_ubuntu.sh
```

If you prefer, you can run it explicitly with bash:

```bash
bash scripts/deploy_ubuntu.sh
```

4. Edit `.env` and add your real `OPENAI_API_KEY` if the script created a fresh environment file.

5. Restart the application services after changing `.env`.

```bash
sudo systemctl restart cybertrust-gunicorn cybertrust-celery
```

### Required `.env` Configuration

If `.env` does not exist, the script writes a working starter file. Review these values before using the server:

```env
DJANGO_SETTINGS_MODULE=cybertrust.config.settings.prod
SECRET_KEY=replace-with-a-long-random-secret
DEBUG=False
SERVER_IP=76.13.143.149
PUBLIC_HOST=76.13.143.149
PUBLIC_PORT=8000
ALLOWED_HOSTS=76.13.143.149,localhost,127.0.0.1
STATIC_ROOT=/path/to/CyberTrustKSA/staticfiles
MEDIA_ROOT=/path/to/CyberTrustKSA/media
DEFAULT_FROM_EMAIL=no-reply@76.13.143.149
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
MAX_UPLOAD_SIZE=26214400
TESSERACT_CMD=/usr/bin/tesseract
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0
LOG_LEVEL=INFO
GUNICORN_BIND=127.0.0.1:8001
GUNICORN_WORKERS=3
GUNICORN_THREADS=2
GUNICORN_TIMEOUT=120
GUNICORN_KEEPALIVE=5
```

Values you must verify:

- `OPENAI_API_KEY`: required for AI analysis features
- `SECRET_KEY`: generated automatically for a new `.env`, but keep it private
- `SERVER_IP`, `PUBLIC_HOST`, and `PUBLIC_PORT`: keep these aligned with the public address you actually open in the browser
- `ALLOWED_HOSTS`: keep `76.13.143.149` unless you move to a different host or add a domain
- `STATIC_ROOT` and `MEDIA_ROOT`: leave these pointing at the project unless you intentionally move storage

### Troubleshooting 400 Bad Request

If you open `http://76.13.143.149:8000/` and Django shows `Bad Request (400)`, the running process usually has the wrong host settings loaded.

Check `.env` and make sure these are present:

```env
SERVER_IP=76.13.143.149
PUBLIC_HOST=76.13.143.149
PUBLIC_PORT=8000
ALLOWED_HOSTS=76.13.143.149,localhost,127.0.0.1
```

Then restart gunicorn and nginx:

```bash
sudo systemctl restart cybertrust-gunicorn nginx
```

If it still fails, inspect the gunicorn log for `DisallowedHost`:

```bash
sudo journalctl -u cybertrust-gunicorn -n 100 --no-pager
```

### Service Management

Check service status:

```bash
sudo systemctl status cybertrust-gunicorn cybertrust-celery nginx redis-server
```

Restart services:

```bash
sudo systemctl restart cybertrust-gunicorn cybertrust-celery nginx redis-server
```

Enable services at boot:

```bash
sudo systemctl enable cybertrust-gunicorn cybertrust-celery nginx redis-server
```

View logs:

```bash
sudo journalctl -u cybertrust-gunicorn -n 100 --no-pager
sudo journalctl -u cybertrust-celery -n 100 --no-pager
sudo journalctl -u nginx -n 100 --no-pager
tail -n 100 logs/ai_engine.log
tail -n 100 logs/chatbot.log
```

### First-Time Admin Setup

Create a Django admin user after deployment:

```bash
./.venv/bin/python manage.py createsuperuser
```

### Redeploy After Code Changes

After pulling updates on the Ubuntu server:

```bash
git pull
./.venv/bin/pip install -r requirements.txt
./.venv/bin/python manage.py migrate --noinput
./.venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart cybertrust-gunicorn cybertrust-celery nginx
```

### Important Runtime Notes

- The current shipped settings use SQLite by default, so this deployment keeps the application database in `db.sqlite3` in the project root.
- Redis is required for Celery and is configured to run locally on `127.0.0.1:6379`.
- OCR features require `tesseract-ocr`, and the deployment script sets `TESSERACT_CMD=/usr/bin/tesseract`.
- Nginx serves `/static/` and `/media/` directly and proxies all other traffic to gunicorn.

### Health Checks

Open these after deployment:

- `http://76.13.143.149:8000/`
- `http://76.13.143.149:8000/admin/`

Run a Django check manually if needed:

```bash
./.venv/bin/python manage.py check
```

## Tests

```bash
python manage.py test
```
