from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied, ValidationError
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url, options_to_json
from webauthn.helpers.exceptions import WebAuthnException
from webauthn.helpers.structs import (
    AuthenticatorAttachment,
    AuthenticatorSelectionCriteria,
    AuthenticatorTransport,
    CredentialDeviceType,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from apps.audit.services import audit_log

from .models import User, WebAuthnChallenge, WebAuthnCredential, WebAuthnEnrollmentTicket


@dataclass(frozen=True)
class WebAuthnOptionsResult:
    token: str
    options: dict[str, Any]


def create_enrollment_ticket(
    *, user: User, actor: User | None, request: Any | None = None
) -> dict[str, Any]:
    token = secrets.token_urlsafe(32)
    ticket = WebAuthnEnrollmentTicket.objects.create(
        user=user,
        token_hash=hash_token(token),
        created_by=actor,
        expires_at=timezone.now()
        + timedelta(seconds=settings.WEBAUTHN_ENROLLMENT_TICKET_TTL_SECONDS),
    )
    audit_log(
        user=actor,
        action="auth.webauthn.ticket.create",
        resource=user,
        result="success",
        request=request,
        after_data={"ticket_id": ticket.id, "expires_at": ticket.expires_at.isoformat()},
    )
    return {
        "token": token,
        "expires_at": ticket.expires_at,
        "user": user,
    }


def begin_registration(*, ticket_token: str, device_name: str = "") -> WebAuthnOptionsResult:
    ticket = get_available_ticket(ticket_token)
    challenge = secrets.token_bytes(32)
    challenge_token = secrets.token_urlsafe(32)
    user = ticket.user
    existing_credentials = [
        credential_descriptor(credential) for credential in active_credentials_for_user(user)
    ]
    options = generate_registration_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        rp_name=settings.WEBAUTHN_RP_NAME,
        user_id=str(user.pk).encode("utf-8"),
        user_name=user.username,
        user_display_name=user.real_name or user.username,
        challenge=challenge,
        timeout=settings.WEBAUTHN_CHALLENGE_TTL_SECONDS * 1000,
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment=AuthenticatorAttachment.PLATFORM,
            resident_key=ResidentKeyRequirement.DISCOURAGED,
            require_resident_key=False,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=existing_credentials,
    )
    WebAuthnChallenge.objects.create(
        user=user,
        purpose=WebAuthnChallenge.Purpose.REGISTER,
        challenge=bytes_to_base64url(challenge),
        token_hash=hash_token(challenge_token),
        metadata={
            "ticket_hash": hash_token(ticket_token),
            "device_name": device_name,
        },
        expires_at=timezone.now() + timedelta(seconds=settings.WEBAUTHN_CHALLENGE_TTL_SECONDS),
    )
    return WebAuthnOptionsResult(token=challenge_token, options=options_as_dict(options))


@transaction.atomic
def finish_registration(
    *,
    ticket_token: str,
    challenge_token: str,
    credential: dict[str, Any],
    request: Any | None = None,
) -> WebAuthnCredential:
    ticket = get_available_ticket(ticket_token, lock=True)
    challenge = get_available_challenge(
        token=challenge_token,
        purpose=WebAuthnChallenge.Purpose.REGISTER,
        lock=True,
    )
    if challenge.user_id != ticket.user_id or challenge.metadata.get("ticket_hash") != hash_token(
        ticket_token
    ):
        raise ValidationError("绑定票据与验证挑战不匹配")

    try:
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(challenge.challenge),
            expected_rp_id=settings.WEBAUTHN_RP_ID,
            expected_origin=settings.WEBAUTHN_ALLOWED_ORIGINS,
            require_user_verification=True,
        )
    except WebAuthnException as exc:
        audit_log(
            user=ticket.user,
            action="auth.webauthn.register",
            resource=ticket.user,
            result="failure",
            request=request,
            error_message=str(exc),
        )
        consume_challenge(challenge)
        raise AuthenticationFailed("本人验证绑定失败") from exc

    if verification.credential_device_type == CredentialDeviceType.MULTI_DEVICE:
        consume_challenge(challenge)
        raise ValidationError("不允许使用可同步到多设备的通行密钥作为定位凭据")
    if verification.credential_backed_up:
        consume_challenge(challenge)
        raise ValidationError("不允许使用已备份的通行密钥作为定位凭据")

    credential_id = bytes_to_base64url(verification.credential_id)
    if WebAuthnCredential.objects.filter(credential_id_hash=hash_token(credential_id)).exists():
        consume_challenge(challenge)
        raise ValidationError("该验证设备已绑定")

    webauthn_credential = WebAuthnCredential.objects.create(
        user=ticket.user,
        name=challenge.metadata.get("device_name", ""),
        credential_id=credential_id,
        public_key=verification.credential_public_key,
        sign_count=verification.sign_count,
        transports=get_registration_transports(credential),
        device_type=verification.credential_device_type.value,
        backed_up=verification.credential_backed_up,
        aaguid=verification.aaguid,
    )
    ticket.used_at = timezone.now()
    ticket.save(update_fields=["used_at"])
    consume_challenge(challenge)
    audit_log(
        user=ticket.user,
        action="auth.webauthn.register",
        resource=webauthn_credential,
        result="success",
        request=request,
        after_data={"credential_id": credential_id, "device_type": webauthn_credential.device_type},
    )
    return webauthn_credential


