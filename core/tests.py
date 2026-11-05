import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_health_check_is_public(api_client):
    # No login: monitoring tools must always reach it
    response = api_client.get(reverse("health"))

    assert response.status_code == 200
    assert response.data == {"status": "ok"}