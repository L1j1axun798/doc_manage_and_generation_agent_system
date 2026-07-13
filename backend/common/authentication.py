from django.conf import settings
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied


class WebAuthnRequired(AuthenticationFailed):
    default_detail = "登录态未完成本人验证，请重新登录"
    default_code = "webauthn_required"


class PasswordChangeRequired(PermissionDenied):
    default_detail = "首次登录或密码重置后必须先修改密码"
    default_code = "password_change_required"


class SecureSessionAuthentication(SessionAuthentication):
    """Apply account and WebAuthn session requirements to every authenticated API."""

    password_change_exempt_paths = {
        "/api/v1/auth/logout/",
        "/api/v1/auth/me/",
        "/api/v1/auth/change-password/",
    }
    webauthn_exempt_paths = {"/api/v1/auth/logout/"}

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None

        user, auth = result
        if not user.is_active:
            raise AuthenticationFailed("账号不可用")

        path = request.path_info.rstrip("/") + "/"
        if (
            getattr(settings, "API_REQUIRE_WEBAUTHN_SESSION", True)
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
