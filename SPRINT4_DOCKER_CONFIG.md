# Sprint 4 Docker Compose & Environment Configuration

## Quick Production Setup with Docker Compose

### docker-compose.prod.yml (Enhanced for Sprint 4)

```yaml
version: '3.9'

services:
  # PostgreSQL Database
  db:
    image: postgres:15-alpine
    container_name: cybertrust_db
    environment:
      POSTGRES_DB: cybertrust
      POSTGRES_USER: cybertrust
      POSTGRES_PASSWORD: secure_password_change_me
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - cybertrust_network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U cybertrust"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Redis Broker & Results Backend
  redis:
    image: redis:7-alpine
    container_name: cybertrust_redis
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    networks:
      - cybertrust_network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Django Application
  web:
    build: .
    container_name: cybertrust_web
    command: sh -c "python manage.py migrate && gunicorn cybertrust.wsgi --bind 0.0.0.0:8000 --workers 4"
    ports:
      - "8000:8000"
    environment:
      DEBUG: "False"
      SECRET_KEY: ${SECRET_KEY}
      DATABASE_URL: postgresql://cybertrust:secure_password_change_me@db:5432/cybertrust
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/0
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      ALLOWED_HOSTS: localhost,127.0.0.1,yourdomain.com
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./:/app
      - static_volume:/app/static
      - media_volume:/app/media
      - logs_volume:/app/logs
    networks:
      - cybertrust_network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  # Celery Worker (Event Handler)
  celery_worker:
    build: .
    container_name: cybertrust_celery
    command: celery -A cybertrust worker -l info --concurrency=4
    environment:
      DEBUG: "False"
      SECRET_KEY: ${SECRET_KEY}
      DATABASE_URL: postgresql://cybertrust:secure_password_change_me@db:5432/cybertrust
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/0
      OPENAI_API_KEY: ${OPENAI_API_KEY}
    depends_on:
      - db
      - redis
      - web
    volumes:
      - ./:/app
      - logs_volume:/app/logs
    networks:
      - cybertrust_network

  # Celery Beat (Scheduled Tasks)
  celery_beat:
    build: .
    container_name: cybertrust_beat
    command: celery -A cybertrust beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    environment:
      DEBUG: "False"
      SECRET_KEY: ${SECRET_KEY}
      DATABASE_URL: postgresql://cybertrust:secure_password_change_me@db:5432/cybertrust
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/0
      OPENAI_API_KEY: ${OPENAI_API_KEY}
    depends_on:
      - db
      - redis
    volumes:
      - ./:/app
    networks:
      - cybertrust_network

  # Flower (Celery Task Monitoring)
  flower:
    build: .
    container_name: cybertrust_flower
    command: celery -A cybertrust flower --port=5555 --broker=redis://redis:6379/0
    ports:
      - "5555:5555"
    environment:
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/0
    depends_on:
      - redis
    networks:
      - cybertrust_network

  # Nginx Reverse Proxy
  nginx:
    image: nginx:alpine
    container_name: cybertrust_nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - static_volume:/app/static:ro
      - media_volume:/app/media:ro
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - web
    networks:
      - cybertrust_network

volumes:
  postgres_data:
  redis_data:
  static_volume:
  media_volume:
  logs_volume:

networks:
  cybertrust_network:
    driver: bridge
```

---

## Environment Variables (.env)

```bash
# Django Security
DEBUG=False
SECRET_KEY=your-very-secure-random-key-change-this-in-production
ALLOWED_HOSTS=localhost,127.0.0.1,yourdomain.com

# Database
DATABASE_URL=postgresql://cybertrust:secure_password_change_me@localhost:5432/cybertrust
# Or SQLite for dev:
# DATABASE_URL=sqlite:///db.sqlite3

# Celery & Redis
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_TASK_TRACK_STARTED=True
CELERY_TASK_TIME_LIMIT=600

# OpenAI
OPENAI_API_KEY=sk-your-actual-api-key-here
OPENAI_MODEL=gpt-4o-mini

# File Upload
MAX_UPLOAD_SIZE=26214400  # 25MB
EVIDENCE_ALLOWED_EXTENSIONS=pdf,docx,png,jpg,jpeg

# Email (for alerts)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# Logging
LOG_LEVEL=INFO

# CORS (if using separate frontend)
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000,https://yourdomain.com

# API Settings
REST_FRAMEWORK_DEFAULT_PAGINATION_PAGE_SIZE=50
REST_FRAMEWORK_DEFAULT_FILTER_BACKENDS=rest_framework.filters.SearchFilter,rest_framework.filters.OrderingFilter
```

---

## Dockerfile (Enhanced for Sprint 4)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    redis-tools \
    tesseract-ocr \
    tesseract-ocr-all \
    libreoffice \
    poppler-utils \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy application
COPY . .

# Create necessary directories
RUN mkdir -p logs static media

# Collect static files
RUN python manage.py collectstatic --noinput || true

# Create non-root user
RUN useradd -m -u 1000 cybertrust && \
    chown -R cybertrust:cybertrust /app

USER cybertrust

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

