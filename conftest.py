import pytest
from rest_framework.test import APIClient

from users.models import User


# A fake app that sends requests to our API, without running the server
@pytest.fixture
def api_client():
    return APIClient()


# A user with the organizer role
@pytest.fixture
def organizer():
    return User.objects.create_user(
        email="organizer@example.com",
        password="Test-pass-2026",
        role=User.Role.ORGANIZER,
    )


# A second organizer, for "someone else's event" tests
@pytest.fixture
def other_organizer():
    return User.objects.create_user(
        email="other@example.com",
        password="Test-pass-2026",
        role=User.Role.ORGANIZER,
    )


# A normal user (attendee is the default role)
@pytest.fixture
def attendee():
    return User.objects.create_user(
        email="attendee@example.com",
        password="Test-pass-2026",
    )