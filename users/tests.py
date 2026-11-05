import pytest
from django.urls import reverse

from users.models import User

# Every test in this file may use the (temporary) test database
pytestmark = pytest.mark.django_db

# A password that passes Django's strength rules
STRONG_PASSWORD = "Accra-Events-2026"


# ---------- Registration ----------

def test_register_creates_attendee(api_client):
    data = {"email": "ama@example.com", "password": STRONG_PASSWORD}

    response = api_client.post(reverse("register"), data, format="json")

    assert response.status_code == 201
    assert "password" not in response.data        # never sent back
    user = User.objects.get(email="ama@example.com")
    assert user.role == User.Role.ATTENDEE        # default role
    assert user.password != STRONG_PASSWORD       # not stored as plain text
    assert user.check_password(STRONG_PASSWORD)   # but it still works


def test_register_ignores_role_and_staff_fields(api_client):
    # Mass-assignment attempt: try to become an organizer and an admin
    data = {
        "email": "sneaky@example.com",
        "password": STRONG_PASSWORD,
        "role": "organizer",
        "is_staff": True,
    }

    response = api_client.post(reverse("register"), data, format="json")

    assert response.status_code == 201
    user = User.objects.get(email="sneaky@example.com")
    assert user.role == User.Role.ATTENDEE
    assert user.is_staff is False


def test_register_stores_email_in_lowercase(api_client):
    data = {"email": "Ama@Example.COM", "password": STRONG_PASSWORD}

    api_client.post(reverse("register"), data, format="json")

    assert User.objects.filter(email="ama@example.com").exists()


def test_register_rejects_duplicate_email_in_any_case(api_client, attendee):
    # The attendee fixture already uses attendee@example.com
    data = {"email": "ATTENDEE@example.com", "password": STRONG_PASSWORD}

    response = api_client.post(reverse("register"), data, format="json")

    assert response.status_code == 400
    assert "email" in response.data
    assert User.objects.count() == 1  # still only the original user


# Runs this test three times, once with each password
@pytest.mark.parametrize("weak_password", ["12345678", "password", "short"])
def test_register_rejects_weak_passwords(api_client, weak_password):
    data = {"email": "weak@example.com", "password": weak_password}

    response = api_client.post(reverse("register"), data, format="json")

    assert response.status_code == 400
    assert "password" in response.data
    assert not User.objects.exists()  # no account was created


# ---------- Login ----------

def test_login_returns_access_and_refresh_tokens(api_client, attendee):
    data = {"email": attendee.email, "password": "Test-pass-2026"}

    response = api_client.post(reverse("token_obtain"), data, format="json")

    assert response.status_code == 200
    assert "access" in response.data
    assert "refresh" in response.data


def test_login_with_wrong_password_fails(api_client, attendee):
    data = {"email": attendee.email, "password": "wrong-password"}

    response = api_client.post(reverse("token_obtain"), data, format="json")

    assert response.status_code == 401
    assert "access" not in response.data


def test_refresh_token_gives_new_access_token(api_client, attendee):
    # Arrange: log in to get a refresh token
    login = api_client.post(
        reverse("token_obtain"),
        {"email": attendee.email, "password": "Test-pass-2026"},
        format="json",
    )

    # Act: swap the refresh token for a new access token
    response = api_client.post(
        reverse("token_refresh"),
        {"refresh": login.data["refresh"]},
        format="json",
    )

    assert response.status_code == 200
    assert "access" in response.data


# ---------- Profile ----------

def test_profile_requires_login(api_client):
    response = api_client.get(reverse("me"))
    assert response.status_code == 401


def test_profile_works_with_a_real_token(api_client, attendee):
    # The full journey: log in, then send the token like an app would
    login = api_client.post(
        reverse("token_obtain"),
        {"email": attendee.email, "password": "Test-pass-2026"},
        format="json",
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

    response = api_client.get(reverse("me"))

    assert response.status_code == 200
    assert response.data["email"] == attendee.email


def test_profile_patch_changes_name_but_not_role(api_client, attendee):
    api_client.force_authenticate(user=attendee)

    response = api_client.patch(
        reverse("me"),
        {"first_name": "Ama", "role": "organizer"},
        format="json",
    )

    assert response.status_code == 200
    attendee.refresh_from_db()
    assert attendee.first_name == "Ama"             # allowed
    assert attendee.role == User.Role.ATTENDEE      # read-only, ignored


def test_profile_put_is_not_allowed(api_client, attendee):
    api_client.force_authenticate(user=attendee)

    response = api_client.put(reverse("me"), {"first_name": "Ama"}, format="json")

    assert response.status_code == 405