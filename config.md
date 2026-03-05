sudo apt update
sudo apt install -y mysql-server default-libmysqlclient-dev build-essential pkg-config


pip install python-decouple
from decouple import config, Csv

DATABASES = {
    "default": {
        "ENGINE": config("DB_ENGINE", default="django.db.backends.mysql"),
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST", default="127.0.0.1"),
        "PORT": config("DB_PORT", default="3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

ALLOWED_HOSTS = config("DJANGO_ALLOWED_HOSTS", cast=Csv())
DEBUG = config("DJANGO_DEBUG", cast=bool, default=False)
SECRET_KEY = config("DJANGO_SECRET_KEY")


CREATE DATABASE cybertrust CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'cybertrust_user'@'%' IDENTIFIED BY 'cybertrust';
GRANT ALL PRIVILEGES ON cybertrust.* TO 'cybertrust_user'@'%';
FLUSH PRIVILEGES;

Install deps: pip install djangorestframework djangorestframework-simplejwt.
With the default permission class set to IsAuthenticated, any DRF view will require auth unless overridden per-view.
Tests: not run.

If you want me to add SIMPLE_JWT settings (token lifetimes, signing key, etc.) or wire a custom User model, say the word.

venv\Scripts\activate
