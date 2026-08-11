from django.conf import settings
from django.contrib.auth import get_user_model, logout
from django.utils.crypto import constant_time_compare
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

User = get_user_model()


class WebAuthnRequired(AuthenticationFailed):
    default_detail = "登录态未完成本人验证，请重新登录"
    default_code = "webauthn_required"


class PasswordChangeRequired(PermissionDenied):
    default_detail = "首次登录或密码重置后必须先修改密码"
    default_code = "password_change_required"


class SessionReplaced(AuthenticationFailed):
    default_detail = "您的账号已在其他设备或浏览器重新登录，当前登录已下线。"
    default_code = "session_replaced"


class SecureSessionAuthentication(SessionAuthentication):
    """Apply account and configured login-session requirements to every authenticated API."""

    password_change_exempt_paths = {
        "/api/v1/auth/logout/",
        "/api/v1/auth/me/",
        "/api/v1/auth/change-password/",
    }
    webauthn_exempt_paths = {"/api/v1/auth/logout/"}
    single_session_exempt_paths = {"/api/v1/auth/logout/"}

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None

        user, auth = result
        if not user.is_active:
            raise AuthenticationFailed("账号不可用")

        path = request.path_info.rstrip("/") + "/"
        if path not in self.single_session_exempt_paths:
            current_session_key = request.session.session_key
            active_session_key = user.active_session_key
            if active_session_key is None and current_session_key:
                claimed = User.objects.filter(
                    pk=user.pk,
                    active_session_key__isnull=True,
                ).update(active_session_key=current_session_key)
                if claimed:
                    active_session_key = current_session_key
                    user.active_session_key = current_session_key
                else:
                    active_session_key = User.objects.values_list(
                        "active_session_key", flat=True
                    ).get(pk=user.pk)

            if (
                not current_session_key
                or not active_session_key
                or not constant_time_compare(current_session_key, active_session_key)
            ):
                logout(request._request)
                raise SessionReplaced()

        if (
            getattr(settings, "LOGIN_REQUIRE_WEBAUTHN", True)
            and path not in self.webauthn_exempt_paths
        ):
            verified_user_id = request.session.get("webauthn_verified_user_id")
            if verified_user_id != user.pk:
                raise WebAuthnRequired()

        if getattr(settings, "API_ENFORCE_PASSWORD_CHANGE", True) and getattr(
            user, "must_change_password", False
        ):
            if path not in self.password_change_exempt_paths:
                raise PasswordChangeRequired()

        return user, auth


class SecureSessionAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "common.authentication.SecureSessionAuthentication"
    name = "cookieAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "cookie",
            "name": settings.SESSION_COOKIE_NAME,
        }
