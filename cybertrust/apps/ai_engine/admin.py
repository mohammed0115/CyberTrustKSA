from django.contrib import admin

from .models import AIAnalysisResult


@admin.register(AIAnalysisResult)
class AIAnalysisResultAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "control",
        "evidence",
        "status",
        "score",
        "confidence",
        "model_name",
        "created_at",
    )
    search_fields = ("control__code", "evidence__file", "organization__name")
    list_filter = ("status", "model_name", "created_at")
    list_select_related = ("organization", "control", "evidence")
    ordering = ("-created_at",)
