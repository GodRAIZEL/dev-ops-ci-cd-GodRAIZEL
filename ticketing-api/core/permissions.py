from rest_framework.permissions import SAFE_METHODS, BasePermission


def is_admin(user):
    return bool(user and user.is_authenticated and user.is_admin_role)


class AdminWriteOrReadOnly(BasePermission):
    """Any authenticated user may read; only admins may create/update/delete."""

    message = "Administrator role required for this action."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.method in SAFE_METHODS or is_admin(request.user)


class BookingPermission(BasePermission):
    """Authenticated users manage their own bookings; admins also edit/delete any."""

    message = "Administrator role required for this action."
    admin_actions = {"update", "partial_update", "destroy"}

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if getattr(view, "action", None) in self.admin_actions:
            return is_admin(request.user)
        return True