def begin_login(*, user: User, request: Any | None = None) -> WebAuthnOptionsResult:
    credentials = list(active_credentials_for_user(user))
    if not credentials:
        audit_log(
            user=user,
            action="auth.password_verified",
            resource=user,
            result="failure",
            request=request,
            error_message="webauthn_not_enrolled",
        )
        raise PermissionDenied("账号尚未绑定本人验证设备，请联系系统管理员")

    challenge = secrets.token_bytes(32)
    pending_token = secrets.token_urlsafe(32)
    options = generate_authentication_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        challenge=challenge,
        timeout=settings.WEBAUTHN_CHALLENGE_TTL_SECONDS * 1000,
        allow_credentials=[credential_descriptor(credential) for credential in credentials],
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    WebAuthnChallenge.objects.create(
        user=user,
        purpose=WebAuthnChallenge.Purpose.LOGIN,
        challenge=bytes_to_base64url(challenge),
        token_hash=hash_token(pending_token),
        expires_at=timezone.now() + timedelta(seconds=settings.WEBAUTHN_CHALLENGE_TTL_SECONDS),
    )
    audit_log(
        user=user,
        action="auth.password_verified",
        resource=user,
        result="success",
        request=request,
    )
    return WebAuthnOptionsResult(token=pending_token, options=options_as_dict(options))


@transaction.atomic
def finish_login(
    *, pending_token: str, credential: dict[str, Any], request: Any | None = None
) -> User:
    challenge = get_available_challenge(
        token=pending_token,
        purpose=WebAuthnChallenge.Purpose.LOGIN,
        lock=True,
    )
    webauthn_credential = get_credential_for_assertion(
        user=challenge.user,
        credential=credential,
    )
    verify_assertion(
        challenge=challenge,
        credential_record=webauthn_credential,
        credential=credential,
        request=request,
        failure_action="auth.webauthn.login",
    )
    consume_challenge(challenge)
    audit_log(
        user=challenge.user,
        action="auth.webauthn.login",
        resource=webauthn_credential,
        result="success",
        request=request,
    )
    return challenge.user


def begin_location_challenge(
    *, user: User, payload_hash: str, request: Any | None = None
) -> WebAuthnOptionsResult:
    credentials = list(active_credentials_for_user(user))
    if not credentials:
        audit_log(
            user=user,
            action="location.challenge",
            resource=user,
            result="denied",
            request=request,
            error_message="webauthn_not_enrolled",
        )
        raise PermissionDenied("账号尚未绑定本人验证设备，请联系系统管理员")

    challenge = secrets.token_bytes(32)
    challenge_token = secrets.token_urlsafe(32)
    options = generate_authentication_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        challenge=challenge,
        timeout=settings.WEBAUTHN_CHALLENGE_TTL_SECONDS * 1000,
        allow_credentials=[credential_descriptor(credential) for credential in credentials],
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    WebAuthnChallenge.objects.create(
        user=user,
        purpose=WebAuthnChallenge.Purpose.LOCATION,
        challenge=bytes_to_base64url(challenge),
        token_hash=hash_token(challenge_token),
        metadata={"payload_hash": payload_hash},
        expires_at=timezone.now() + timedelta(seconds=settings.WEBAUTHN_CHALLENGE_TTL_SECONDS),
    )
    return WebAuthnOptionsResult(token=challenge_token, options=options_as_dict(options))


@transaction.atomic
def verify_location_challenge(
    *,
    user: User,
    challenge_token: str,
    credential: dict[str, Any],
    payload_hash: str,
    request: Any | None = None,
) -> WebAuthnCredential:
    challenge = get_available_challenge(
        token=challenge_token,
        purpose=WebAuthnChallenge.Purpose.LOCATION,
        lock=True,
    )
    if challenge.user_id != user.id:
        raise PermissionDenied("定位验证不属于当前用户")
    if challenge.metadata.get("payload_hash") != payload_hash:
        consume_challenge(challenge)
        raise ValidationError("定位数据与本人验证挑战不匹配")

    webauthn_credential = get_credential_for_assertion(user=user, credential=credential)
    verify_assertion(
        challenge=challenge,
        credential_record=webauthn_credential,
        credential=credential,
        request=request,
        failure_action="location.webauthn",
    )
    consume_challenge(challenge)
    return webauthn_credential


