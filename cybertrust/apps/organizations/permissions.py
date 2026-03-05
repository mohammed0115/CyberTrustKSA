from rest_framework.permissions import BasePermission, SAFE_METHODS


def is_org_admin(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.is_staff or user.groups.filter(name="org_admins").exists()


class IsOrgAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return is_org_admin(request.user)

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return is_org_admin(request.user)
