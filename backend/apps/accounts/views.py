from django.contrib.auth import (
    authenticate,
    get_user_model,
    login,
    logout,
    update_session_auth_hash,
)
from django.middleware.csrf import get_token
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
    LoginSerializer,
    ResetPasswordSerializer,
    UserCreateSerializer,
    UserSerializer,
)
from .services import create_user, disable_user, reset_password, update_user

User = get_user_model()


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

    @extend_schema(request=LoginSerializer, responses=UserSerializer)
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

        login(request, user)
        audit_log(
            user=user,
            action="auth.login",
            resource=user,
            result="success",
            request=request,
        )
        return Response(UserSerializer(user).data)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: OpenApiResponse(description="已退出")})
    def post(self, request):
        user = request.user
        audit_log(user=user, action="auth.logout", resource=user, result="success", request=request)
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=UserSerializer)
    def get(self, request):
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
