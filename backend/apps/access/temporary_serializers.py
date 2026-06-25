from django.urls import reverse
from rest_framework import serializers

from apps.documents.models import DocumentVersion

from .models import TemporaryAccessGrant


class TemporaryAccessGrantSerializer(serializers.ModelSerializer):
    document = serializers.IntegerField(source="document_version.document_id", read_only=True)
    document_title = serializers.CharField(source="document_version.document.title", read_only=True)
    original_filename = serializers.CharField(
        source="document_version.original_filename",
        read_only=True,
    )
    created_by_name = serializers.CharField(source="created_by.real_name", read_only=True)
    revoked_by_name = serializers.CharField(source="revoked_by.real_name", read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    remaining_downloads = serializers.IntegerField(read_only=True)

    class Meta:
        model = TemporaryAccessGrant
        fields = [
            "id",
            "document_version",
            "document",
            "document_title",
            "original_filename",
            "max_downloads",
            "used_count",
            "remaining_downloads",
            "expires_at",
            "is_expired",
            "is_active",
            "created_by",
            "created_by_name",
            "created_at",
            "revoked_at",
            "revoked_by",
            "revoked_by_name",
            "last_used_at",
        ]
        read_only_fields = [
            "id",
            "document",
            "document_title",
            "original_filename",
            "used_count",
            "remaining_downloads",
            "is_expired",
            "is_active",
            "created_by",
            "created_by_name",
            "created_at",
            "revoked_at",
            "revoked_by",
            "revoked_by_name",
            "last_used_at",
        ]


class TemporaryAccessGrantCreateSerializer(serializers.Serializer):
    document_version = serializers.PrimaryKeyRelatedField(
        queryset=DocumentVersion.objects.select_related("document"),
    )
    expires_at = serializers.DateTimeField(required=False)
    max_downloads = serializers.IntegerField(min_value=1, default=1)


class TemporaryAccessGrantCreatedSerializer(TemporaryAccessGrantSerializer):
    token = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    class Meta(TemporaryAccessGrantSerializer.Meta):
        fields = [*TemporaryAccessGrantSerializer.Meta.fields, "token", "download_url"]

    def get_token(self, obj: TemporaryAccessGrant) -> str:
        return str(self.context["token"])

    def get_download_url(self, obj: TemporaryAccessGrant) -> str:
        token = self.context["token"]
        request = self.context.get("request")
        path = reverse("temporary-access-download", kwargs={"token": token})
        if request is None:
            return path
        return request.build_absolute_uri(path)
