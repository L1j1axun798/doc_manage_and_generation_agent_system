from rest_framework import serializers

from apps.folders.models import Folder
from common.validators import validate_uploaded_file

from .models import Document, DocumentVersion


class DocumentVersionSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source="uploaded_by.real_name", read_only=True)

    class Meta:
        model = DocumentVersion
        fields = [
            "id",
            "document",
            "version_number",
            "original_filename",
            "content_type",
            "file_size",
            "sha256",
            "uploaded_by",
            "uploaded_by_name",
            "created_at",
        ]
        read_only_fields = fields


class DocumentSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    folder_name = serializers.CharField(source="folder.name", read_only=True)
    created_by_name = serializers.CharField(source="created_by.real_name", read_only=True)
    deleted_by_name = serializers.CharField(source="deleted_by.real_name", read_only=True)
    current_version = DocumentVersionSerializer(read_only=True)

    class Meta:
        model = Document
        fields = [
            "id",
            "project",
            "project_name",
            "folder",
            "folder_name",
            "title",
            "description",
            "access_level",
            "current_version",
            "lock_version",
            "deleted_at",
            "deleted_by",
            "deleted_by_name",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class DocumentUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    access_level = serializers.ChoiceField(choices=Document.AccessLevel.choices, required=False)
    expected_updated_at = serializers.DateTimeField()


class DocumentMoveSerializer(serializers.Serializer):
    folder = serializers.PrimaryKeyRelatedField(queryset=Folder.objects.filter(is_active=True))
    expected_updated_at = serializers.DateTimeField()


class DocumentMutationSerializer(serializers.Serializer):
    expected_updated_at = serializers.DateTimeField()


class DocumentBatchDownloadSerializer(serializers.Serializer):
    document_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        max_length=20,
    )


class DocumentUploadSerializer(serializers.Serializer):
    folder = serializers.PrimaryKeyRelatedField(queryset=Folder.objects.filter(is_active=True))
    file = serializers.FileField()
    title = serializers.CharField(max_length=255, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    access_level = serializers.ChoiceField(
        choices=Document.AccessLevel.choices,
        default=Document.AccessLevel.INTERNAL,
    )

    def validate_file(self, uploaded_file):
        validate_uploaded_file(uploaded_file)
        return uploaded_file


class DocumentVersionUploadSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, uploaded_file):
        validate_uploaded_file(uploaded_file)
        return uploaded_file
