from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ChangePasswordView,
    CsrfView,
    LoginView,
    LogoutView,
    MeView,
    UserViewSet,
    WebAuthnCredentialDetailView,
    WebAuthnCredentialListView,
    WebAuthnEnrollmentTicketView,
    WebAuthnLoginVerifyView,
    WebAuthnRegisterOptionsView,
    WebAuthnRegisterVerifyView,
)

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")

urlpatterns = [
    path("auth/csrf/", CsrfView.as_view(), name="auth-csrf"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path(
        "auth/webauthn/login/verify/",
        WebAuthnLoginVerifyView.as_view(),
        name="auth-webauthn-login-verify",
    ),
    path(
        "auth/webauthn/enrollment-tickets/",
        WebAuthnEnrollmentTicketView.as_view(),
        name="auth-webauthn-enrollment-ticket",
    ),
    path(
        "auth/webauthn/register/options/",
        WebAuthnRegisterOptionsView.as_view(),
        name="auth-webauthn-register-options",
    ),
    path(
        "auth/webauthn/register/verify/",
        WebAuthnRegisterVerifyView.as_view(),
        name="auth-webauthn-register-verify",
    ),
    path(
        "auth/webauthn/credentials/",
        WebAuthnCredentialListView.as_view(),
        name="auth-webauthn-credentials",
    ),
    path(
        "auth/webauthn/credentials/<int:pk>/",
        WebAuthnCredentialDetailView.as_view(),
        name="auth-webauthn-credential-detail",
    ),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/change-password/", ChangePasswordView.as_view(), name="auth-change-password"),
    *router.urls,
]
