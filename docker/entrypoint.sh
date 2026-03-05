#!/usr/bin/env sh
set -e

DB_HOST="${DB_HOST:-mysql}"
DB_PORT="${DB_PORT:-3306}"

echo "Waiting for database at ${DB_HOST}:${DB_PORT}..."
python - <<'PY'
import os
import socket
import sys
import time

host = os.getenv("DB_HOST", "mysql")
port = int(os.getenv("DB_PORT", "3306"))
timeout = int(os.getenv("DB_WAIT_TIMEOUT", "30"))

start = time.time()
while True:
    try:
        with socket.create_connection((host, port), timeout=2):
            break
    except OSError:
        if time.time() - start > timeout:
            print(f"Database not reachable after {timeout}s", file=sys.stderr)
            sys.exit(1)
        time.sleep(1)

print("Database is up.")
PY

if [ "${SKIP_MIGRATIONS:-0}" = "1" ]; then
  echo "Skipping migrations."
else
  python manage.py migrate
fi

if [ "${DJANGO_COLLECTSTATIC:-0}" = "1" ]; then
  python manage.py collectstatic --noinput
fi

exec "$@"
