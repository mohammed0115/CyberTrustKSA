from decouple import Csv, config

from .base import *  # noqa: F403


def _dedupe(items):
    return list(dict.fromkeys(item.strip() for item in items if item and item.strip()))


DEBUG = config("DEBUG", default=False, cast=bool)
PUBLIC_HOST = config("PUBLIC_HOST", default="")
SERVER_IP = config("SERVER_IP", default="76.13.143.149")
PUBLIC_PORT = config("PUBLIC_PORT", default="8000")

configured_hosts = config("ALLOWED_HOSTS", default="", cast=Csv())
ALLOWED_HOSTS = _dedupe(
    [*configured_hosts, "localhost", "127.0.0.1", PUBLIC_HOST, SERVER_IP]
)

CSRF_TRUSTED_ORIGINS = _dedupe(
    [
        *[f"http://{host}" for host in ALLOWED_HOSTS if host != "*"],
        *[f"https://{host}" for host in ALLOWED_HOSTS if host != "*"],
        *[f"http://{host}:{PUBLIC_PORT}" for host in ALLOWED_HOSTS if host != "*"],
        *[f"https://{host}:{PUBLIC_PORT}" for host in ALLOWED_HOSTS if host != "*"],
    ]
)
