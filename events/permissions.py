from rest_framework import permissions
from users.models import User


# Allows the request only if the user is logged in AND is an organizer
class IsOrganizer(permissions.BasePermission):
    # The error message sent back when the rule fails
    message = "Only organizers can do this."

    def has_permission(self, request, view):
        # DRF calls this before the view runs; True = allowed, False = blocked
        return (
            request.user.is_authenticated
            and request.user.role == User.Role.ORGANIZER
        )

# Allows changes only to events the logged-in user organizes
class IsEventOwner(permissions.BasePermission):
    message = "You can only change your own events."

    def has_object_permission(self, request, view, obj):
        # obj is the specific event being touched; DRF passes it in
        return obj.organizer == request.user