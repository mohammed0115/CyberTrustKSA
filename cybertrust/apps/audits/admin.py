from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "organization", "actor", "created_at")
    search_fields = ("event_type", "organization__name", "actor__email")
    list_filter = ("event_type", "created_at")
    list_select_related = ("organization", "actor")
    ordering = ("-created_at",)
