from rest_framework.permissions import BasePermission


class IsOrgAdmin(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return user.is_superuser or user.is_staff or user.groups.filter(name="org_admins").exists()
