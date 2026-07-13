from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers

from .models import DocumentGrant


class DocumentGrantSerializer(serializers.ModelSerializer):
    document_title = serializers.CharField(source="document.title", read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)
    user_real_name = serializers.CharField(source="user.real_name", read_only=True)
    user_phone = serializers.CharField(source="user.phone", read_only=True)
    created_by_name = serializers.CharField(source="created_by.real_name", read_only=True)
    revoked_by_name = serializers.CharField(source="revoked_by.real_name", read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = DocumentGrant
        fields = [
            "id",
            "document",
            "document_title",
            "user",
            "user_username",
            "user_real_name",
            "user_phone",
            "can_view",
            "can_download",
            "can_update",
            "can_delete",
            "can_restore",
            "can_manage",
            "expires_at",
            "is_expired",
            "is_active",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
            "revoked_at",
            "revoked_by",
            "revoked_by_name",
        ]
        read_only_fields = [
            "id",
            "document_title",
            "user_username",
            "user_real_name",
            "user_phone",
            "is_expired",
            "is_active",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
            "revoked_at",
            "revoked_by",
            "revoked_by_name",
        ]

    def validate_user(self, user):
        if not user.is_active:
            raise serializers.ValidationError("不能授权给已停用用户")
        return user

    def validate(self, attrs):
        if self.instance is None:
            document = attrs.get("document")
            user = attrs.get("user")
            if (
                document is not None
                and user is not None
                and DocumentGrant.objects.filter(
                    document=document,
                    user=user,
                    revoked_at__isnull=True,
                )
                .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
                .exists()
            ):
                raise serializers.ValidationError("该用户已有未撤销授权")
        return attrs


class DocumentGrantUpdateSerializer(DocumentGrantSerializer):
    class Meta(DocumentGrantSerializer.Meta):
        read_only_fields = [*DocumentGrantSerializer.Meta.read_only_fields, "document", "user"]

    def validate(self, attrs):
        immutable_errors = {}
        if "document" in self.initial_data:
            immutable_errors["document"] = "授权文档不能修改"
        if "user" in self.initial_data:
            immutable_errors["user"] = "授权用户不能修改"
        if immutable_errors:
            raise serializers.ValidationError(immutable_errors)
        return super().validate(attrs)
