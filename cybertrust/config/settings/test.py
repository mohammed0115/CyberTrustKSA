"""
Test Django settings - isolated test database and configurations.

Usage:
    export DJANGO_SETTINGS_MODULE=cybertrust.config.settings.test
    python manage.py test
    pytest
"""
from cybertrust.config.settings.base import *  # noqa: F401, F403

# Use in-memory SQLite database for faster tests
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'TEST': {
            'NAME': ':memory:',
        },
    }
}

# Disable migrations for faster test runs (optional)
class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = DisableMigrations()

# Disable password validation for tests
AUTH_PASSWORD_VALIDATORS = []

# Use simple password hasher for faster tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Disable logging during tests to reduce noise
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'CRITICAL',  # Only errors
    },
}

# Use a fast cache backend
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# Disable CSRF for API tests
MIDDLEWARE = [
    m for m in MIDDLEWARE
    if 'CSRFMiddleware' not in m
]

# Set OpenAI API key for tests (will be mocked anyway)
OPENAI_API_KEY = "sk-test-key-for-testing"
OPENAI_MODEL = "gpt-4o-mini"

# Email backend for tests
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Disable debug toolbar in tests
DEBUG = False
DEBUG_TOOLBAR = False

# Simplify session settings for tests
SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# Run tests serially to avoid database conflicts
TEST_PARALLEL_WORKERS = 1
