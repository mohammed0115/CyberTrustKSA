from django.contrib import admin

from .models import Control, ControlCategory, ControlScoreSnapshot


@admin.register(ControlCategory)
class ControlCategoryAdmin(admin.ModelAdmin):
    list_display = ("name_en", "name_ar", "code", "order", "created_at")
    search_fields = ("name_en", "name_ar", "code")
    list_filter = ("created_at",)
    ordering = ("order", "name_en")


@admin.register(Control)
class ControlAdmin(admin.ModelAdmin):
    list_display = ("code", "title_en", "category", "risk_level", "is_active", "created_at")
    search_fields = ("code", "title_en", "title_ar", "category__name_en", "category__name_ar")
    list_filter = ("risk_level", "is_active", "category")
    list_select_related = ("category",)
    ordering = ("category__order", "code")


@admin.register(ControlScoreSnapshot)
class ControlScoreSnapshotAdmin(admin.ModelAdmin):
    list_display = ("organization", "control", "score", "status", "computed_at")
    search_fields = ("organization__name", "control__code")
    list_filter = ("status", "control__risk_level", "computed_at")
    list_select_related = ("organization", "control")
    ordering = ("-computed_at",)
