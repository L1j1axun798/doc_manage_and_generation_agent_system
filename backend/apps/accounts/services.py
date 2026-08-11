from secrets import token_urlsafe
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import HttpRequest

from apps.audit.services import audit_log

User = get_user_model()


@transaction.atomic
def activate_login_session(*, request: HttpRequest, user: Any) -> bool:
    """Make the request session the user's only valid login session."""
    request.session.save()
    session_key = request.session.session_key
    if not session_key:
        raise RuntimeError("Authenticated session has no session key")

    locked_user = User.objects.select_for_update().get(pk=user.pk)
    previous_session_key = locked_user.active_session_key
    locked_user.active_session_key = session_key
    locked_user.save(update_fields=["active_session_key"])
    user.active_session_key = session_key
    return bool(previous_session_key and previous_session_key != session_key)


def clear_active_login_session(*, request: HttpRequest, user: Any) -> None:
    session_key = request.session.session_key
    if not session_key:
        return
    User.objects.filter(pk=user.pk, active_session_key=session_key).update(
        active_session_key=None
    )


@transaction.atomic
def create_user(*, actor: Any, data: dict[str, Any], request: Any = None) -> Any:
    password = data.pop("password")
    user = User.objects.create_user(**data)
    user.set_password(password)
    user.save(update_fields=["password"])
    audit_log(
        user=actor,
        action="user.create",
        resource=user,
        result="success",
        request=request,
        after_data=user_snapshot(user),
    )
    return user


@transaction.atomic
def update_user(*, actor: Any, user: Any, data: dict[str, Any], request: Any = None) -> Any:
    before_data = user_snapshot(user)
    for field, value in data.items():
        setattr(user, field, value)
    if not user.is_active:
        user.active_session_key = None
    user.save()
    audit_log(
        user=actor,
        action="user.update",
        resource=user,
        result="success",
        request=request,
        before_data=before_data,
        after_data=user_snapshot(user),
    )
    return user


@transaction.atomic
def disable_user(*, actor: Any, user: Any, request: Any = None) -> None:
    before_data = user_snapshot(user)
    user.is_active = False
    user.active_session_key = None
    user.save(update_fields=["is_active", "active_session_key"])
    audit_log(
        user=actor,
        action="user.disable",
        resource=user,
        result="success",
        request=request,
        before_data=before_data,
        after_data=user_snapshot(user),
    )


@transaction.atomic
def reset_password(
    *,
    actor: Any,
    user: Any,
    new_password: str | None = None,
    request: Any = None,
) -> str:
    temporary_password = new_password or token_urlsafe(12)
    user.set_password(temporary_password)
    user.must_change_password = True
    user.active_session_key = None
    user.save(update_fields=["password", "must_change_password", "active_session_key"])
    audit_log(
        user=actor,
        action="user.reset_password",
        resource=user,
        result="success",
        request=request,
        after_data={"user_id": user.pk, "must_change_password": True},
    )
    return temporary_password


def user_snapshot(user: Any) -> dict[str, Any]:
    return {
        "id": user.pk,
        "username": user.username,
        "real_name": user.real_name,
        "employee_no": user.employee_no,
        "role": user.role,
        "phone": user.phone,
        "email": user.email,
        "is_active": user.is_active,
        "must_change_password": user.must_change_password,
    }
