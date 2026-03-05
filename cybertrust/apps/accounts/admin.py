from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .forms import CustomUserChangeForm, CustomUserCreationForm
from .models import OrganizationInvite, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    model = User
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    ordering = ("email",)
    list_display = ("email", "organization", "is_staff", "is_active")
    list_filter = ("is_staff", "is_active", "organization")
    search_fields = ("email",)

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Organization", {"fields": ("organization",)}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2", "is_staff", "is_superuser", "is_active", "organization"),
            },
        ),
    )


@admin.register(OrganizationInvite)
class OrganizationInviteAdmin(admin.ModelAdmin):
    list_display = ("email", "organization", "invited_by", "created_at", "accepted_at")
    list_filter = ("organization", "accepted_at")
    search_fields = ("email",)
