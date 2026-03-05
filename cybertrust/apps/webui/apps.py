from django.apps import AppConfig


class WebuiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    # Point to the real app module.
    name = "cybertrust.webui"