CMD ["gunicorn", "cybertrust.wsgi", "--bind", "0.0.0.0:8000", "--workers", "4"]
```

---

## Nginx Configuration (nginx.conf)

```nginx
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';

    access_log /var/log/nginx/access.log main;

    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 25M;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1000;
    gzip_types text/plain text/css text/xml text/javascript 
               application/x-javascript application/xml+rss 
               application/json application/javascript;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=upload_limit:10m rate=2r/s;

    upstream django {
        server web:8000;
    }

    upstream flower {
        server flower:5555;
    }

    # HTTP to HTTPS redirect
    server {
        listen 80;
        server_name _;
        
        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }
        
        location / {
            return 301 https://$host$request_uri;
        }
    }

    # HTTPS server
    server {
        listen 443 ssl http2;
        server_name yourdomain.com www.yourdomain.com;

        ssl_certificate /etc/nginx/certs/cert.pem;
        ssl_certificate_key /etc/nginx/certs/key.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;

        # Security headers
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "no-referrer-when-downgrade" always;

        # Static files
        location /static/ {
            alias /app/static/;
            expires 30d;
        }

        # Media files
        location /media/ {
            alias /app/media/;
            expires 7d;
        }

        # Flower (monitoring)
        location /flower/ {
            proxy_pass http://flower/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # Flower-specific settings
            proxy_http_version 1.1;
            proxy_set_header Connection "";
            proxy_buffering off;
        }

        # API endpoints with rate limiting
        location /api/v1/organizations/ {
            limit_req zone=api_limit burst=20 nodelay;
            
            proxy_pass http://django;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Evidence upload with stricter rate limiting
        location /api/v1/organizations/*/evidence/upload/ {
            limit_req zone=upload_limit burst=5 nodelay;
            
            proxy_pass http://django;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # Timeouts for large files
            proxy_connect_timeout 60s;
            proxy_send_timeout 600s;
            proxy_read_timeout 600s;
        }

        # All other requests
        location / {
            proxy_pass http://django;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

---

## Launch Production System

### 1. Build and Start Services

```bash
# Set up environment
cp .env.example .env
# Edit .env with your actual values

# Build images
docker-compose -f docker-compose.prod.yml build

# Start all services
docker-compose -f docker-compose.prod.yml up -d

# Check status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f web
docker-compose -f docker-compose.prod.yml logs -f celery_worker
```

### 2. Initialize Database

```bash
# Run migrations
docker-compose -f docker-compose.prod.yml exec web python manage.py migrate

# Create superuser
docker-compose -f docker-compose.prod.yml exec web python manage.py createsuperuser

# Load initial data
docker-compose -f docker-compose.prod.yml exec web python manage.py loaddata cybertrust/apps/controls/data/controls.json
```

### 3. Access Services

- **Web App:** https://yourdomain.com
- **API:** https://yourdomain.com/api/v1/
- **Flower (Monitoring):** https://yourdomain.com/flower/
- **Admin:** https://yourdomain.com/admin/

### 4. Monitor & Maintain

```bash
# View active tasks
docker-compose -f docker-compose.prod.yml exec celery_worker celery -A cybertrust inspect active

# Scale workers
docker-compose -f docker-compose.prod.yml up -d --scale celery_worker=3

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Stop services
docker-compose -f docker-compose.prod.yml down

# Clean up (⚠️ removes all data)
docker-compose -f docker-compose.prod.yml down -v
```

---

## SSL Certificate Setup (Let's Encrypt)

```bash
# Using Certbot with Docker
docker run -it --rm \
  -v /path/to/certs:/etc/letsencrypt \
  -v /path/to/webroot:/var/www/certbot \
  certbot/certbot certonly \
  --webroot \
  -w /var/www/certbot \
  -d yourdomain.com \
  -d www.yourdomain.com

# Renew certificates (run monthly)
docker run -it --rm \
  -v /path/to/certs:/etc/letsencrypt \
  certbot/certbot renew
```

---

## Monitoring & Alerts

### Check Application Health

```bash
curl https://yourdomain.com/health/
# Should return: {"status": "healthy", ...}
```

### Monitor Celery Tasks

```bash
# SSH to production server, then:
docker-compose -f docker-compose.prod.yml exec celery_worker celery -A cybertrust inspect
```

### Database Backups

```bash
# Daily backup script
#!/bin/bash
docker-compose -f docker-compose.prod.yml exec db pg_dump -U cybertrust cybertrust | \
  gzip > backups/cybertrust_$(date +%Y%m%d).sql.gz
```

---

## Performance Tuning

### Increase Celery Concurrency

In `docker-compose.prod.yml`, change:
```yaml
celery_worker:
  command: celery -A cybertrust worker -l info --concurrency=8  # Increase from 4
```

### Enable Redis Clustering

For high availability, use Redis Sentinel or Cluster mode.

### Database Connection Pooling

Add to settings:
```python
DATABASES = {
    'default': {
        'CONN_MAX_AGE': 600,  # Connection pooling
        'CONN_HEALTH_CHECKS': True,
    }
}
```

---

## Summary

You now have a production-ready setup with:
✅ Docker Compose orchestration
✅ PostgreSQL database
✅ Redis broker
✅ Celery workers
✅ Nginx reverse proxy
✅ SSL/TLS encryption
✅ Health checks & monitoring
✅ Horizontal scaling capability

Deploy with confidence! 🚀
