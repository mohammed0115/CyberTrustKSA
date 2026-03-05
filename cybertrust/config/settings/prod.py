from decouple import Csv, config

from .base import *  # noqa: F403

DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="", cast=Csv())
