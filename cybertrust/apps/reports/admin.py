from django.contrib import admin

from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("organization", "name", "report_type", "status", "size_display", "created_at")
    search_fields = ("name", "organization__name")
    list_filter = ("report_type", "status", "created_at")
    list_select_related = ("organization", "created_by")
    ordering = ("-created_at",)
