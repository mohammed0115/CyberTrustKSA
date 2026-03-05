
from django.contrib import admin

from .models import Organization, Membership, Invitation


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    search_fields = ("name", "slug")
    list_filter = ("is_active",)


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
