from django.test import Client
from django.urls import reverse


def test_request_id_header_can_be_supplied(client: Client) -> None:
    response = client.get(reverse("system:health"), HTTP_X_REQUEST_ID="req-test-1")

    assert response["X-Request-ID"] == "req-test-1"
    assert response.json()["request_id"] == "req-test-1"
