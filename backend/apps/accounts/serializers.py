from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
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
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


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
