from django.contrib import admin

from .models import AIAnalysisResult, ChatMessage


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("organization", "user", "role", "language", "created_at")
    search_fields = ("organization__name", "user__email", "content")
    list_filter = ("role", "language", "created_at")
    list_select_related = ("organization", "user")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)


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
