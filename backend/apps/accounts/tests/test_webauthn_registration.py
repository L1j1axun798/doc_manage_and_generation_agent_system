from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.structs import CredentialDeviceType

from apps.accounts.models import (
    WebAuthnChallenge,
    WebAuthnCredential,
    WebAuthnEnrollmentTicket,
)
from apps.accounts.webauthn_services import finish_registration, hash_token
from apps.audit.models import AuditLog

User = get_user_model()


def prepare_registration(user):
    ticket_token = "ticket-token"
    challenge_token = "challenge-token"
    WebAuthnEnrollmentTicket.objects.create(
        user=user,
        token_hash=hash_token(ticket_token),
        expires_at=timezone.now() + timedelta(minutes=10),
    )
    WebAuthnChallenge.objects.create(
        user=user,
        purpose=WebAuthnChallenge.Purpose.REGISTER,
        challenge=bytes_to_base64url(b"registration-challenge"),
        token_hash=hash_token(challenge_token),
        metadata={
            "ticket_hash": hash_token(ticket_token),
            "device_name": "iPhone",
        },
        expires_at=timezone.now() + timedelta(minutes=5),
    )
    return ticket_token, challenge_token


def mock_synced_passkey_verification(monkeypatch):
    verification = SimpleNamespace(
        credential_id=b"iphone-passkey-id",
        credential_public_key=b"iphone-passkey-public-key",
        sign_count=0,
        aaguid="00000000-0000-0000-0000-000000000000",
        credential_device_type=CredentialDeviceType.MULTI_DEVICE,
        credential_backed_up=True,
    )
    monkeypatch.setattr(
        "apps.accounts.webauthn_services.verify_registration_response",
        lambda **kwargs: verification,
    )


@pytest.mark.django_db
@override_settings(WEBAUTHN_ALLOW_SYNCED_PASSKEYS=True)
def test_finish_registration_accepts_and_audits_synced_passkey(monkeypatch):
    user = User.objects.create_user(
        username="iphone-user",
        password="iPhonePass123!",
        real_name="iPhone 员工",
    )
    ticket_token, challenge_token = prepare_registration(user)
    mock_synced_passkey_verification(monkeypatch)

    credential = finish_registration(
        ticket_token=ticket_token,
        challenge_token=challenge_token,
        credential={"response": {"transports": ["internal", "hybrid"]}},
    )

    assert credential.device_type == CredentialDeviceType.MULTI_DEVICE.value
    assert credential.backed_up is True
    assert credential.transports == ["internal", "hybrid"]
    audit = AuditLog.objects.get(action="auth.webauthn.register", result="success")
    assert audit.after_data == {
        "credential_id": credential.credential_id,
        "device_type": "multi_device",
        "backed_up": True,
    }


@pytest.mark.django_db
@override_settings(WEBAUTHN_ALLOW_SYNCED_PASSKEYS=False)
def test_finish_registration_can_retain_strict_single_device_policy(monkeypatch):
    user = User.objects.create_user(
        username="strict-device-user",
        password="StrictDevice123!",
        real_name="严格策略员工",
    )
    ticket_token, challenge_token = prepare_registration(user)
    mock_synced_passkey_verification(monkeypatch)

    with pytest.raises(ValidationError, match="不允许使用可同步"):
        finish_registration(
            ticket_token=ticket_token,
            challenge_token=challenge_token,
            credential={"response": {"transports": ["internal"]}},
        )

    assert not WebAuthnCredential.objects.filter(user=user).exists()