def reset_user_webauthn_credentials(*, user: User, actor: User, request: Any | None = None) -> int:
    credentials = list(WebAuthnCredential.objects.filter(user=user, is_active=True))
    for credential in credentials:
        credential.revoke(actor=actor)
    WebAuthnEnrollmentTicket.objects.filter(user=user, used_at__isnull=True).update(
        used_at=timezone.now()
    )
    WebAuthnChallenge.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
    audit_log(
        user=actor,
        action="auth.webauthn.reset",
        resource=user,
        result="success",
        request=request,
        after_data={"revoked_credentials": len(credentials)},
    )
    return len(credentials)


def revoke_credential(
    *, credential: WebAuthnCredential, actor: User, request: Any | None = None
) -> None:
    active_count = WebAuthnCredential.objects.filter(user=credential.user, is_active=True).count()
    if active_count <= 1:
        raise ValidationError("不能删除最后一个本人验证设备")
    credential.revoke(actor=actor)
    audit_log(
        user=actor,
        action="auth.webauthn.credential.revoke",
        resource=credential,
        result="success",
        request=request,
    )


def active_credentials_for_user(user: User) -> QuerySet[WebAuthnCredential]:
    return WebAuthnCredential.objects.filter(user=user, is_active=True, revoked_at__isnull=True)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def options_as_dict(options: Any) -> dict[str, Any]:
    return json.loads(options_to_json(options))


def credential_descriptor(credential: WebAuthnCredential) -> PublicKeyCredentialDescriptor:
    return PublicKeyCredentialDescriptor(
        id=base64url_to_bytes(credential.credential_id),
        transports=parse_transports(credential.transports),
    )


def parse_transports(transports: list[str] | None) -> list[AuthenticatorTransport]:
    parsed: list[AuthenticatorTransport] = []
    for transport in transports or []:
        try:
            parsed.append(AuthenticatorTransport(transport))
        except ValueError:
            continue
    return parsed


def get_registration_transports(credential: dict[str, Any]) -> list[str]:
    transports = credential.get("response", {}).get("transports", [])
    return [str(transport) for transport in transports if isinstance(transport, str)]


def get_available_ticket(ticket_token: str, *, lock: bool = False) -> WebAuthnEnrollmentTicket:
    queryset = WebAuthnEnrollmentTicket.objects.select_related("user")
    if lock:
        queryset = queryset.select_for_update()
    ticket = queryset.filter(token_hash=hash_token(ticket_token)).first()
    if not ticket or not ticket.is_available:
        raise ValidationError("绑定票据无效或已过期")
    return ticket


def get_available_challenge(
    *,
    token: str,
    purpose: str,
    lock: bool = False,
) -> WebAuthnChallenge:
    queryset = WebAuthnChallenge.objects.select_related("user")
    if lock:
        queryset = queryset.select_for_update()
    challenge = queryset.filter(token_hash=hash_token(token), purpose=purpose).first()
    if not challenge or not challenge.is_available:
        raise AuthenticationFailed("本人验证挑战无效或已过期")
    return challenge


def consume_challenge(challenge: WebAuthnChallenge) -> None:
    challenge.used_at = timezone.now()
    challenge.save(update_fields=["used_at"])


def get_credential_for_assertion(*, user: User, credential: dict[str, Any]) -> WebAuthnCredential:
    credential_id = credential.get("id") or credential.get("rawId")
    if not isinstance(credential_id, str):
        raise AuthenticationFailed("本人验证凭据无效")
    webauthn_credential = (
        active_credentials_for_user(user)
        .filter(credential_id_hash=hash_token(credential_id))
        .first()
    )
    if not webauthn_credential:
        raise PermissionDenied("当前设备未绑定，不能用于登录或定位")
    return webauthn_credential


def verify_assertion(
    *,
    challenge: WebAuthnChallenge,
    credential_record: WebAuthnCredential,
    credential: dict[str, Any],
    request: Any | None = None,
    failure_action: str,
) -> None:
    try:
        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(challenge.challenge),
            expected_rp_id=settings.WEBAUTHN_RP_ID,
            expected_origin=settings.WEBAUTHN_ALLOWED_ORIGINS,
            credential_public_key=bytes(credential_record.public_key),
            credential_current_sign_count=credential_record.sign_count,
            require_user_verification=True,
        )
    except WebAuthnException as exc:
        consume_challenge(challenge)
        audit_log(
            user=challenge.user,
            action=failure_action,
            resource=credential_record,
            result="failure",
            request=request,
            error_message=str(exc),
        )
        raise AuthenticationFailed("本人验证失败") from exc

    credential_record.sign_count = verification.new_sign_count
    credential_record.device_type = verification.credential_device_type.value
    credential_record.backed_up = verification.credential_backed_up
    credential_record.last_used_at = timezone.now()
    credential_record.save(update_fields=["sign_count", "device_type", "backed_up", "last_used_at"])
