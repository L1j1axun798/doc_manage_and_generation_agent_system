from django.test import Client
from django.urls import reverse


def test_client_request_id_is_replaced(client: Client) -> None:
    response = client.get(reverse("system:health"), HTTP_X_REQUEST_ID="req-test-1")

    assert response["X-Request-ID"] != "req-test-1"
    assert len(response["X-Request-ID"]) == 32
    assert response.json()["request_id"] == response["X-Request-ID"]
