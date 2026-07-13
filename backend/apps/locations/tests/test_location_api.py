from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.accounts.models import WebAuthnCredential
from apps.audit.models import AuditLog
from apps.locations.models import LocationReport

User = get_user_model()


def make_user(username: str, role: str = User.Role.DATA_OPERATOR, **kwargs):
    return User.objects.create_user(
        username=username,
        password="Password123!",
        real_name=username,
        role=role,
        **kwargs,
    )


class VerifiedCredential:
    id = 1


@pytest.fixture(autouse=True)
def mock_location_webauthn(monkeypatch):
    monkeypatch.setattr(
        "apps.locations.views.verify_location_challenge",
        lambda **kwargs: VerifiedCredential(),
    )


def with_webauthn(payload: dict) -> dict:
    return {
        **payload,
        "webauthn": {
            "challenge_token": "challenge-token",
            "credential": {"id": "credential-001"},
        },
    }


def create_webauthn_credential(user) -> WebAuthnCredential:
    return WebAuthnCredential.objects.create(
        user=user,
        name="本人手机",
        credential_id="credential-001",
        public_key=b"public-key",
        sign_count=0,
        transports=["internal"],
        device_type="single_device",
    )


@pytest.mark.django_db
def test_authenticated_user_can_report_success_location(client):
    user = make_user("operator")
    client.force_login(user)

    response = client.post(
        "/api/v1/locations/report/",
        with_webauthn(
            {
                "longitude": "116.397128",
                "latitude": "39.916527",
                "accuracy": "25.50",
                "address": "北京市东城区",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 201
    report = LocationReport.objects.get()
    assert report.user == user
    assert report.longitude == Decimal("116.397128")
    assert report.latitude == Decimal("39.916527")
    assert report.report_status == LocationReport.ReportStatus.SUCCESS
    assert response.json()["reported_at"]
    assert AuditLog.objects.filter(action="location.report", result="success").exists()


@pytest.mark.django_db
def test_report_accepts_browser_precision_coordinates(client):
    user = make_user("operator")
    client.force_login(user)

    response = client.post(
        "/api/v1/locations/report/",
        with_webauthn(
            {
                "longitude": 116.397128456789,
                "latitude": 39.916527987654,
                "accuracy": 25.507,
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 201
    report = LocationReport.objects.get()
    assert report.longitude == Decimal("116.397128")
    assert report.latitude == Decimal("39.916528")
    assert report.accuracy == Decimal("25.51")


@pytest.mark.django_db
def test_report_accepts_locate_failed_without_coordinates(client):
    user = make_user("operator")
    client.force_login(user)

    response = client.post(
        "/api/v1/locations/report/",
        with_webauthn(
            {
                "report_status": "locate_failed",
                "failure_reason": "用户拒绝定位授权",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 201
    report = LocationReport.objects.get()
    assert report.longitude is None
    assert report.latitude is None
    assert report.accuracy is None
    assert report.failure_reason == "用户拒绝定位授权"
    assert report.report_status == LocationReport.ReportStatus.LOCATE_FAILED


@pytest.mark.django_db
def test_report_validates_success_coordinates_and_accuracy(client):
    user = make_user("operator")
    client.force_login(user)

    missing_coordinate = client.post(
        "/api/v1/locations/report/",
        with_webauthn({"longitude": "116.397128"}),
        content_type="application/json",
    )
    invalid_longitude = client.post(
        "/api/v1/locations/report/",
        with_webauthn({"longitude": "181", "latitude": "39.916527"}),
        content_type="application/json",
    )
    invalid_accuracy = client.post(
        "/api/v1/locations/report/",
        with_webauthn({"longitude": "116.397128", "latitude": "39.916527", "accuracy": "-1"}),
        content_type="application/json",
    )

    assert missing_coordinate.status_code == 400
    assert invalid_longitude.status_code == 400
    assert invalid_accuracy.status_code == 400
    assert LocationReport.objects.count() == 0


@pytest.mark.django_db
def test_report_requires_login(client):
    response = client.post(
        "/api/v1/locations/report/",
        with_webauthn({"longitude": "116.397128", "latitude": "39.916527"}),
        content_type="application/json",
    )

    assert response.status_code in {403, 401}
    assert LocationReport.objects.count() == 0


@pytest.mark.django_db
def test_report_requires_webauthn_assertion(client):
    user = make_user("operator")
    client.force_login(user)

    response = client.post(
        "/api/v1/locations/report/",
        {"longitude": "116.397128", "latitude": "39.916527"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert LocationReport.objects.count() == 0


@pytest.mark.django_db
def test_report_challenge_returns_webauthn_options_for_bound_user(client):
    user = make_user("operator")
    create_webauthn_credential(user)
    client.force_login(user)

    response = client.post(
        "/api/v1/locations/report/challenge/",
        {"longitude": "116.397128", "latitude": "39.916527"},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["token"]
    assert response.json()["options"]["challenge"]


@pytest.mark.django_db
def test_me_latest_returns_only_current_user_and_should_report(client):
    user = make_user("operator")
    other_user = make_user("other")
    LocationReport.objects.create(
        user=other_user,
        longitude="120.000000",
        latitude="30.000000",
        reported_at=timezone.now(),
    )
    LocationReport.objects.create(
        user=user,
        longitude="116.397128",
        latitude="39.916527",
        reported_at=timezone.now(),
    )
    client.force_login(user)

    response = client.get("/api/v1/locations/me/latest/")

    assert response.status_code == 200
    data = response.json()
    assert data["user"]["id"] == user.id
    assert data["location_status"] == "normal"
    assert data["should_report"] is False
    assert data["latest_report"]["longitude"] == "116.397128"


@pytest.mark.django_db
def test_me_latest_marks_expired_success_report_as_should_report(client):
    user = make_user("operator")
    LocationReport.objects.create(
        user=user,
        longitude="116.397128",
        latitude="39.916527",
        reported_at=timezone.now() - timedelta(hours=5),
    )
    client.force_login(user)

    response = client.get("/api/v1/locations/me/latest/")

    assert response.status_code == 200
    assert response.json()["location_status"] == "expired"
    assert response.json()["should_report"] is True


@pytest.mark.django_db
def test_admin_latest_requires_system_admin(client):
    user = make_user("operator")
    client.force_login(user)

    response = client.get("/api/v1/locations/admin/latest/")

    assert response.status_code == 403


@pytest.mark.django_db
def test_admin_latest_returns_active_non_temporary_users_with_statuses(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    normal = make_user("normal")
    expired = make_user("expired")
    failed = make_user("failed")
    make_user("today-unreported")
    inactive = make_user("inactive", is_active=False)
    temporary = make_user("temporary", User.Role.TEMPORARY_USER)
    now = timezone.now()
    LocationReport.objects.create(
        user=normal,
        longitude="116.397128",
        latitude="39.916527",
        reported_at=now - timedelta(hours=1),
    )
    LocationReport.objects.create(
        user=expired,
        longitude="117.000000",
        latitude="40.000000",
        reported_at=now - timedelta(hours=5),
    )
    LocationReport.objects.create(
        user=failed,
        report_status=LocationReport.ReportStatus.LOCATE_FAILED,
        failure_reason="定位失败",
        reported_at=now,
    )
    LocationReport.objects.create(
        user=inactive,
        longitude="118.000000",
        latitude="41.000000",
        reported_at=now,
    )
    LocationReport.objects.create(
        user=temporary,
        longitude="119.000000",
        latitude="42.000000",
        reported_at=now,
    )
    client.force_login(admin)

    response = client.get("/api/v1/locations/admin/latest/")

    assert response.status_code == 200
    rows = {item["user"]["username"]: item for item in response.json()}
    assert set(rows) == {"admin", "normal", "expired", "failed", "today-unreported"}
    assert rows["admin"]["location_status"] == "today_unreported"
    assert rows["normal"]["location_status"] == "normal"
    assert rows["expired"]["location_status"] == "expired"
    assert rows["failed"]["location_status"] == "locate_failed"
    assert rows["today-unreported"]["location_status"] == "today_unreported"
