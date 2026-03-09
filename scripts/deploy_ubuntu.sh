#!/usr/bin/env bash

set -euo pipefail

SERVER_IP="${SERVER_IP:-76.13.143.149}"
PUBLIC_PORT="${PUBLIC_PORT:-8000}"
APP_BIND_HOST="${APP_BIND_HOST:-127.0.0.1}"
APP_BIND_PORT="${APP_BIND_PORT:-8001}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-$PROJECT_DIR/.venv}"
ENV_FILE="${ENV_FILE:-$PROJECT_DIR/.env}"
APP_USER="${APP_USER:-${SUDO_USER:-$USER}}"
APP_GROUP="${APP_GROUP:-$(id -gn "$APP_USER")}"
GUNICORN_SERVICE="cybertrust-gunicorn"
CELERY_SERVICE="cybertrust-celery"
NGINX_SITE="cybertrustksa-8000"

if [[ $EUID -eq 0 ]]; then
    SUDO=""
else
    SUDO="sudo"
fi

log() {
    printf '\n[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1"
}

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Missing required command: $1" >&2
        exit 1
    fi
}

write_env_file() {
    local secret_key
    secret_key="$($PYTHON_BIN -c "import secrets; print(secrets.token_urlsafe(50))")"

    cat > "$ENV_FILE" <<EOF
DJANGO_SETTINGS_MODULE=cybertrust.config.settings.prod
SECRET_KEY=$secret_key
DEBUG=False
ALLOWED_HOSTS=$SERVER_IP,localhost,127.0.0.1
STATIC_ROOT=$PROJECT_DIR/staticfiles
MEDIA_ROOT=$PROJECT_DIR/media
DEFAULT_FROM_EMAIL=no-reply@$SERVER_IP
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
MAX_UPLOAD_SIZE=26214400
TESSERACT_CMD=/usr/bin/tesseract
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0
LOG_LEVEL=INFO
GUNICORN_BIND=$APP_BIND_HOST:$APP_BIND_PORT
GUNICORN_WORKERS=3
GUNICORN_THREADS=2
GUNICORN_TIMEOUT=120
GUNICORN_KEEPALIVE=5
EOF
    chmod 600 "$ENV_FILE"
}

write_systemd_service() {
    local service_name="$1"
    local exec_start="$2"

    $SUDO tee "/etc/systemd/system/${service_name}.service" >/dev/null <<EOF
[Unit]
Description=$service_name
After=network.target redis-server.service
Requires=redis-server.service

[Service]
Type=simple
User=$APP_USER
Group=$APP_GROUP
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=$ENV_FILE
Environment=PYTHONUNBUFFERED=1
ExecStart=$exec_start
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
}

write_nginx_config() {
    $SUDO tee "/etc/nginx/sites-available/$NGINX_SITE" >/dev/null <<EOF
server {
    listen $PUBLIC_PORT;
    server_name $SERVER_IP;

    client_max_body_size 25M;

    location /static/ {
        alias $PROJECT_DIR/staticfiles/;
        access_log off;
        expires 7d;
    }

    location /media/ {
        alias $PROJECT_DIR/media/;
        access_log off;
        expires 7d;
    }

    location / {
        proxy_pass http://$APP_BIND_HOST:$APP_BIND_PORT;
        include /etc/nginx/proxy_params;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
    }
}
EOF

    $SUDO ln -sfn "/etc/nginx/sites-available/$NGINX_SITE" "/etc/nginx/sites-enabled/$NGINX_SITE"
}

require_command "$PYTHON_BIN"
require_command git

log "Installing Ubuntu packages"
$SUDO apt-get update
$SUDO apt-get install -y \
    python3 \
    python3-venv \
    python3-dev \
    build-essential \
    pkg-config \
    default-libmysqlclient-dev \
    redis-server \
    nginx \
    tesseract-ocr

log "Preparing project directories"
mkdir -p "$PROJECT_DIR/logs" "$PROJECT_DIR/media" "$PROJECT_DIR/staticfiles"

if [[ ! -d "$VENV_DIR" ]]; then
    log "Creating virtual environment"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

log "Installing Python dependencies"
"$VENV_DIR/bin/pip" install --upgrade pip setuptools wheel
"$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt"

if [[ ! -f "$ENV_FILE" ]]; then
    log "Creating .env from deployment defaults"
    write_env_file
else
    log "Using existing .env file"
fi

set -a
source "$ENV_FILE"
set +a

log "Running Django database migrations"
"$VENV_DIR/bin/python" "$PROJECT_DIR/manage.py" migrate --noinput

log "Collecting static files"
"$VENV_DIR/bin/python" "$PROJECT_DIR/manage.py" collectstatic --noinput

log "Running Django system checks"
"$VENV_DIR/bin/python" "$PROJECT_DIR/manage.py" check

log "Writing systemd service files"
write_systemd_service \
    "$GUNICORN_SERVICE" \
    "$VENV_DIR/bin/gunicorn --config $PROJECT_DIR/gunicorn.conf.py cybertrust.config.wsgi:application"
write_systemd_service \
    "$CELERY_SERVICE" \
    "$VENV_DIR/bin/celery -A cybertrust worker -l info"

log "Writing Nginx site for http://$SERVER_IP:$PUBLIC_PORT"
write_nginx_config

log "Enabling and restarting services"
$SUDO systemctl daemon-reload
$SUDO systemctl enable redis-server "$GUNICORN_SERVICE" "$CELERY_SERVICE" nginx
$SUDO systemctl restart redis-server
$SUDO systemctl restart "$GUNICORN_SERVICE"
$SUDO systemctl restart "$CELERY_SERVICE"
$SUDO nginx -t
$SUDO systemctl restart nginx

if command -v ufw >/dev/null 2>&1; then
    log "Allowing public port $PUBLIC_PORT through UFW"
    $SUDO ufw allow "$PUBLIC_PORT/tcp" || true
fi

log "Deployment finished"
cat <<EOF

Public URL: http://$SERVER_IP:$PUBLIC_PORT
Project dir: $PROJECT_DIR
Environment file: $ENV_FILE

Review these items next:
1. Edit $ENV_FILE and set OPENAI_API_KEY.
2. Check service status with: sudo systemctl status $GUNICORN_SERVICE $CELERY_SERVICE nginx redis-server
3. Create an admin user if needed: $VENV_DIR/bin/python $PROJECT_DIR/manage.py createsuperuser

EOF
