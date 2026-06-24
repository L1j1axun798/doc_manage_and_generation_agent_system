from django.test import Client
from django.urls import reverse


def test_health_check_returns_ok(client: Client) -> None:
    response = client.get(reverse("system:health"))

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response["X-Request-ID"]
