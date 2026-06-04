from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsManager(BasePermission):
    message = 'Only motorpool managers can perform this action.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_manager)

class IsManagerOrAuditor(BasePermission):
    message = 'You do not have permission to perform this action.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_manager:
            return True
        if request.user.is_auditor and request.method in SAFE_METHODS:
            return True
        return False

class IsManagerOrReadOwn(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_manager or user.is_auditor:
            return request.method in SAFE_METHODS or user.is_manager

        submitted_by = getattr(obj, 'submitted_by', None) or getattr(obj, 'driver', None)
        return submitted_by == user

class ReadOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.method in SAFE_METHODS
        )