from django.contrib import admin

from .models import Evidence, EvidenceControlLink


@admin.register(Evidence)
class EvidenceAdmin(admin.ModelAdmin):
    list_display = ("organization", "filename", "file_type", "status", "uploaded_by", "created_at")
    search_fields = ("file", "organization__name", "uploaded_by__email")
    list_filter = ("file_type", "status", "created_at")
    list_select_related = ("organization", "uploaded_by")
    ordering = ("-created_at",)


@admin.register(EvidenceControlLink)
class EvidenceControlLinkAdmin(admin.ModelAdmin):
    list_display = ("evidence", "control", "linked_by", "created_at")
    search_fields = ("evidence__file", "control__code", "linked_by__email")
    list_filter = ("created_at",)
    list_select_related = ("control", "linked_by", "evidence")
    ordering = ("-created_at",)
