from rest_framework.permissions import BasePermission


class IsBearerAuthenticated(BasePermission):
    """
    Allows access only to authenticated users.
    Works with TokenAuthentication (Bearer token) and SessionAuthentication.
    Applied to write/compute endpoints — GET endpoints stay AllowAny globally.
    """

    message = (
        "Authentication required. Provide a valid Bearer token in Authorization header."
    )

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)
