
from django.contrib import admin

from .models import Organization, Membership, Invitation, VendorAssessment, AssessmentQuestion


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "vendor_type", "is_active", "created_at")
    search_fields = ("name", "slug")
    list_filter = ("is_active", "vendor_type")
    fieldsets = (
        ("Basic Info", {"fields": ("name", "slug", "industry", "size")}),
        ("Compliance", {"fields": ("vendor_type",)}),
        ("Status", {"fields": ("is_active", "created_at", "updated_at")}),
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "role", "is_active", "created_at")
    search_fields = ("user__email", "organization__name")
    list_filter = ("role", "is_active")


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("email", "organization", "role", "expires_at", "accepted_at", "created_at")
    search_fields = ("email", "organization__name")
    list_filter = ("role",)


@admin.register(VendorAssessment)
class VendorAssessmentAdmin(admin.ModelAdmin):
    list_display = ("organization", "status", "vendor_type_determined", "risk_score", "completed_at")
    search_fields = ("organization__name",)
    list_filter = ("status", "vendor_type_determined", "created_at")
    list_select_related = ("organization",)
    fieldsets = (
        ("Organization", {"fields": ("organization",)}),
        ("Assessment", {"fields": ("status", "vendor_type_determined", "risk_score")}),
        ("Responses", {"fields": ("responses",)}),
        ("Timeline", {"fields": ("created_at", "completed_at")}),
    )
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(AssessmentQuestion)
class AssessmentQuestionAdmin(admin.ModelAdmin):
    list_display = ("category", "order", "is_active", "created_at")
    search_fields = ("question_en", "question_ar")
    list_filter = ("category", "is_active", "created_at")
    fieldsets = (
        ("Question", {"fields": ("question_en", "question_ar")}),
        ("Configuration", {"fields": ("category", "order", "is_active")}),
    )
    ordering = ("order",)
