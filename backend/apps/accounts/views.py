from django.contrib.auth import (
    authenticate,
    get_user_model,
    login,
    logout,
    update_session_auth_hash,
)
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import audit_log

from .permissions import IsSystemAdmin
from .serializers import (
    ChangePasswordSerializer,
    LoginChallengeResponseSerializer,
    LoginSerializer,
    ResetPasswordSerializer,
    UserCreateSerializer,
    UserSerializer,
    WebAuthnCredentialSerializer,
    WebAuthnEnrollmentTicketCreateSerializer,
    WebAuthnEnrollmentTicketSerializer,
    WebAuthnLoginVerifySerializer,
    WebAuthnRegisterOptionsResponseSerializer,
    WebAuthnRegisterOptionsSerializer,
    WebAuthnRegisterVerifySerializer,
)
from .services import create_user, disable_user, reset_password, update_user
from .webauthn_services import (
    active_credentials_for_user,
    begin_login,
    begin_registration,
    create_enrollment_ticket,
    finish_login,
    finish_registration,
    reset_user_webauthn_credentials,
    revoke_credential,
)

User = get_user_model()
WEBAUTHN_SESSION_USER_KEY = "webauthn_verified_user_id"
WEBAUTHN_SESSION_VERIFIED_AT_KEY = "webauthn_verified_at"


def mark_webauthn_session(request, user) -> None:
    request.session[WEBAUTHN_SESSION_USER_KEY] = user.pk
    request.session[WEBAUTHN_SESSION_VERIFIED_AT_KEY] = timezone.now().isoformat()


def is_webauthn_session(request) -> bool:
    if not request.user.is_authenticated:
        return False
    return request.session.get(WEBAUTHN_SESSION_USER_KEY) == request.user.pk


class CsrfView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses=OpenApiTypes.OBJECT)
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        return Response({"csrfToken": get_token(request)})


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=LoginSerializer, responses=LoginChallengeResponseSerializer)
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]
        user = authenticate(request, username=username, password=password)

        if user is None:
            existing_user = User.objects.filter(username=username).first()
            if existing_user and not existing_user.is_active:
                audit_log(
                    user=existing_user,
                    action="auth.login",
                    resource=existing_user,
                    result="failure",
                    request=request,
                    error_message="inactive_user",
                )
                raise PermissionDenied("账号已停用")
            audit_log(
                user=existing_user,
                action="auth.login",
                resource=existing_user,
                result="failure",
                request=request,
                error_message="invalid_credentials",
            )
            raise AuthenticationFailed("用户名或密码错误")

        result = begin_login(user=user, request=request)
        return Response(
            {
                "status": "webauthn_required",
                "pending_token": result.token,
                "options": result.options,
            }
        )


class WebAuthnLoginVerifyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=WebAuthnLoginVerifySerializer, responses=UserSerializer)
    def post(self, request):
        serializer = WebAuthnLoginVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = finish_login(
            pending_token=serializer.validated_data["pending_token"],
            credential=serializer.validated_data["credential"],
            request=request,
        )
        login(request, user)
        mark_webauthn_session(request, user)
        audit_log(
            user=user,
            action="auth.login",
            resource=user,
            result="success",
            request=request,
        )
        return Response(UserSerializer(user).data)


class WebAuthnEnrollmentTicketView(APIView):
    permission_classes = [IsSystemAdmin]

    @extend_schema(
        request=WebAuthnEnrollmentTicketCreateSerializer,
        responses=WebAuthnEnrollmentTicketSerializer,
    )
    def post(self, request):
        serializer = WebAuthnEnrollmentTicketCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = get_object_or_404(User, pk=serializer.validated_data["user"])
        result = create_enrollment_ticket(user=user, actor=request.user, request=request)
        return Response(WebAuthnEnrollmentTicketSerializer(result).data, status=201)


class WebAuthnRegisterOptionsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=WebAuthnRegisterOptionsSerializer,
        responses=WebAuthnRegisterOptionsResponseSerializer,
    )
    def post(self, request):
        serializer = WebAuthnRegisterOptionsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = begin_registration(
            ticket_token=serializer.validated_data["ticket"],
            device_name=serializer.validated_data.get("device_name", ""),
        )
        return Response({"challenge_token": result.token, "options": result.options})


class WebAuthnRegisterVerifyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=WebAuthnRegisterVerifySerializer, responses=WebAuthnCredentialSerializer)
    def post(self, request):
        serializer = WebAuthnRegisterVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        credential = finish_registration(
            ticket_token=serializer.validated_data["ticket"],
            challenge_token=serializer.validated_data["challenge_token"],
            credential=serializer.validated_data["credential"],
            request=request,
        )
        return Response(WebAuthnCredentialSerializer(credential).data, status=201)


class WebAuthnCredentialListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=WebAuthnCredentialSerializer(many=True))
    def get(self, request):
        credentials = active_credentials_for_user(request.user).order_by("-created_at")
        return Response(WebAuthnCredentialSerializer(credentials, many=True).data)


class WebAuthnCredentialDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: OpenApiResponse(description="已撤销")})
    def delete(self, request, pk):
        credential = get_object_or_404(active_credentials_for_user(request.user), pk=pk)
        revoke_credential(credential=credential, actor=request.user, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class LogoutView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=None, responses={204: OpenApiResponse(description="已退出")})
    def post(self, request):
        user = request.user if request.user.is_authenticated else None
        if user is not None:
            audit_log(
                user=user,
                action="auth.logout",
                resource=user,
                result="success",
                request=request,
            )
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=UserSerializer)
    def get(self, request):
        if not is_webauthn_session(request):
            logout(request)
            raise AuthenticationFailed("登录态已过期，请重新登录")
        return Response(UserSerializer(request.user).data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ChangePasswordSerializer,
        responses={204: OpenApiResponse(description="密码已修改")},
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(serializer.validated_data["old_password"]):
            audit_log(
                user=user,
                action="auth.change_password",
                resource=user,
                result="failure",
                request=request,
                error_message="old_password_mismatch",
            )
            raise AuthenticationFailed("原密码错误")

        user.set_password(serializer.validated_data["new_password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        update_session_auth_hash(request, user)
        audit_log(
            user=user,
            action="auth.change_password",
            resource=user,
            result="success",
            request=request,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.order_by("-is_active", "id")
    permission_classes = [IsSystemAdmin]
    search_fields = ["username", "real_name", "phone", "employee_no"]
    ordering_fields = ["id", "username", "real_name", "is_active", "created_at"]
    ordering = ["-is_active", "id"]

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        return UserSerializer

    def perform_create(self, serializer):
        serializer.instance = create_user(
            actor=self.request.user,
            data=dict(serializer.validated_data),
            request=self.request,
        )

    def perform_update(self, serializer):
        serializer.instance = update_user(
            actor=self.request.user,
            user=self.get_object(),
            data=dict(serializer.validated_data),
            request=self.request,
        )

    @action(detail=True, methods=["post"])
    def disable(self, request, pk=None):
        user = self.get_object()
        disable_user(actor=request.user, user=user, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        user = self.get_object()
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        temporary_password = reset_password(
            actor=request.user,
            user=user,
            new_password=serializer.validated_data.get("new_password"),
            request=request,
        )
        return Response(
            {
                "temporary_password": temporary_password,
                "must_change_password": True,
            }
        )

    @action(detail=True, methods=["post"], url_path="webauthn-reset")
    def webauthn_reset(self, request, pk=None):
        user = self.get_object()
        revoked_count = reset_user_webauthn_credentials(
            user=user,
            actor=request.user,
            request=request,
        )
        return Response({"revoked_credentials": revoked_count})
