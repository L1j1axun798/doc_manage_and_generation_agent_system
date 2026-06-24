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
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


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
