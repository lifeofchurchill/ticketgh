from rest_framework import generics, permissions

from .serializers import RegisterSerializer


# POST /api/v1/auth/register/ : create a new attendee account
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer         # checks the data and creates the user
    permission_classes = [permissions.AllowAny]   # anyone can sign up, logged in or not