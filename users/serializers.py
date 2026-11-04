from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

# Get our custom User model (the one AUTH_USER_MODEL points to)
User = get_user_model()


# Checks sign-up data and creates the new user
class RegisterSerializer(serializers.ModelSerializer):
    # write_only: accepted in the request, never included in the response
    # validate_password: applies Django's password strength rules
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ["id", "email", "password", "first_name", "last_name"]
        read_only_fields = ["id"]  # the database assigns the ID, not the user

    def validate_email(self, value):
        # Treat Kofi@Example.com and kofi@example.com as the same address
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def create(self, validated_data):
        # Use our manager so the password is hashed, never stored as plain text
        return User.objects.create_user(**validated_data)

# Shows the logged-in user's own profile, and lets them edit their name
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "role"]
        # These can be seen but not changed through this endpoint
        read_only_fields = ["id", "email", "role"]