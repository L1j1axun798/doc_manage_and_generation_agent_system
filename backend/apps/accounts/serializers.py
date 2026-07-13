from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import User, WebAuthnCredential


class UserSerializer(serializers.ModelSerializer):
    webauthn_enabled = serializers.SerializerMethodField()
    webauthn_credentials_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "real_name",
            "employee_no",
            "role",
            "phone",
            "email",
            "is_active",
            "must_change_password",
            "webauthn_enabled",
            "webauthn_credentials_count",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_webauthn_enabled(self, obj: User) -> bool:
        annotated_count = getattr(obj, "active_webauthn_credentials_count", None)
        if annotated_count is not None:
            return bool(annotated_count)
        return obj.webauthn_credentials.filter(is_active=True, revoked_at__isnull=True).exists()

    def get_webauthn_credentials_count(self, obj: User) -> int:
        annotated_count = getattr(obj, "active_webauthn_credentials_count", None)
        if annotated_count is not None:
            return int(annotated_count)
        return obj.webauthn_credentials.filter(is_active=True, revoked_at__isnull=True).count()


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "password",
            "real_name",
            "employee_no",
            "role",
            "phone",
            "email",
            "is_active",
            "must_change_password",
        ]
        read_only_fields = ["id"]

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False)


class WebAuthnOptionsResponseSerializer(serializers.Serializer):
    token = serializers.CharField()
    options = serializers.DictField()


class LoginChallengeResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    pending_token = serializers.CharField()
    options = serializers.DictField()


class WebAuthnLoginVerifySerializer(serializers.Serializer):
    pending_token = serializers.CharField()
    credential = serializers.DictField()


class WebAuthnEnrollmentTicketCreateSerializer(serializers.Serializer):
    user = serializers.IntegerField()


class WebAuthnEnrollmentTicketSerializer(serializers.Serializer):
    token = serializers.CharField()
    expires_at = serializers.DateTimeField()
    user = UserSerializer()


class WebAuthnRegisterOptionsSerializer(serializers.Serializer):
    ticket = serializers.CharField()
    device_name = serializers.CharField(required=False, allow_blank=True, max_length=120)


class WebAuthnRegisterOptionsResponseSerializer(serializers.Serializer):
    challenge_token = serializers.CharField()
    options = serializers.DictField()


class WebAuthnRegisterVerifySerializer(serializers.Serializer):
    ticket = serializers.CharField()
    challenge_token = serializers.CharField()
    credential = serializers.DictField()


class WebAuthnCredentialSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebAuthnCredential
        fields = [
            "id",
            "name",
            "credential_id",
            "transports",
            "device_type",
            "backed_up",
            "created_at",
            "last_used_at",
        ]
        read_only_fields = fields


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(trim_whitespace=False)
    new_password = serializers.CharField(trim_whitespace=False)

    def validate_new_password(self, value: str) -> str:
        validate_password(value, self.context["request"].user)
        return value


class ResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(required=False, min_length=8, trim_whitespace=False)

    def validate_new_password(self, value: str) -> str:
        validate_password(value)
        return value
