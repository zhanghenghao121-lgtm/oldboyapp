from rest_framework.permissions import BasePermission
from apps.console.auth import resolve_console_user


class IsConsoleAdmin(BasePermission):
    def has_permission(self, request, view):
        user, _ = resolve_console_user(request)
        if user:
            request.console_user = user
            return True
        return False
