from rest_framework import generics, permissions

from .serializers import RegisterSerializer, UserSerializer


# POST /api/v1/auth/register/ : create a new attendee account
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer         # checks the data and creates the user
    permission_classes = [permissions.AllowAny]   # anyone can sign up, logged in or not


# GET and PATCH /api/v1/auth/me/ : view or edit your own profile
class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]  # must be logged in
    http_method_names = ["get", "patch", "head", "options"]  # no PUT, only partial edits

    def get_object(self):
        # The profile is always the logged-in user's own; no ID in the address
        return self.request.user