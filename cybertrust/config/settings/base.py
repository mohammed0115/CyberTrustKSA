from pathlib import Path

from decouple import Csv, config
from pathlib import Path
#BASE_DIR = Path(__file__).resolve().parent.parent.parent

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

SECRET_KEY = config("SECRET_KEY", default="unsafe-secret-key-change-me")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="", cast=Csv())

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "django_filters",
    "cybertrust.apps.accounts.apps.AccountsConfig",
    "cybertrust.apps.organizations.apps.OrganizationsConfig",
    "cybertrust.apps.controls.apps.ControlsConfig",
    "cybertrust.apps.evidence.apps.EvidenceConfig",
    "cybertrust.apps.ai_engine.apps.AiEngineConfig",
    "cybertrust.apps.audits.apps.AuditsConfig",
    "cybertrust.apps.reports.apps.ReportsConfig",
    "cybertrust.webui.apps.WebuiConfig",
    
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "cybertrust.config.middleware.ApiLoggingMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "cybertrust.config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "cybertrust.config.wsgi.application"
ASGI_APPLICATION = "cybertrust.config.asgi.application"

# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.mysql",
#         "NAME": config("DB_NAME", default="cybertrust"),
#         "USER": config("DB_USER", default="cybertrust_user"),
#         "PASSWORD": config("DB_PASSWORD", default="cybertrust"),
#         "HOST": config("DB_HOST", default="localhost"),
#         "PORT": config("DB_PORT", default=3306, cast=int),
#         "OPTIONS": {
#             "charset": "utf8mb4",
#             "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
#         },
#     }
# }


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "webui:login"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

STATIC_ROOT = config("STATIC_ROOT", default=str(BASE_DIR / "staticfiles"))
MEDIA_ROOT = config("MEDIA_ROOT", default=str(BASE_DIR / "media"))
MEDIA_URL = "/media/"

DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="no-reply@cybertrust.local")
OPENAI_API_KEY = config("OPENAI_API_KEY", default="")
OPENAI_MODEL = config("OPENAI_MODEL", default="gpt-4o-mini")
MAX_UPLOAD_SIZE = config("MAX_UPLOAD_SIZE", default=25 * 1024 * 1024, cast=int)
AI_TEXT_MAX_CHARS = config("AI_TEXT_MAX_CHARS", default=50000, cast=int)
EVIDENCE_ALLOWED_EXTENSIONS = {"pdf", "docx", "png", "jpg", "jpeg"}
TESSERACT_CMD = config("TESSERACT_CMD", default="")
TESSERACT_LANG = config("TESSERACT_LANG", default="eng")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
    ),
}

CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://redis:6379/0")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default=CELERY_BROKER_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

LOG_LEVEL = config("LOG_LEVEL", default="INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "[{asctime}] {levelname} {name} {message}",
            "style": "{",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        }
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": LOG_LEVEL},
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "api": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
